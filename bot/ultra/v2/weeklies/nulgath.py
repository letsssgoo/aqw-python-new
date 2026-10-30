"""Ultra Nulgath -- port of ``UltraNulgath_LW.cs``.

Two monsters: the **Blade** (``id.1``) and Nulgath itself (``id.2``).  The
interesting half is the taunt relay, because Nulgath's ``Abyss!`` cast is not
visible in the bot's own state:

* slot 4 (Lord of Order) watches the ``ct`` packet stream for ``Abyss!``; two
  seconds later it taunts and publishes ``ABYSS_TAUNT_DONE_{attempt}_{cycle}``;
* the **taunter one** pane (slot 1 on Default, slot 3 otherwise) opens with a
  taunt five seconds into the pull, then answers every signal five seconds
  later with its own taunt.

Targets are per slot and per composition (``GetTargetMapId``):

===========  =====================================================
slot         target
===========  =====================================================
Default s2   Blade while alive and above 750,000 HP, else Nulgath
Stable s1    Blade while above 500,000 HP, else Nulgath
Stable s2    Blade while alive, else Nulgath
Reliable s1  Blade while alive, else Nulgath
Reliable s2  Blade while alive, else Nulgath
everything   Nulgath (s1/s3/s4 on Default, s3/s4 on Stable/Reliable)
===========  =====================================================

Only ``Default`` / ``Stable`` / ``Reliable`` are ported; Optimized, Pay2Win and
Fast need classes the V2 presets do not carry.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Tuple

from bot.ultra.v2 import scrolls
from bot.ultra.v2.core import V2Core
from bot.ultra.v2.options import UltraOptions, UltraSpec
from bot.ultra.v2.packets import PacketDetector

SPEC = UltraSpec(
    id="nulgath",
    title="Ultra Nulgath",
    quest=8692,
    prereq_quest=0,
    prereq_name="",
    min_level=80,
    map="ultranulgath",
    safe_cell="Enter",
    safe_pad="Spawn",
    boss_cell="Boss",
    boss_pad="Right",
    monster_id=2,                 # NulgathMapId
)

BLADE = "id.1"
NULGATH = "id.2"
ENRAGE = scrolls.ENRAGE

#: The Blade is only worth hitting above these HP thresholds.
BLADE_HEALTH_THRESHOLD = 750_000
STABLE_BLADE_THRESHOLD = 500_000

#: Taunt timing: the opening taunt five seconds into the pull, the Abyss answer
#: five seconds after slot 4's signal, and slot 4's own taunt two seconds after
#: it sees ``Abyss!``.
TAUNTER_ONE_TAUNT_DELAY_MS = 5000
PLAYER_FOUR_TAUNT_DELAY_MS = 2000

#: ``GenericPrebuff``: skills 3, 2, 1 with 750 ms between them.
PREBUFF_SKILLS = (3, 2, 1)
PREBUFF_GAP_MS = 750

#: The pane that watches the packet stream (``IsArmyPlayer(4)``).
WATCHER_SLOT = 4


class UltraNulgath(V2Core):
    """One pane of the Ultra Nulgath fight."""

    def __init__(self, cmd, options: UltraOptions, slot: int = 1):
        super().__init__(cmd, SPEC, options, slot)
        default = options.composition == "Default"
        self.is_taunter_one = self.slot == (1 if default else 3)
        self.is_taunter = self.is_taunter_one or self.slot == WATCHER_SLOT
        self.is_watcher = self.slot == WATCHER_SLOT
        self.detector = (PacketDetector(self.bot, "ct", "Abyss!")
                         if self.is_watcher else None)
        self._taunt_scheduled = False
        self._opening_taunt = False
        self._abyss_cycle = 1
        self._taunt_at = datetime.min

    # --------------------------------------------------------------- targets
    def target_map_id(self) -> str:
        """``GetTargetMapId``: which monster this slot hits right now."""
        composition = self.options.composition
        if composition in ("Stable", "Reliable"):
            if self.slot == 1:
                if composition == "Reliable":
                    return (BLADE if self.cmd.is_monster_alive(BLADE)
                            else NULGATH)
                return (BLADE if self.blade_hp() > STABLE_BLADE_THRESHOLD
                        else NULGATH)
            if self.slot == 2:
                return (BLADE if self.cmd.is_monster_alive(BLADE)
                        else NULGATH)
            return NULGATH
        # Default (and the compositions that are not ported) hit Nulgath,
        # except Default's slot 2, which chips the Blade while it is healthy.
        if self.slot != 2:
            return NULGATH
        return (BLADE if self.cmd.is_monster_alive(BLADE)
                and self.blade_hp() > BLADE_HEALTH_THRESHOLD else NULGATH)

    def blade_hp(self) -> int:
        monster = self.cmd.get_monster(BLADE)
        return int(getattr(monster, "current_hp", 0) or 0) if monster else 0

    # ------------------------------------------------------------ taunt relay
    def abyss_signal(self, attempt: int, cycle: int) -> str:
        return f"ABYSS_TAUNT_DONE_{attempt}_{cycle}"

    def start_taunt_cycle(self) -> None:
        """``Fight``'s locals: the taunter one opens five seconds in."""
        self._taunt_scheduled = self.is_taunter_one
        self._opening_taunt = self.is_taunter_one
        self._abyss_cycle = 1
        self._taunt_at = (datetime.now()
                          + timedelta(milliseconds=TAUNTER_ONE_TAUNT_DELAY_MS)
                          if self.is_taunter_one else datetime.min)

    def taunter_one_step(self, attempt: int, now: datetime) -> None:
        """``RunTaunterOneTaunts``: opening taunt, then answer every signal."""
        if self._taunt_scheduled:
            if now < self._taunt_at:
                return
            self.request_taunt(NULGATH)
            if self._opening_taunt:
                self._opening_taunt = False
                self.log("requested the opening Nulgath taunt.")
            else:
                self.log(f"requested Abyss response taunt {self._abyss_cycle}.")
                self._abyss_cycle += 1
            self._taunt_scheduled = False
            return

        signal = self.abyss_signal(attempt, self._abyss_cycle)
        if not self.sync.read(signal).get(WATCHER_SLOT):
            return
        self._taunt_at = now + timedelta(milliseconds=TAUNTER_ONE_TAUNT_DELAY_MS)
        self._taunt_scheduled = True
        self.log(f"received {signal}.")

    def player_four_step(self, attempt: int, now: datetime) -> bool:
        """``RunPlayerFourTaunts``: watch, wait two seconds, taunt, signal."""
        detector = self.detector
        if not self._taunt_scheduled:
            if detector is None or not detector.seen(self._abyss_cycle):
                return True
            self._taunt_at = now + timedelta(milliseconds=PLAYER_FOUR_TAUNT_DELAY_MS)
            self._taunt_scheduled = True
            self.log(f"detected Abyss cycle {self._abyss_cycle}.")
            return True

        if now < self._taunt_at:
            return True

        self.request_taunt(NULGATH)
        signal = self.abyss_signal(attempt, self._abyss_cycle)
        self.sync.signal(signal, True)
        self.log(f"requested taunt and sent {signal}.")
        self._abyss_cycle += 1
        self._taunt_scheduled = False
        return True

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

        try:
            if not await self.defeat_and_turn_in():
                return False
        finally:
            if self.detector is not None:
                self.detector.stop()
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
            await self.precast_buffs(skills=PREBUFF_SKILLS,
                                     gap_ms=PREBUFF_GAP_MS)
            if self.detector is not None and not self.detector.start():
                return self.abort("the Abyss packet detector could not start")
            if not await self.require_step("FIGHT_READY"):
                return False

            await self.jump_boss()
            if not await self.require_step("START_FIGHT"):
                return False

            self.begin_attempt(attempt)
            result = await self.fight(attempt)
            if self.detector is not None:
                self.detector.stop()
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
        """``Fight``: hold the slot's target and run the taunt relay."""
        self.start_taunt_cycle()
        await self.start_skills(NULGATH, taunter=self.is_taunter)
        self.log("started fighting.")

        while self.cmd.is_still_connected() and not self.sync.aborted():
            if not self.cmd.is_monster_alive(NULGATH):
                break
            if self.should_reset(attempt):
                await self.stop_skills()
                return "reset"

            if self.bot.player.ISDEAD:
                self.note_death()
                state = await self.wait_respawn(attempt)
                if state == "reset":
                    await self.stop_skills()
                    return "reset"
                if state == "stopped":
                    await self.stop_skills()
                    return "stopped"
                if not self.cmd.is_monster_alive(NULGATH):
                    break
                if self.should_reset(attempt):
                    await self.stop_skills()
                    return "reset"
                if not self.in_boss_room():
                    await self.jump_boss()
                continue

            self.target_priority = (self.target_map_id(),)
            now = datetime.now()
            if self.is_taunter_one:
                self.taunter_one_step(attempt, now)
            elif self.is_watcher:
                if not self.player_four_step(attempt, now):
                    await self.stop_skills()
                    return "stopped"

            await self.cmd.sleep(self.poll_ms)

        await self.stop_skills()
        if not self.cmd.is_still_connected() or self.sync.aborted():
            return "stopped"
        self.log("confirmed Ultra Nulgath defeated.")
        return "defeated"


async def main(cmd, slot: int = 1, options: Optional[UltraOptions] = None) -> None:
    """Run one pane standalone (``python -m bot.ultra.v2.weeklies.nulgath``)."""
    runner = UltraNulgath(cmd, options or UltraOptions(), slot)
    okay = await runner.run()
    if not okay and runner.aborted:
        cmd.bot.log(f"[V2 Nulgath] slot {slot} stopped: {runner.aborted}")
