"""Ultra Dage -- port of ``UltraDage_LW.cs``.

One boss (``id.1``) and one long fight, held together by three scroll duties:

* **Enrage** on the taunter pair, alternating the boss's ``Focus`` taunt with
  ``TAUNT_{attempt}_{n}`` signals exactly like the other taunt cycles;
* **Decay**: the boss announces it with
  ``"I possess the full power of the Legion at my disposal."`` on the ``ct``
  packet; the holder of that cycle answers with the Scroll of Decay;
* **Mystify** on slot 4 (except Stable): the holder equips Mystify and keeps
  Decay as its fallback, publishing which mode the party is in.

On top of the scrolls, slots 3 and 4 run the **safe heal**: skill 2 once while
the pane carries no ``Noxious Decay`` aura -- the one window where a heal lands
instead of feeding the boss.

Roles per column (Pay2Win and Test are not ported):

===========  =================  ===============  ============  ==========
column       Enrage taunters    opening owner     Decay holder  Mystify
===========  =================  ===============  ============  ==========
Default      slots 1, 3         slot 1            slot 2        slot 4
Stable       slots 3, 4         slot 3            slot 2        --
Reliable     slots 1, 3         slot 1            slot 2        slot 4
===========  =================  ===============  ============  ==========

Every pane wears **Health Vamp** on the weapon and Vainglory on the cape, which
is the script's own override of the class presets.

``DrainZoneEvents`` is the reference's ``RunToArea`` subscription; without a
Flash event feed it becomes a cell check that walks back to ``Boss/Right``.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from bot.ultra.v2 import scrolls
from bot.ultra.v2.core import V2Core
from bot.ultra.v2.options import UltraOptions, UltraSpec
from bot.ultra.v2.packets import PacketDetector, ZoneWatcher

SPEC = UltraSpec(
    id="dage",
    title="Ultra Dage",
    quest=8547,
    prereq_quest=793,
    prereq_name="Fail to the King",
    min_level=80,
    map="ultradage",
    safe_cell="Enter",
    safe_pad="Spawn",
    boss_cell="Boss",
    boss_pad="Right",
    monster_id=1,                 # DageMapId
)

BOSS = "id.1"
ENRAGE = scrolls.ENRAGE
DECAY_SCROLL = "Scroll of Decay"
MYSTIFY_SCROLL = "Scroll of Mystify"

#: The boss's Decay announcement, verbatim from the script.
DECAY_MESSAGE = "I possess the full power of the Legion at my disposal."
NOXIOUS_DECAY = "Noxious Decay"
UNLEASHED_DOOM = "Unleashed Doom"
FOCUS = "Focus"
FOCUS_REFRESH_MS = 1500
STABLE = "Stable"

#: ``DrainZoneEvents`` walks to these spots inside the boss room.
ZONE_WALK_Y = 420
ZONE_WALK_X = {"A": 122, "B": 856}


class UltraDage(V2Core):
    """One pane of the Ultra Dage fight."""

    def __init__(self, cmd, options: UltraOptions, slot: int = 1):
        super().__init__(cmd, SPEC, options, slot)
        self.detector = PacketDetector(self.bot, "ct", DECAY_MESSAGE)
        #: ``StartZoneListener``: zone changes, drained every pass.
        self.zones = ZoneWatcher(self.bot)
        self.mystify_mode = False
        self.next_decay_cycle = 1
        self.safe_heal_used = False
        self._decay_logged = False
        # Reliable's Verus DoomKnight must not touch skill 2 while the boss's
        # Unleashed Doom aura is up (the reference's ``blockedStrictSkill``).
        if self.options.composition == "Reliable" and self.slot == 1:
            self.blocked_skill = 2
            self.blocked_aura = UNLEASHED_DOOM

    # ----------------------------------------------------------------- roles
    def is_taunter(self) -> bool:
        if self.options.composition == STABLE:
            return self.slot in (3, 4)
        return self.slot in (1, 3)

    def opening_owner(self) -> bool:
        return self.slot == (3 if self.options.composition == STABLE else 1)

    def partner_slot(self) -> int:
        if self.options.composition == STABLE:
            return 4 if self.opening_owner() else 3
        return 3 if self.opening_owner() else 1

    def is_decay_holder(self) -> bool:
        return self.slot == 2

    def is_mystify_holder(self) -> bool:
        return self.options.composition != STABLE and self.slot == 4

    def is_damage_dealer(self) -> bool:
        return self.options.composition == STABLE and self.slot == 1

    def is_safe_healer(self) -> bool:
        return self.slot in (3, 4)

    def uses_full_potions(self) -> bool:
        return self.options.composition == STABLE and self.slot == 1

    def taunt_signal(self, attempt: int, number: int) -> str:
        return f"TAUNT_{attempt}_{number}"

    @staticmethod
    def align_signal(number: int, sender_is_opening_owner: bool) -> int:
        signal_is_opening_owner = number % 2 != 0
        return (number if signal_is_opening_owner == sender_is_opening_owner
                else number + 1)

    def boss_alive(self) -> bool:
        return self.cmd.is_monster_alive(BOSS)

    # --------------------------------------------------------------- scrolls
    def prepare_scrolls(self) -> None:
        """``Prepare``: which scroll this pane stocks."""
        if self.is_taunter():
            self.scroll = ENRAGE
        elif self.is_decay_holder():
            self.scroll = DECAY_SCROLL
        elif self.is_mystify_holder():
            self.scroll = MYSTIFY_SCROLL

    async def equip_attempt_scroll(self, attempt: int) -> bool:
        """``PrepareSafeRoom``: equip this attempt's scroll and set the mode."""
        if self.is_taunter():
            await scrolls.equip(self.cmd, ENRAGE)
            return True
        if self.is_decay_holder():
            await scrolls.equip(self.cmd, DECAY_SCROLL)
            return True
        if not self.is_mystify_holder():
            return True

        equipped = await scrolls.equip(self.cmd, MYSTIFY_SCROLL)
        self.mystify_mode = bool(equipped)
        if not self.mystify_mode:
            await scrolls.equip(self.cmd, DECAY_SCROLL)

        name = (f"MYSTIFY_{attempt}" if self.mystify_mode
                else f"ALTERNATING_DECAY_{attempt}")
        self.sync.signal(name, True)
        self.log(f"selected {'Mystify' if self.mystify_mode else 'alternating Decay'} mode.")
        return True

    async def resolve_scroll_mode(self, attempt: int) -> bool:
        """The barrier, then Default's non-slot-4 panes read slot 4's mode."""
        if not await self.require_step(f"SCROLL_MODE_{attempt}"):
            return False
        if self.options.composition == "Default" and self.slot != 4:
            self.mystify_mode = bool(
                self.sync.read(f"MYSTIFY_{attempt}").get(4))
        return True

    # ------------------------------------------------------------- the fight
    async def run(self) -> bool:
        if not await self.require_step("PREFLIGHT"):
            return False
        if not await self.validate_access():
            return False
        self.log(f"started as {self.alias}: {self.describe()}")

        await self.join()
        if not await self.accept_quest():
            return False
        self.prepare_scrolls()
        if not await self.prepare(scroll=getattr(self, "scroll", None),
                                  drop_combat_potion=not self.uses_full_potions()):
            return False
        if not await self.require_step("SETUP_DONE"):
            return False

        if not await self.defeat_and_turn_in():
            return False
        if not await self.sync.step("BOSS_DEFEATED"):
            return False
        if not await self.sync.step("FINISH"):
            return False

        if self.slot == 1:
            self.sync.signal("COMPLETE", True)
        self.log("finished.")
        return True

    async def fight_attempts(self) -> bool:
        retries = max(1, int(self.options.retries))
        attempts = retries + 1
        for attempt in range(1, attempts + 1):
            await self.join()
            await self.use_potions(
                drop_combat_potion=not self.uses_full_potions())
            if not await self.equip_attempt_scroll(attempt):
                return False
            if not await self.resolve_scroll_mode(attempt):
                return False
            if not self.start_decay_detector():
                return False
            if not self.start_zone_listener():
                return False
            if not await self.require_step("FIGHT_READY"):
                return False

            await self.jump_boss()
            # ``StartSkillEngine`` in the reference's ``StartFightSystems``:
            # without this the pane walked in and stood there.
            await self.start_skills(BOSS, taunter=self.is_taunter())
            self.target_priority = (BOSS,)
            self.begin_attempt(attempt)
            try:
                result = await self.fight(attempt)
            finally:
                self.detector.stop()
                self.zones.stop()
            if result == "defeated":
                await self.cmd.jump_cell(self.spec.safe_cell, self.spec.safe_pad)
                self.log("confirmed Ultra Dage defeated.")
                return True
            if result == "stopped":
                return False
            if result == "reset":
                if not await self.handle_reset(attempt):
                    return False
                await self.use_potions(
                    drop_combat_potion=not self.uses_full_potions())

            if attempt >= attempts:
                self.log(f"failed after {attempts} fight attempt(s).")
                if self.slot == 1:
                    self.sync.stop("ATTEMPTS_EXHAUSTED")
                return self.abort(f"the party wiped {retries} time(s)")
        return False

    def start_decay_detector(self) -> bool:
        """``StartDecayDetector``: the panes that answer Decay watch for it."""
        watches = (self.is_decay_holder()
                   or (self.options.composition == "Default"
                       and self.slot == 4 and not self.mystify_mode))
        if not watches:
            return True
        return self.detector.start()

    async def fight(self, attempt: int) -> str:
        """``Fight``: taunter, damage dealer, or scroll holder."""
        if self.is_taunter():
            return await self.fight_enrage_taunter(attempt)
        if self.is_damage_dealer():
            return await self.fight_damage_dealer(attempt)
        return await self.fight_scroll_holder(attempt)

    def fight_result(self, attempt: int, boss_observed: bool) -> str:
        """``GetFightResult``: the boss was seen and is gone -> defeated."""
        if self.boss_alive():
            return "continue"
        if boss_observed:
            return "defeated"
        if self.should_reset(attempt):
            return "reset"
        return "continue"

    async def recover(self, attempt: int) -> str:
        """``RecoverFromDeath``: respawn, walk back in, keep going."""
        if not self.bot.player.ISDEAD:
            return "continue"
        self.note_death()
        await self.drain_zone_events(move=False)
        state = await self.wait_respawn(attempt)
        if state in ("reset", "stopped"):
            return state
        if not self.boss_alive() and self._boss_seen:
            return "defeated"
        if not self.in_boss_room():
            await self.jump_boss()
        return "continue"

    async def fight_damage_dealer(self, attempt: int) -> str:
        self._boss_seen = self.boss_alive()
        self.log("started fighting.")
        while self.cmd.is_still_connected() and not self.sync.aborted():
            result = self.fight_result(attempt, self._boss_seen)
            if result != "continue":
                return await self.finish_fight(result)
            result = await self.recover(attempt)
            if result != "continue":
                return await self.finish_fight(result)
            self._boss_seen = self._boss_seen or self.boss_alive()
            await self.drain_zone_events()
            self.target_priority = (BOSS,)
            await self.cmd.sleep(self.poll_ms)
        return await self.finish_fight("stopped")

    async def fight_enrage_taunter(self, attempt: int) -> str:
        """``FightEnrageTaunter``: alternate the Focus taunt with its partner."""
        self._boss_seen = self.boss_alive()
        partner = self.partner_slot()
        opening_owner = self.opening_owner()
        owns_focus = False
        waiting_for_focus = opening_owner
        partner_death_seen = False
        signal_number = 1
        focus_baseline = self.target_aura_expiry(FOCUS, BOSS) or datetime.min

        if opening_owner:
            self.request_taunt(BOSS)
            self.log("requested the first Dage taunt.")
        self.log("started fighting.")

        while self.cmd.is_still_connected() and not self.sync.aborted():
            result = self.fight_result(attempt, self._boss_seen)
            if result != "continue":
                return await self.finish_fight(result)
            was_dead = self.bot.player.ISDEAD
            result = await self.recover(attempt)
            if result != "continue":
                return await self.finish_fight(result)
            if was_dead and self.is_safe_healer():
                self.safe_heal_used = True
            self._boss_seen = self._boss_seen or self.boss_alive()

            await self.drain_zone_events()
            self.target_priority = (BOSS,)
            if self.is_safe_healer():
                await self.handle_safe_heal()

            if was_dead:
                signal_number = self.align_signal(signal_number, opening_owner)
                owns_focus = False
                waiting_for_focus = True
                focus_baseline = self.target_aura_expiry(FOCUS, BOSS) or datetime.min
                self.request_taunt(BOSS)
                self.log("owns the next Dage taunt after returning.")

            state = self.partner_state(partner)
            if state is not None:
                partner_dead, partner_in_room = state
                if partner_dead and not partner_death_seen:
                    signal = self.taunt_signal(attempt, signal_number)
                    if (not owns_focus and not waiting_for_focus
                            and self.sync.read(signal).get(partner)):
                        signal_number += 1
                    partner_death_seen = True
                    owns_focus = False
                    waiting_for_focus = False
                    self.log("detected its taunt partner died.")
                if partner_death_seen:
                    if not partner_dead and partner_in_room:
                        partner_death_seen = False
                        signal_number = self.align_signal(signal_number,
                                                          not opening_owner)
                        owns_focus = False
                        waiting_for_focus = False
                        self.log("restored alternating Dage taunts.")
                    else:
                        self.request_taunt(BOSS)
                        await self.cmd.sleep(self.poll_ms)
                        continue

            focus = self.target_aura_expiry(FOCUS, BOSS)
            if (waiting_for_focus and focus is not None
                    and focus > focus_baseline):
                focus_baseline = focus
                waiting_for_focus = False
                owns_focus = True
                self.log("confirmed its Focus and owns the taunt cycle.")

            if waiting_for_focus:
                if focus is None:
                    self.request_taunt(BOSS)
            elif owns_focus and focus is None:
                owns_focus = False
                waiting_for_focus = True
                focus_baseline = datetime.min
                self.request_taunt(BOSS)
            elif (owns_focus and focus is not None
                  and focus - datetime.now()
                  <= timedelta(milliseconds=FOCUS_REFRESH_MS)):
                signal = self.taunt_signal(attempt, signal_number)
                self.sync.signal(signal, True)
                self.log(f"sent {signal} to player{partner}.")
                signal_number += 1
                owns_focus = False
            elif not owns_focus and not waiting_for_focus:
                signal = self.taunt_signal(attempt, signal_number)
                if self.sync.read(signal).get(partner):
                    signal_number += 1
                    focus_baseline = self.target_aura_expiry(FOCUS, BOSS) or datetime.min
                    waiting_for_focus = True
                    self.request_taunt(BOSS)
                    self.log(f"received {signal} and requested its scheduled "
                             f"Dage taunt.")

            await self.cmd.sleep(self.poll_ms)
        return await self.finish_fight("stopped")

    async def fight_scroll_holder(self, attempt: int) -> str:
        """``FightScrollHolder``: safe heal, Mystify, and the Decay answers."""
        self._boss_seen = self.boss_alive()
        self.log("started fighting.")
        while self.cmd.is_still_connected() and not self.sync.aborted():
            result = self.fight_result(attempt, self._boss_seen)
            if result != "continue":
                return await self.finish_fight(result)
            was_dead = self.bot.player.ISDEAD
            result = await self.recover(attempt)
            if result != "continue":
                return await self.finish_fight(result)
            if was_dead:
                self.safe_heal_used = True
            self._boss_seen = self._boss_seen or self.boss_alive()

            await self.drain_zone_events()
            self.target_priority = (BOSS,)
            if self.is_safe_healer():
                await self.handle_safe_heal()

            if self.is_mystify_holder() and self.mystify_mode:
                self.request_taunt(BOSS)      # ``RequestImmediateSkillFive``

            self.handle_decay_detections()
            await self.cmd.sleep(self.poll_ms)
        return await self.finish_fight("stopped")

    # --------------------------------------------------------------- helpers
    def handle_decay_detections(self) -> None:
        """``HandleDecayDetections``: answer the cycles this pane owns."""
        while self.detector.seen(self.next_decay_cycle):
            if not self._decay_logged:
                self.log("detected Decay in ct packets.")
                self._decay_logged = True
            cycle = self.next_decay_cycle
            self.next_decay_cycle += 1

            owns = ((self.slot == 2 and (self.options.composition == STABLE
                                         or self.mystify_mode
                                         or cycle % 2 != 0))
                    or (self.slot == 4
                        and self.options.composition == "Default"
                        and not self.mystify_mode and cycle % 2 == 0))
            if not owns:
                continue
            self.request_taunt(BOSS)
            self.log(f"requested Decay for cycle {cycle}.")

    async def handle_safe_heal(self) -> bool:
        """``HandleSafeHeal``: one heal in the window without ``Noxious Decay``."""
        if self.self_aura(NOXIOUS_DECAY) is not None:
            self.safe_heal_used = False
            return False
        if self.safe_heal_used or self.bot.player.ISDEAD:
            return False
        if not self.boss_alive():
            return False
        if not self.bot.player.canUseSkill(2):
            return False
        healed = bool(await self.cmd.use_skill(2))
        if healed:
            self.safe_heal_used = True
            self.log("used its safe-window heal.")
        return healed

    def start_zone_listener(self) -> bool:
        """``StartZoneListener``: arm the zone listener for this attempt."""
        if not self.zones.start():
            self.abort("the zone listener could not start")
            return False
        return True

    async def drain_zone_events(self, move: bool = True) -> None:
        """``DrainZoneEvents``: walk to the spot each zone letter names.

        The reference walks, never jumps: zone "A" is 122, zone "B" is 856 and
        the middle is 500, all on y=420 inside the boss room.
        """
        while True:
            drained = self.zones.drain()
            if not drained:
                return
            for zone in drained:
                if not move or self.bot.player.ISDEAD:
                    continue
                x = {"A": 122, "B": 856}.get(zone, 500)
                await self.cmd.walk_to(x, ZONE_WALK_Y)
                self.log(f"walked to zone {zone or 'middle'} ({x}, "
                         f"{ZONE_WALK_Y}).")

    def partner_state(self, slot: int):
        """``TryGetPartnerState``: ``(dead, in_boss_room)`` or None."""
        try:
            name = str(self.options.players[slot - 1]).lower()
        except Exception:
            return None
        for player in getattr(self.bot, "player_in_area", []) or []:
            if str(getattr(player, "str_username", "")).lower() != name:
                continue
            dead = int(getattr(player, "int_state", 0) or 0) == 0
            in_room = (not dead
                       and str(getattr(player, "str_frame", "")).lower()
                       == self.spec.boss_cell.lower())
            return dead, in_room
        return None

    async def finish_fight(self, result: str) -> str:
        await self.stop_skills()
        if not self.cmd.is_still_connected() or self.sync.aborted():
            return "stopped"
        return result

    _boss_seen = False


async def main(cmd, slot: int = 1, options: Optional[UltraOptions] = None) -> None:
    """Run one pane standalone (``python -m bot.ultra.v2.weeklies.dage``)."""
    runner = UltraDage(cmd, options or UltraOptions(), slot)
    okay = await runner.run()
    if not okay and runner.aborted:
        cmd.bot.log(f"[V2 Dage] slot {slot} stopped: {runner.aborted}")
