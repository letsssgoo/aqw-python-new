"""``V2Core`` -- the shared engine every Ultra V2 fight is written on.

The reference splits this between ``CoreLoneWolf`` (presets, skill engine, army
sync, potions, scrolls, enhancements) and each script's own ``Run`` /
``RunFightAttempts``; this is that core half.  A boss module keeps only what is
boss-shaped: its cells, its role rules, and the order it does things in.

Deliberate differences from the reference, each decided with the user:

* **no GCD/haste reading** -- the reference computes "when is the next skill
  ready" from the Flash client (``world.GCDTS``/``world.GCD``/haste).  This
  engine paces from the cooldown packets it already receives, so a cast is sent
  only when the server says the slot is ready;
* **no ``Flash.GetGameObject``** -- bank state, mana, health and auras come from
  the models (:mod:`model.player`, :mod:`model.aura`);
* ``Events.RunToArea`` becomes a packet subscription on ``zoneSet`` (the same
  mechanism Ultra Speaker and Ledgermayne use).

``StopRequested`` from :mod:`core.command` unwinds everything, so a stopped pane
ends where it stood instead of walking the rest of the script.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional, Sequence

from bot.ultra import party
from bot.ultra.v2 import enhancements, potions, presets, scrolls
from bot.ultra.v2.options import UltraOptions, UltraSpec, compositions
from bot.ultra.v2.sync import PARTY_SIZE, SLOTS, Sync
from bot.ultra.v2.presets import KINGS_ECHO, STRICT, Preset

#: King's Echo thresholds, verbatim from ``CoreLoneWolf``.
RESIDUAL_ENERGY_SKILL4 = 24
KINGS_ECHO_MANA_FLOOR = 12
KINGS_ECHO_SURVIVAL_HP = 50.0
KINGS_ECHO_SURVIVAL_MANA = 24.0

#: A wipe needs this many panes down inside one attempt (``ShouldResetFight``'s
#: default ``deadPlayerThreshold``).
WIPE_DEATHS = 2


class V2Core:
    """One pane of one ultra: gear, pots, skills, wipeout and quest gates."""

    def __init__(self, cmd, spec: UltraSpec, options: UltraOptions,
                 slot: int = 1, *, poll_ms: int = 150):
        self.cmd = cmd
        self.bot = cmd.bot
        self.spec = spec
        self.options = options
        self.slot = int(slot)
        self.poll_ms = poll_ms
        self.sync = Sync(spec.id, self.slot, PARTY_SIZE)
        self.preset: Preset = presets.preset_for(spec.id, options.composition,
                                                 self.slot, options.extras)
        self.aborted = ""
        self.taunt_requested = False
        self._attempt_started = 0.0
        self._death_reported = False
        self._skill_task: Optional[asyncio.Task] = None
        self._log = None
        #: When True the rotation pauses while the target's counter-attack aura
        #: is up.  Ezrajal is the boss that needs it (v1: ``respect_counter_attack``).
        self.respect_counter_attack = False
        #: Extra targets tried before the boss, in order (Engineer's two adds).
        self.target_priority: tuple = ()

    # ------------------------------------------------------------------ log
    @property
    def alias(self) -> str:
        return f"player{self.slot}"

    def log(self, message: str) -> None:
        """One line, always tagged with the ultra, slot and class."""
        line = f"[V2 {self.spec.title.replace('Ultra ', '')}] {self.alias} " \
               f"({self.preset.cls}): {message}"
        try:
            self.bot.log(line)
        except Exception:
            print(line)

    def describe(self) -> str:
        """The line a run prints before it touches anything."""
        short = " / ".join(presets.preset_for_class(cls).short
                           for cls in compositions(self.spec.id)[
                               self.options.composition])
        return (f"slot {self.slot} wears {self.preset.cls} in the "
                f"{self.options.composition} composition ({short})")

    def abort(self, reason: str) -> bool:
        """Say why the run is stopping, tell the whole party, answer False.

        One pane stopping stops the party: the abort marker is written for every
        slot (the reference's ``StopArmySync``), so the others unwind at their
        next step or loop check instead of waiting on a party that is already
        gone.
        """
        self.aborted = reason
        self.log(f"stopping: {reason}")
        if self.sync.enabled:
            self.sync.stop(reason)
        return False

    # --------------------------------------------------------------- access
    async def validate_access(self) -> bool:
        """Quest chain and level, the reference's ``ValidateUltraAccess``."""
        if not await self.cmd.is_completed_before(self.spec.prereq_quest):
            self.log(f'Quest Locked Run: finish "{self.spec.prereq_name}" '
                     f'[{self.spec.prereq_quest}] first.')
            return self.abort(f"prerequisite quest {self.spec.prereq_quest} is "
                              f"not done")
        level = int(getattr(self.bot.player, "LEVEL", 0) or 0)
        if level < self.spec.min_level:
            self.log(f"level {level} is below the {self.spec.min_level} this "
                     f"ultra needs.")
            return self.abort(f"level {level} < {self.spec.min_level}")
        if not self.cmd.is_in_inventory_or_bank(self.preset.cls):
            self.log(f"{self.preset.cls} is in neither the inventory nor the "
                     f"bank.")
            return self.abort(f"{self.preset.cls} is not owned")
        return True

    # ---------------------------------------------------------------- setup
    async def prepare(self, *, scroll: Optional[str] = None,
                      drop_combat_potion: bool = False) -> bool:
        """Equip the class, wear the enhancements, stock the potions and scroll."""
        self.log(f"starting setup: {self.describe()}")
        if not await self.cmd.equip_item(self.preset.cls):
            return self.abort(f"could not equip {self.preset.cls}")

        if self.options.use_enhancements:
            self.log(f"enhancements: {enhancements.describe(self.preset)}")
            if not await enhancements.prepare(self.cmd, self.preset):
                return self.abort("an enhancement the composition needs is "
                                  "missing")
        else:
            self.log("enhancements: skipped by the option.")

        if self.options.use_potions:
            combat = None if drop_combat_potion else self.preset.combat_potion
            for name in (self.preset.tonic, self.preset.elixir, combat):
                if name:
                    await potions.prepare(self.cmd, name)
        else:
            self.log("potions: skipped by the option.")

        if scroll:
            if not await scrolls.prepare(self.cmd, scroll):
                return self.abort(f"{scroll} stock is short")
        self.log("setup finished.")
        return True

    async def use_potions(self, *, drop_combat_potion: bool = False) -> None:
        """Drink the tonic/elixir and equip slot 5 for this attempt."""
        if not self.options.use_potions:
            return
        combat = None if drop_combat_potion else self.preset.combat_potion
        await potions.use_loadout(self.cmd, self.preset.tonic,
                                  self.preset.elixir, combat)

    # ----------------------------------------------------------------- fight
    async def precast_buffs(self, skills: Sequence[int] = (1, 2, 3),
                            gap_ms: int = 1000) -> None:
        """Cast the opening buffs before a pull -- and again after every wipe.

        v1's ``precast_buffs``, which the daily bosses use: the buffs are gone
        after a wipe, so a reset attempt that walks back in without them fights
        with no buffs at all.  Every Ultra V2 module calls this before
        :meth:`start_skills` and after :meth:`handle_reset`.
        """
        for skill in skills:
            await self.cmd.use_skill(skill, buff_only=True)
            await self.cmd.sleep(gap_ms)

    def counter_attack_active(self, target: str) -> bool:
        """True while the target carries Ezrajal's ``Counter Attack`` aura."""
        return self.target_aura("Counter Attack")

    async def start_skills(self, target: str, *, use_survival: bool = False,
                           taunter: bool = False) -> None:
        """Run the skill engine in the background until :meth:`stop_skills`."""
        await self.stop_skills()
        self._skill_task = asyncio.create_task(
            self._skill_loop(target, use_survival=use_survival,
                             taunter=taunter))

    async def stop_skills(self) -> None:
        task, self._skill_task = self._skill_task, None
        if task is None or task.done():
            return
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    def request_taunt(self) -> None:
        """Ask the engine for skill 5 on the current target (``RequestTaunt``)."""
        self.taunt_requested = True

    async def _skill_loop(self, target: str, *, use_survival: bool,
                          taunter: bool) -> None:
        preset = self.preset
        index = 0
        while (self.cmd.is_still_connected()
               and not self.bot.player.ISDEAD
               and not self.sync.aborted()
               and self.cmd.is_monster_alive(self.pick_target(target))):
            target = self.pick_target(target)
            if self.taunt_requested:
                self.taunt_requested = False
                if taunter and await self.cmd.use_skill(5, target_monsters=target):
                    self.log("taunt cast (skill 5).")
            elif (self.respect_counter_attack
                  and self.counter_attack_active(target)):
                # Attacking into the counter attack is what kills the party.
                await self.cmd.sleep(self.poll_ms)
            elif preset.mode == KINGS_ECHO:
                await self._kings_echo_step(target, use_survival)
            elif preset.mode == STRICT:
                index = await self._strict_step(target, index)
            else:
                await self._simple_step(target)
            await self.cmd.sleep(self.poll_ms)

    async def _simple_step(self, target: str) -> None:
        """Cast the first rotation skill the server says is ready."""
        for slot in self.preset.skills:
            if not self.bot.player.canUseSkill(slot):
                continue
            if await self.cmd.use_skill(slot, target_monsters=target):
                return
        await self.cmd.sleep(100)

    async def _strict_step(self, target: str, index: int) -> int:
        """Walk the fixed rotation, advancing only on a cast (``Strict``)."""
        rotation = self.preset.skills
        if not rotation:
            return 0
        slot = rotation[index % len(rotation)]
        if await self.cmd.use_skill(slot, target_monsters=target):
            return (index + 1) % len(rotation)
        return index

    async def _kings_echo_step(self, target: str, use_survival: bool) -> None:
        """``KingsEchoSkillEngine``: energy/mana first, survival second."""
        player = self.bot.player
        residual = self.self_aura_value("Residual Energy")
        if ((residual >= RESIDUAL_ENERGY_SKILL4
             or player.MANA < KINGS_ECHO_MANA_FLOOR)
                and player.canUseSkill(4)):
            if await self.cmd.use_skill(4, target_monsters=target):
                return

        hp = _percent(player.CURRENT_HP, player.MAX_HP)
        mp = _percent(player.MANA, player.MAX_MP)
        if (use_survival and hp < KINGS_ECHO_SURVIVAL_HP
                and mp > KINGS_ECHO_SURVIVAL_MANA
                and player.canUseSkill(3)):
            if await self.cmd.use_skill(3, target_monsters=target):
                return

        for slot in self.preset.skills:
            if player.canUseSkill(slot):
                if await self.cmd.use_skill(slot, target_monsters=target):
                    return
        await self.cmd.sleep(100)

    # ---------------------------------------------------------------- auras
    def self_aura(self, name: str):
        """The player's aura of that name, or None."""
        return self.bot.player.getAura(name)

    def self_aura_value(self, name: str) -> int:
        aura = self.self_aura(name)
        return int(getattr(aura, "value", 0) or 0) if aura else 0

    def pick_target(self, default: str) -> str:
        """The first alive target from :attr:`target_priority`, else ``default``.

        Engineer is the boss that needs it: two adds (``id.2``, ``id.1``) come
        before the main boss (``id.3``), and the reference re-reads that order
        every pass of the fight loop.
        """
        for candidate in self.target_priority:
            if self.cmd.is_monster_alive(candidate):
                return candidate
        return default

    def target_aura(self, name: str) -> bool:
        """True when the current target carries that aura (``Target.GetAura``)."""
        monster = self.cmd.get_monster(self._target_name())
        if monster is None:
            return False
        from core.utils import normalize
        wanted = normalize(name)
        return any(normalize(getattr(aura, "name", "")) == wanted
                   for aura in getattr(monster, "AURAS", []) or [])

    def _target_name(self) -> str:
        return f"id.{self.spec.monster_id}"

    # -------------------------------------------------------------- wipeout
    def begin_attempt(self) -> None:
        """Mark the moment this attempt started, for the wipe detector."""
        self._attempt_started = __import__("time").time()
        self._death_reported = False

    def note_death(self) -> None:
        """Publish this pane's death once per attempt."""
        if self._death_reported or not self.bot.player.ISDEAD:
            return
        self._death_reported = True
        if self.sync.enabled:
            party.report_death(self.sync.name, self.slot)
        self.log("died.")

    def should_reset(self, attempt: int) -> bool:
        """True when a wipe took ``WIPE_DEATHS`` panes down in this attempt."""
        if attempt <= 0 or not self.sync.enabled:
            return False
        deaths = party.death_times(self.sync.name, SLOTS)
        down = [slot for slot, when in deaths.items()
                if when >= self._attempt_started]
        if len(down) >= WIPE_DEATHS:
            self.log(f"wipe detected: slots {', '.join(map(str, sorted(down)))} "
                     f"went down this attempt.")
            return True
        return False

    async def wait_respawn(self, attempt: int) -> str:
        """Wait out a death; ``"alive"``, ``"reset"`` or ``"stopped"``."""
        while (self.cmd.is_still_connected() and self.bot.player.ISDEAD
               and not self.sync.aborted()):
            self.note_death()
            if self.should_reset(attempt):
                return "reset"
            await self.cmd.sleep(500)
        if not self.cmd.is_still_connected() or self.sync.aborted():
            return "stopped"
        if self.sync.enabled:
            party.clear_death(self.sync.name, self.slot)
        self.log("respawned.")
        return "alive"

    async def handle_reset(self, attempt: int) -> bool:
        """Regroup at the safe room after a wipe (``HandleFightReset``)."""
        await self.stop_skills()
        self.log(f"attempt {attempt} reset; regrouping at "
                 f"{self.spec.safe_cell}/{self.spec.safe_pad}.")
        await self.cmd.jump_cell(self.spec.safe_cell, self.spec.safe_pad)
        alive = await self.wait_respawn(attempt)
        if alive == "stopped":
            return False
        if alive == "reset":
            return False
        if not self.in_safe_room():
            self.log("could not reach the safe room after the reset.")
            return False
        return self.sync.step(f"FIGHT_RESET_{attempt}_SAFE")

    # ------------------------------------------------------------------ map
    async def join(self, map_name: Optional[str] = None, *,
                   safe: bool = True) -> None:
        """Join the ultra's map (private room honoured) and take the safe cell."""
        target = map_name or self.spec.map
        room = self.options.private_room or None
        await self.cmd.join_map(target, room)
        if safe:
            await self.cmd.jump_cell(self.spec.safe_cell, self.spec.safe_pad)

    def in_safe_room(self) -> bool:
        cell = str(getattr(self.bot.player, "CELL", "") or "")
        return cell.lower() == self.spec.safe_cell.lower()

    def in_boss_room(self) -> bool:
        cell = str(getattr(self.bot.player, "CELL", "") or "")
        return cell.lower() == self.spec.boss_cell.lower()

    async def jump_boss(self) -> None:
        await self.cmd.jump_cell(self.spec.boss_cell, self.spec.boss_pad)

    # ---------------------------------------------------------------- quests
    async def accept_quest(self) -> bool:
        """Accept the ultra's quest, the reference's ``AcceptUltraQuest``."""
        if not await self.cmd.ensure_accept_quest(self.spec.quest):
            return self.abort(f"quest {self.spec.quest} could not be accepted "
                              f"(the daily may already be done)")
        return True

    async def finish_quest(self) -> bool:
        """Turn the ultra's quest in, the reference's ``CompleteUltraQuest``."""
        await self.cmd.jump_cell(self.spec.safe_cell, self.spec.safe_pad)
        if not await self.cmd.ensure_turn_in_quest(self.spec.quest):
            return self.abort(f"quest {self.spec.quest} could not be turned in")
        self.sync.mark_done()
        return True

    # ------------------------------------------------------------- reporting
    def status(self) -> Dict[str, Any]:
        """Small dict the hub page shows while the run is alive."""
        return {
            "ultra": self.spec.id,
            "slot": self.slot,
            "alias": self.alias,
            "class": self.preset.cls,
            "composition": self.options.composition,
            "cell": getattr(self.bot.player, "CELL", ""),
            "aborted": self.aborted,
        }


def _percent(value: int, maximum: int) -> float:
    return (value / maximum * 100.0) if maximum else 0.0
