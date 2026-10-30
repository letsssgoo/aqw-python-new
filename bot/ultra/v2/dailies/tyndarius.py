"""Ultra Tyndarius -- full port of ``Dailies/UltraTyndarius_LW.cs``.

Everything the script does, in its own order:

* ``Prepare`` / ``PrepareSafeRoom`` -- class, enhancements, potions; a taunter
  stocks the Scroll of Enrage and loses its combat potion (slot 5 is the
  scroll); potions and prebuff in the safe room.
* ``PrepareRighteousSeal`` + signal -- the ArchPaladin pane (slot 3) seals the
  boss with skill 3 and publishes ``RIGHTEOUS_n``; the others wait for it.
* ``RunFightAttempts`` dispatch, verbatim:
  ArchPaladin -> ``FightBossTaunter``; its partner (slot 4) -> the same;
  otherwise the default branch -> ``FightAddTaunter`` with
  ``tauntMapId = slot 1 ? FirstAdd : SecondAdd``.
* ``FightBossTaunter`` -- the alternating Focus/taunt cycle between the
  ArchPaladin and its partner, with ``TAUNT_{attempt}_{n}`` signals and the
  partner-death takeover.
* ``GetPriorityTarget`` -- SecondAdd (id.3) -> FirstAdd (id.1) -> MainBoss (id.2).
* ``RecoverFromDeath`` -- a death is walked off and the fight continues; only a
  whole-party wipe resets, and a reset retries from potions + prebuff.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from bot.ultra.v2 import scrolls
from bot.ultra.v2.core import V2Core
from bot.ultra.v2.options import UltraOptions, UltraSpec

SPEC = UltraSpec(
    id="tyndarius",
    title="Ultra Tyndarius",
    quest=8245,
    prereq_quest=8243,
    prereq_name="Avatar of Fire",
    min_level=61,
    map="ultratyndarius",
    safe_cell="Enter",
    safe_pad="Spawn",
    boss_cell="Boss",
    boss_pad="Left",
    monster_id=2,                 # MainBossMapId
)

FIRST_ADD = 1
MAIN_BOSS = 2
SECOND_ADD = 3
BOSS = "id.2"
RIGHTEOUS_SEAL = "Righteous Seal"
FOCUS = "Focus"
HEAL_BELOW = 60
ARCH_PALADIN_SLOT = 3
TAUNT_PARTNER_SLOT = 4            # Pay2Win would use 3; not ported
FOCUS_REFRESH_MS = 1500


def _id(map_id: int) -> str:
    return f"id.{map_id}"


class UltraTyndarius(V2Core):
    """One pane of the Tyndarius fight."""

    def __init__(self, cmd, options: UltraOptions, slot: int = 1):
        super().__init__(cmd, SPEC, options, slot)
        self.skill_rotation = (0, 1, 2, 0, 3, 4)
        self.heal_below = HEAL_BELOW
        # Every pane tops the party up below 60%, not just slots 3 and 4.
        self.heal_slots = ()
        if self.preset.cls == "Lord of Order":
            # LoO is the dedicated healer here: heal on cooldown, no HP gate
            # and no gap between heals.
            self.spam_heal = True
            self.heal_gap_ms = 0
        elif self.preset.cls == "ArchPaladin":
            # AP keeps skill 2 for the emergency heal (below 60%, with a gap),
            # so it is taken out of the rotation -- otherwise the rotation
            # itself casts it and it is not "held" at all.
            self.heal_gap_ms = 1500
            self.skill_rotation = tuple(
                slot for slot in self.skill_rotation if slot != self.heal_skill)
        self.is_taunter = self.slot >= 3          # IsTaunterRole
        self.is_arch_paladin = self.slot == ARCH_PALADIN_SLOT

    # ---------------------------------------------------------------- targets
    def priority_target(self) -> str:
        """``GetPriorityTarget``: second add, then first add, then the boss."""
        for map_id in (SECOND_ADD, FIRST_ADD, MAIN_BOSS):
            if self.cmd.is_monster_alive(_id(map_id)):
                return _id(map_id)
        return _id(MAIN_BOSS)

    def boss_alive(self) -> bool:
        return self.cmd.is_monster_alive(_id(MAIN_BOSS))

    # ------------------------------------------------------------ death logic
    async def recover(self, attempt: int) -> str:
        """``RecoverFromDeath``: ``continue``, ``defeated``, ``reset``, ``stopped``.

        Death is handled **first**: checking "is the boss alive" first returned
        ``continue`` for a dead pane whose boss still stood, so wait_respawn was
        never reached -- and the skill loop (which exits on death) was never
        restarted.  That is the pane that stood in the cell doing nothing.
        """
        if self.bot.player.ISDEAD:
            self.note_death()
            state = await self.wait_respawn(attempt)
            if state == "reset":
                return "reset"
            if state == "stopped":
                return "stopped"
        if self.boss_alive():
            if self.should_reset(attempt):
                return "reset"
            return "continue"
        if self.cmd.can_turnin_quest(self.spec.quest):
            return "defeated"
        if not self.boss_alive():
            if self.cmd.can_turnin_quest(self.spec.quest):
                return "defeated"
            await self.cmd.sleep(500)
        if not self.in_boss_room():
            await self.jump_boss()
        return "continue"

    # ---------------------------------------------------------------- setup
    async def righteous_seal(self) -> bool:
        """``PrepareRighteousSeal``: cast 3 until the boss carries the seal."""
        self.log("starting Righteous Seal preparation.")
        while self.cmd.is_still_connected() and not self.sync.aborted():
            if self.bot.player.ISDEAD:
                state = await self.wait_respawn(1)
                if state == "stopped":
                    return False
            if not self.in_boss_room():
                await self.jump_boss()
            if not self.boss_alive():
                return True
            if self.target_aura(RIGHTEOUS_SEAL):
                self.log("confirmed Righteous Seal.")
                return True
            if self.bot.player.canUseSkill(3):
                await self.cmd.use_skill(3, target_monsters=_id(MAIN_BOSS))
            await self.cmd.sleep(self.poll_ms)
        return False

    # ------------------------------------------------------------------- flow
    async def run(self) -> bool:
        if not await self.require_step("PREFLIGHT"):
            return False
        if not await self.validate_access():
            return False
        self.log(f"started as {self.alias}: {self.describe()}")

        await self.join()
        if not await self.accept_quest():
            return False
        if not await self.prepare(scroll=scrolls.ENRAGE if self.is_taunter
                                  else None,
                                  drop_combat_potion=self.is_taunter):
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
            await self.use_potions(drop_combat_potion=self.is_taunter)
            if self.is_taunter:
                await scrolls.equip(self.cmd, scrolls.ENRAGE)
            if not await self.require_step("FIGHT_READY"):
                return False

            seal_signal = f"RIGHTEOUS_{attempt}"
            if self.is_arch_paladin:
                if not await self.righteous_seal():
                    return False
                self.sync.signal(seal_signal, True)
                await self.jump_boss()
            else:
                if not await self.sync.wait_signal(seal_signal,
                                                   key=ARCH_PALADIN_SLOT,
                                                   timeout=180):
                    if self.sync.aborted():
                        return False
                    return self.abort("the Righteous Seal signal never came")
                await self.jump_boss()
            # Nobody fights from the safe cell: prove every pane stands in
            # Boss/Left before the party moves on.
            if not await self.ensure_boss_room():
                return False
            if not await self.require_step("BOSS_ROOM"):
                return False
            await self.precast_buffs()
            if not await self.require_step("BUFFS_DONE"):
                return False

            self.begin_attempt(attempt)
            result = await self.fight(attempt)
            if result == "defeated":
                return True
            if result == "stopped":
                return False
            if result == "reset":
                if not await self.handle_reset(attempt):
                    return False
                await self.use_potions(drop_combat_potion=self.is_taunter)
                if self.is_taunter:
                    await scrolls.equip(self.cmd, scrolls.ENRAGE)

            if attempt >= attempts:
                self.log(f"failed after {attempts} fight attempt(s).")
                if self.slot == 1:
                    self.sync.stop("ATTEMPTS_EXHAUSTED")
                return self.abort(f"the party wiped {retries} time(s)")
        return False

    async def fight(self, attempt: int) -> str:
        """The dispatch of ``Fight`` without the Pay2Win/Test columns."""
        if self.is_arch_paladin:
            return await self.fight_boss_taunter(attempt, True,
                                                TAUNT_PARTNER_SLOT)
        if self.slot == TAUNT_PARTNER_SLOT:
            return await self.fight_boss_taunter(attempt, False,
                                                ARCH_PALADIN_SLOT)
        # Default roles: slot 1 taunts the first add, the rest the second one.
        taunt_map = FIRST_ADD if self.slot == 1 else SECOND_ADD
        return await self.fight_add_taunter(attempt, taunt_map)

    # ------------------------------------------------------------- branches
    async def fight_add_taunter(self, attempt: int, taunt_map: int) -> str:
        """``FightAddTaunter``: taunt the add, otherwise stay on priority."""
        await self.start_skills(_id(MAIN_BOSS), taunter=True)
        self.log("started fighting.")

        while self.cmd.is_still_connected() and not self.sync.aborted():
            state = await self.recover(attempt)
            if state == "defeated":
                break
            if state == "reset":
                await self.stop_skills()
                return "reset"
            if state == "stopped":
                await self.stop_skills()
                return "stopped"

            taunted = False
            if self.cmd.is_monster_alive(_id(taunt_map)):
                taunted = await self.immediate_taunt(_id(taunt_map))
            if not taunted:
                await self.maintain_target(self.priority_target())
            await self.cmd.sleep(self.poll_ms)

        await self.stop_skills()
        if not self.cmd.is_still_connected() or self.sync.aborted():
            return "stopped"
        self.log("confirmed Ultra Tyndarius defeated.")
        return "defeated"

    async def fight_boss_taunter(self, attempt: int, is_arch_paladin: bool,
                                 partner_slot: int) -> str:
        """``FightBossTaunter``: alternating Focus/taunt cycle with its partner."""
        await self.start_skills(_id(MAIN_BOSS), taunter=True)
        self.log("started fighting.")

        owns_focus = False
        waiting_for_focus = is_arch_paladin
        partner_death_seen = False
        signal_number = 1
        focus_baseline = self.target_aura_expiry(FOCUS)
        if is_arch_paladin:
            self.request_taunt(_id(MAIN_BOSS))
            self.log("requested the first boss taunt.")

        while self.cmd.is_still_connected() and not self.sync.aborted():
            was_dead = self.bot.player.ISDEAD
            state = await self.recover(attempt)
            if state == "defeated":
                break
            if state == "reset":
                await self.stop_skills()
                return "reset"
            if state == "stopped":
                await self.stop_skills()
                return "stopped"
            if was_dead:
                # Back from the dead: take the next scheduled taunt.
                signal_number = self.align_signal(signal_number, is_arch_paladin)
                owns_focus = False
                waiting_for_focus = True
                focus_baseline = self.target_aura_expiry(FOCUS)
                self.request_taunt(_id(MAIN_BOSS))

            await self.maintain_target(_id(MAIN_BOSS))

            partner_dead = self.partner_is_dead(partner_slot)
            if partner_dead and not partner_death_seen:
                signal = self.taunt_signal(attempt, signal_number)
                if (not owns_focus and not waiting_for_focus
                        and self.sync.read(signal).get(partner_slot)):
                    signal_number += 1
                partner_death_seen = True
                owns_focus = False
                waiting_for_focus = False
                self.log("detected its taunt partner died.")

            if partner_death_seen:
                if not partner_dead:
                    partner_death_seen = False
                    signal_number = self.align_signal(signal_number,
                                                      not is_arch_paladin)
                    owns_focus = False
                    waiting_for_focus = False
                    self.log("restored alternating boss taunts.")
                else:
                    self.request_taunt(_id(MAIN_BOSS))
                    await self.cmd.sleep(self.poll_ms)
                    continue

            focus = self.target_aura_expiry(FOCUS)
            if (waiting_for_focus and focus is not None
                    and (focus_baseline is None or focus > focus_baseline)):
                focus_baseline = focus
                waiting_for_focus = False
                owns_focus = True
                self.log("confirmed its Focus and owns the taunt cycle.")

            if waiting_for_focus:
                if focus is None:
                    self.request_taunt(_id(MAIN_BOSS))
            elif owns_focus and focus is None:
                owns_focus = False
                waiting_for_focus = True
                focus_baseline = None
                self.request_taunt(_id(MAIN_BOSS))
            elif (owns_focus and focus is not None
                  and focus - datetime.now()
                  <= timedelta(milliseconds=FOCUS_REFRESH_MS)):
                signal = self.taunt_signal(attempt, signal_number)
                self.sync.signal(signal, True)
                self.log(f"sent {signal} to player{partner_slot}.")
                signal_number += 1
                owns_focus = False
            elif not owns_focus and not waiting_for_focus:
                signal = self.taunt_signal(attempt, signal_number)
                if self.sync.read(signal).get(partner_slot):
                    signal_number += 1
                    focus_baseline = self.target_aura_expiry(FOCUS)
                    waiting_for_focus = True
                    self.request_taunt(_id(MAIN_BOSS))
                    self.log(f"received {signal} and requested its scheduled "
                             f"boss taunt.")

            await self.cmd.sleep(self.poll_ms)

        await self.stop_skills()
        if not self.cmd.is_still_connected() or self.sync.aborted():
            return "stopped"
        self.log("confirmed Ultra Tyndarius defeated.")
        return "defeated"

    async def ensure_boss_room(self) -> bool:
        """Move into ``Boss/Left`` and wait until the pane is really there."""
        waited = 0
        while self.cmd.is_still_connected() and not self.sync.aborted():
            if self.bot.player.ISDEAD:
                # A dead pane cannot stand in the room; wait it out (attempt 0
                # keeps the wipe detector out of this wait).
                if await self.wait_respawn(0) == "stopped":
                    return False
                continue
            if self.in_boss_room():
                return True
            await self.jump_boss()
            await self.cmd.sleep(500)
            waited += 500
            if waited >= 20_000:
                self.abort("could not reach Boss/Left; the party would fight "
                           "a pane short")
                return False
        return False

    # ------------------------------------------------------------- helpers
    def taunt_signal(self, attempt: int, number: int) -> str:
        return f"TAUNT_{attempt}_{number}"

    @staticmethod
    def align_signal(number: int, sender_is_arch_paladin: bool) -> int:
        """``AlignSignalNumber``: odd signals belong to the ArchPaladin."""
        signal_is_arch_paladin = number % 2 != 0
        return number if signal_is_arch_paladin == sender_is_arch_paladin \
            else number + 1

    def partner_is_dead(self, slot: int) -> bool:
        from bot.ultra import party
        if not self.sync.enabled:
            return False
        return slot in party.death_times(self.sync.name, (slot,))

    async def immediate_taunt(self, target: str) -> bool:
        """``RequestImmediateTaunt``: taunt now, and say whether it went out.

        LW returns false when the taunt cannot be cast (skill 5 not ready), and
        only then does the caller fall back to ``MaintainTarget``.  A successful
        taunt also leaves the pane's target on that monster, which is why the
        rotation follows it here.
        """
        if not self.cmd.is_monster_alive(target):
            return False
        if not self.bot.player.canUseSkill(5):
            return False
        self.request_taunt(target)
        self.target_priority = (target,)
        return True

    async def maintain_target(self, target: str) -> None:
        """``MaintainTarget``: keep the rotation aimed at ``target``."""
        self.target_priority = (target,)


async def main(cmd, slot: int = 1, options: Optional[UltraOptions] = None) -> None:
    """Run one pane standalone (``python -m bot.ultra.v2.dailies.tyndarius``)."""
    runner = UltraTyndarius(cmd, options or UltraOptions(), slot)
    okay = await runner.run()
    if not okay and runner.aborted:
        cmd.bot.log(f"[V2 Tyndarius] slot {slot} stopped: {runner.aborted}")
