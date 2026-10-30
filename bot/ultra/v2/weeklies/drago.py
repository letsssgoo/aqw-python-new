"""Ultra King Drago -- port of ``UltraDrago_LW.cs``.

Three monsters: **Dene** (``id.1``), Drago (``id.2``) and **Algie** (``id.3``).
Drago only becomes the target once both guards are down; until then each pane
holds its assigned guard.

The shape, from the reference:

* **default / reliable** -- every pane runs the *guard pair* cycle: slots 1 and 4
  hold Algie while 2 and 3 hold Dene, and each pair alternates the guard **Focus**
  taunt between its two panes (``ALGIE_TAUNT_`` / ``DENIE_TAUNT_`` signals, the
  same odd/even alignment Tyndarius uses);
* **stable** -- slot 1 is a plain damage dealer, slot 4 taunts Algie immediately
  and slot 2/3 keep the guard pair.  Optimized is not a column here;
* the pull is **counted down**, not waited on: slot 1 publishes
  ``DRAGO_ENTRY_TIME_{attempt}`` two seconds in the future and every pane starts
  its skill engine first, then walks in on that timestamp together.

``AggressiveMoveToBossRoom`` uses the reference's Flash jump first; this engine
has no Flash, so it is the map jump plus a wait until the pane really stands in
``Boss/Left`` (the fallback branch the reference also keeps).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Tuple

from bot.ultra.v2 import scrolls
from bot.ultra.v2.core import V2Core
from bot.ultra.v2.options import UltraOptions, UltraSpec

SPEC = UltraSpec(
    id="drago",
    title="Ultra Drago",
    quest=8397,
    prereq_quest=8395,
    prereq_name="Mahapadma",
    min_level=80,
    map="ultradrago",
    safe_cell="Enter",
    safe_pad="Spawn",
    boss_cell="Boss",
    boss_pad="Left",
    monster_id=2,                 # DragoMapId
)

DENE = "id.1"
DRAGO = "id.2"
ALGIE = "id.3"
ENRAGE = scrolls.ENRAGE
FOCUS = "Focus"

#: The coordinated pull: slot 1 publishes a timestamp two seconds ahead.
ENTRY_LEAD_MS = 2000
ENTRY_TIMEOUT_MS = 5000
FOCUS_REFRESH_MS = 1500
TARGET_SETTLE_MS = 50

#: ``Stable`` is the only ported column with separate roles; Default and
#: Reliable run the guard pair on every pane.
STABLE = "Stable"

ALGIE_TAUNT = "ALGIE_TAUNT_"
DENE_TAUNT = "DENIE_TAUNT_"


def _id(map_id: int) -> str:
    return f"id.{map_id}"


class UltraDrago(V2Core):
    """One pane of the King Drago fight."""

    def __init__(self, cmd, options: UltraOptions, slot: int = 1):
        super().__init__(cmd, SPEC, options, slot)
        # ``isTaunter``: everyone on Default/Reliable (they all carry the
        # scroll), slots 2-4 on Stable.
        self.is_taunter = (self.options.composition != STABLE
                           or self.slot != 1)

    # ----------------------------------------------------------------- roles
    def guard_map_id(self) -> str:
        """``GetAssignedGuardMapId``: slots 1 and 4 hold Algie."""
        return ALGIE if self.slot in (1, 4) else DENE

    def partner_slot(self) -> int:
        """``GetPartnerPlayerNumber``: 1 <-> 4 and 2 <-> 3."""
        return {1: 4, 4: 1, 3: 2, 2: 3}[self.slot]

    def is_opening_owner(self) -> bool:
        """``IsOpeningOwner``: slots 1 and 3 take the first taunt."""
        return self.slot in (1, 3)

    def signal_prefix(self) -> str:
        return ALGIE_TAUNT if self.slot in (1, 4) else DENE_TAUNT

    def taunt_signal(self, attempt: int, number: int) -> str:
        return f"{self.signal_prefix()}{attempt}_{number}"

    @staticmethod
    def align_signal(number: int, sender_is_opening_owner: bool) -> int:
        """``AlignSignalNumber``: odd signals belong to the opening owner."""
        signal_is_opening_owner = number % 2 != 0
        return (number if signal_is_opening_owner == sender_is_opening_owner
                else number + 1)

    # --------------------------------------------------------------- targets
    def initial_target(self) -> str:
        """``GetInitialTarget``: the ArchPaladin opens Dene, everyone else Algie."""
        if self.slot == 3 or (self.options.composition == STABLE
                              and self.slot == 2):
            return DENE
        return ALGIE

    def normal_target(self) -> str:
        """``GetNormalTarget``: a guard while one stands, else Drago."""
        algie = self.cmd.is_monster_alive(ALGIE)
        dene = self.cmd.is_monster_alive(DENE)
        if algie and dene:
            if self.options.composition == STABLE:
                return ALGIE if self.slot in (1, 4) else DENE
            return DENE if self.slot == 3 else ALGIE
        if algie:
            return ALGIE
        if dene:
            return DENE
        return DRAGO

    def boss_alive(self) -> bool:
        return self.cmd.is_monster_alive(DRAGO)

    # ----------------------------------------------------------------- entry
    def publish_entry_time(self, attempt: int) -> int:
        """Slot 1 stamps the pull time; returns it (0 when not slot 1)."""
        if self.slot != 1:
            return 0
        stamp = int((datetime.now()
                     + timedelta(milliseconds=ENTRY_LEAD_MS)).timestamp() * 1000)
        self.sync.signal(f"DRAGO_ENTRY_TIME_{attempt}", stamp)
        self.log("published the entry timestamp.")
        return stamp

    async def entry_time(self, attempt: int) -> int:
        """``GetEntryTimestamp``: slot 1 stamps it, the rest read it."""
        if self.slot == 1:
            return self.publish_entry_time(attempt)
        name = f"DRAGO_ENTRY_TIME_{attempt}"
        while self.cmd.is_still_connected() and not self.sync.aborted():
            stamp = int(self.sync.read(name).get(1) or 0)
            if stamp > 0:
                self.log("received the entry timestamp.")
                return stamp
            await self.cmd.sleep(self.poll_ms)
        return 0

    async def wait_entry_time(self, stamp: int) -> bool:
        """``WaitForEntryTimestamp``: hold the pull until the party's clock."""
        while self.cmd.is_still_connected() and not self.sync.aborted():
            remaining = stamp - int(datetime.now().timestamp() * 1000)
            if remaining <= 0:
                return True
            await self.cmd.sleep(min(remaining, TARGET_SETTLE_MS))
        return False

    async def aggressive_move(self, target: str) -> bool:
        """``AggressiveMoveToBossRoom``: jump in and prove we are inside."""
        if self.in_boss_room():
            return True
        self.target_priority = (target,)
        await self.jump_boss()
        if await self.wait_boss_room(target):
            return True
        await self.jump_boss()
        if await self.wait_boss_room(target):
            return True
        self.abort("could not enter the boss room; the party would fight a "
                   "pane short")
        return False

    async def wait_boss_room(self, target: str) -> bool:
        deadline = datetime.now() + timedelta(milliseconds=ENTRY_TIMEOUT_MS)
        while (self.cmd.is_still_connected()
               and datetime.now() < deadline):
            if self.in_boss_room():
                return True
            self.target_priority = (target,)
            await self.cmd.sleep(self.poll_ms)
        return self.in_boss_room()

    # ------------------------------------------------------------------ flow
    async def run(self) -> bool:
        if not await self.require_step("PREFLIGHT"):
            return False
        if not await self.validate_access():
            return False
        self.log(f"started as {self.alias}: {self.describe()}")

        await self.join()
        if not await self.accept_quest():
            return False
        if not await self.prepare(scroll=ENRAGE if self.is_taunter else None,
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
                await scrolls.equip(self.cmd, ENRAGE)
            if not await self.require_step("FIGHT_READY"):
                return False
            # ``GenericPrebuff`` runs after the barrier here, before the clock.
            await self.precast_buffs()
            stamp = await self.entry_time(attempt)
            if stamp <= 0:
                return False

            initial = self.initial_target()
            self.target_priority = (initial,)
            await self.start_skills(initial, taunter=self.is_taunter)

            if not await self.wait_entry_time(stamp):
                return False
            if not await self.aggressive_move(initial):
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
                    await scrolls.equip(self.cmd, ENRAGE)

            if attempt >= attempts:
                self.log(f"failed after {attempts} fight attempt(s).")
                if self.slot == 1:
                    self.sync.stop("ATTEMPTS_EXHAUSTED")
                return self.abort(f"the party wiped {retries} time(s)")
        return False

    async def fight(self, attempt: int) -> str:
        """``Fight``: Stable splits the roles, the other columns all guard."""
        if self.options.composition == STABLE:
            if self.slot == 1:
                return await self.fight_damage_dealer(attempt)
            if self.slot == 4:
                return await self.fight_immediate_algie_taunter(attempt)
        return await self.fight_guard_pair(attempt)

    # -------------------------------------------------------------- branches
    def fight_result(self, attempt: int) -> str:
        """``GetFightResult``: Drago down ends the fight, a wipe resets it."""
        if not self.boss_alive():
            return "defeated"
        if self.should_reset(attempt):
            return "reset"
        return "continue"

    async def recover(self, attempt: int) -> Tuple[str, bool]:
        """``RecoverFromDeath``: ``(result, recovered)``."""
        if not self.bot.player.ISDEAD:
            return "continue", False
        self.note_death()
        state = await self.wait_respawn(attempt)
        if state == "reset":
            return "reset", False
        if state == "stopped":
            return "stopped", False
        if not self.boss_alive():
            return "defeated", False
        if not await self.aggressive_move(self.normal_target()):
            return "stopped", False
        return "continue", True

    async def fight_damage_dealer(self, attempt: int) -> str:
        """``FightDamageDealer``: hold the normal target, no taunt duty."""
        self.log("started fighting.")
        while self.cmd.is_still_connected() and not self.sync.aborted():
            result = self.fight_result(attempt)
            if result != "continue":
                return await self.finish_fight(result)
            result, _ = await self.recover(attempt)
            if result != "continue":
                return await self.finish_fight(result)
            self.target_priority = (self.normal_target(),)
            await self.cmd.sleep(self.poll_ms)
        return await self.finish_fight("stopped")

    async def fight_immediate_algie_taunter(self, attempt: int) -> str:
        """``FightImmediateAlgieTaunter``: taunt Algie, else normal target."""
        self.log("started fighting.")
        while self.cmd.is_still_connected() and not self.sync.aborted():
            result = self.fight_result(attempt)
            if result != "continue":
                return await self.finish_fight(result)
            result, _ = await self.recover(attempt)
            if result != "continue":
                return await self.finish_fight(result)

            taunted = False
            if (self.cmd.is_monster_alive(ALGIE)
                    and self.bot.player.canUseSkill(5)):
                self.request_taunt(ALGIE)
                taunted = True
            if not taunted:
                self.target_priority = (self.normal_target(),)
            await self.cmd.sleep(self.poll_ms)
        return await self.finish_fight("stopped")

    async def fight_guard_pair(self, attempt: int) -> str:
        """``FightGuardPair``: alternate the guard Focus taunt with the partner."""
        guard = self.guard_map_id()
        partner = self.partner_slot()
        opening_owner = self.is_opening_owner()

        pair_closed = False
        owns_focus = False
        waiting_for_focus = opening_owner
        partner_death_seen = False
        signal_number = 1
        focus_baseline = datetime.min
        next_inspection = datetime.min

        self.log("started fighting.")
        if opening_owner and self.cmd.is_monster_alive(guard):
            focus_baseline = self.begin_taunt_acquisition(guard)
            self.log("requested the first guard taunt.")

        while self.cmd.is_still_connected() and not self.sync.aborted():
            result = self.fight_result(attempt)
            if result != "continue":
                return await self.finish_fight(result)
            result, recovered = await self.recover(attempt)
            if result != "continue":
                return await self.finish_fight(result)

            if not pair_closed and not self.cmd.is_monster_alive(guard):
                pair_closed = True
                owns_focus = False
                waiting_for_focus = False
                self.log("closed its guard taunt loop.")

            if pair_closed:
                self.target_priority = (self.normal_target(),)
                await self.cmd.sleep(self.poll_ms)
                continue

            if recovered:
                signal_number = self.align_signal(signal_number, opening_owner)
                owns_focus = False
                waiting_for_focus = True
                focus_baseline = self.begin_taunt_acquisition(guard)
                self.log("owns the next guard taunt after returning.")

            if not waiting_for_focus:
                self.target_priority = (self.normal_target(),)

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
                        self.log("restored alternating guard taunts.")
                    else:
                        self.request_taunt(guard)
                        await self.cmd.sleep(self.poll_ms)
                        continue

            focus = self.target_aura_expiry(FOCUS, guard)
            now = datetime.now()

            if waiting_for_focus:
                if focus is not None and focus > focus_baseline:
                    focus_baseline = focus
                    next_inspection = focus - timedelta(
                        milliseconds=FOCUS_REFRESH_MS)
                    waiting_for_focus = False
                    owns_focus = True
                    self.target_priority = (self.normal_target(),)
                    self.log("confirmed its Focus and owns the taunt cycle.")
                elif focus is None:
                    self.request_taunt(guard)
            elif owns_focus and now >= next_inspection:
                if focus is None:
                    owns_focus = False
                    waiting_for_focus = True
                    focus_baseline = datetime.min
                    self.request_taunt(guard)
                elif focus - now <= timedelta(milliseconds=FOCUS_REFRESH_MS):
                    signal = self.taunt_signal(attempt, signal_number)
                    self.sync.signal(signal, True)
                    self.log(f"sent {signal} to player{partner}.")
                    signal_number += 1
                    owns_focus = False
                    self.target_priority = (self.normal_target(),)
                else:
                    next_inspection = focus - timedelta(
                        milliseconds=FOCUS_REFRESH_MS)
                    self.target_priority = (self.normal_target(),)
            elif not owns_focus and not waiting_for_focus:
                signal = self.taunt_signal(attempt, signal_number)
                if self.sync.read(signal).get(partner):
                    signal_number += 1
                    focus_baseline = self.begin_taunt_acquisition(guard)
                    waiting_for_focus = True
                    self.log(f"received {signal} and requested its scheduled "
                             f"guard taunt.")

            await self.cmd.sleep(self.poll_ms)

        return await self.finish_fight("stopped")

    async def finish_fight(self, result: str) -> str:
        """``FinishFight``: stop the engine and say how the fight ended."""
        await self.stop_skills()
        if not self.cmd.is_still_connected() or self.sync.aborted():
            return "stopped"
        if result == "defeated":
            self.log("confirmed King Drago defeated.")
        elif result == "reset":
            self.log("received the coordinated fight reset.")
        return result

    # --------------------------------------------------------------- helpers
    def begin_taunt_acquisition(self, guard: str) -> datetime:
        """``BeginTauntAcquisition``: note Focus, then request the guard taunt."""
        self.target_priority = (guard,)
        baseline = self.target_aura_expiry(FOCUS, guard)
        self.request_taunt(guard)
        return baseline or datetime.min

    def partner_state(self, slot: int) -> Optional[Tuple[bool, bool]]:
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


async def main(cmd, slot: int = 1, options: Optional[UltraOptions] = None) -> None:
    """Run one pane standalone (``python -m bot.ultra.v2.weeklies.drago``)."""
    runner = UltraDrago(cmd, options or UltraOptions(), slot)
    okay = await runner.run()
    if not okay and runner.aborted:
        cmd.bot.log(f"[V2 Drago] slot {slot} stopped: {runner.aborted}")
