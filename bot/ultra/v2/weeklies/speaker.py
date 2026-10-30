"""Ultra Speaker -- port of ``UltraSpeaker_LW.cs``.

The fight is a walking chart, not a taunt ladder:

* Speaker announces **Truth** (``I will make you see the truth.``) and
  **Listen** (``You shall listen.``) in ``ct`` packets, in a fixed order per
  section.  Each expected warning names the pane that answers it ("fresh") and,
  on some steps, a pane that queues a specific skill.
* Every **Equalize** (an ``event`` packet with ``zoneSet`` "A") closes a
  section and hands the red zone to the next owner.  Zones are coordinates in
  ``Boss/Left``: safe ``(890, 395)``, red ``(731, 380)``, tolerance 20.
* The pane whose zone it is walks in, waits for ``Sanctity``, walks safe again
  and publishes ``SPEAKER_ZONE_{attempt}_{cycle}_CLEAR`` for the next owner.
* A chart mismatch is published as ``SPEAKER_CHART_FAILURE_{attempt}``; pane 1
  turns that into ``SPEAKER_CHART_RESET_{attempt}`` and the party resets.

The ArchPaladin covers ``Righteous Seal`` with skill 4 when its remaining time
falls inside the last second.  ``BruteForceMethod`` keeps everyone in the safe
zone and ignores the whole chart -- the script's own emergency switch.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from bot.ultra.v2 import scrolls
from bot.ultra.v2.core import V2Core
from bot.ultra.v2.options import UltraOptions, UltraSpec
from bot.ultra.v2.packets import MarkerWatcher, ZoneWatcher

SPEC = UltraSpec(
    id="speaker",
    title="Ultra Speaker",
    quest=9173,
    prereq_quest=9125,
    prereq_name="Your Hero",
    min_level=90,
    map="ultraspeaker",
    safe_cell="Enter",
    safe_pad="Spawn",
    boss_cell="Boss",
    boss_pad="Left",
    monster_id=1,                 # SpeakerMapId
    extra_options=(
        {
            "key": "brute_force",
            "label": "Brute Force Method",
            "help": "Keep every pane in the safe zone and ignore the Equalize "
                    "movement chart.  The script's own emergency switch for "
                    "when Ultra Speaker is bugged.",
            "default": False,
        },
    ),
)

SPEAKER = "id.1"
ENRAGE = scrolls.ENRAGE
TRUTH = "I will make you see the truth."
LISTEN = "You shall listen."
SANCTITY = "Sanctity"
RIGHTEOUS_SEAL = "Righteous Seal"

SAFE_X, SAFE_Y = 890, 395
RED_X, RED_Y = 731, 380
TOLERANCE = 20
WALK_SPEED = 8
RETRY_MS = 500
SEAL_WINDOW_MS = 1000

#: ``ZoneOwners``: cycle 1 -> slot 2, then 1, 3, 4.
ZONE_OWNERS = (2, 1, 3, 4)
AP_PLAYER = 3


@dataclass(frozen=True)
class Step:
    warning: str
    owner: int
    fresh: bool
    skill_owner: int = 0
    skill: int = 0


OPENING = (Step(TRUTH, 1, True), Step(LISTEN, 4, True))
SECTION_ONE = (Step(TRUTH, 3, True, 3, 3),
               Step(LISTEN, 2, True),
               Step(TRUTH, 2, False, 4, 4))
SECTION_TWO = (Step(LISTEN, 1, True),
               Step(TRUTH, 1, False, 3, 3),
               Step(TRUTH, 4, True),
               Step(LISTEN, 4, False))


@dataclass
class ZoneState:
    moving: bool = False
    x: int = 0
    y: int = 0
    arrival: str = ""
    confirm_at: float = 0.0
    waiting_sanctity: int = 0
    waiting_clear: int = 0


class UltraSpeaker(V2Core):
    """One pane of the Ultra Speaker fight."""

    def __init__(self, cmd, options: UltraOptions, slot: int = 1):
        super().__init__(cmd, SPEC, options, slot)
        self.brute_force = bool((options.extras or {}).get("brute_force"))
        # Default/Reliable arm every pane as a taunter, like the other weeklies.
        self.is_taunter = True
        self.warnings = MarkerWatcher(self.bot, "ct", (TRUTH, LISTEN),
                                      require_all=False, choice=True)
        self.zones = ZoneWatcher(self.bot)
        self._warning_queue: List[str] = []
        #: ``pauseEveryChoice``: the skill engine holds while a fresh taunt is
        #: being placed, and resumes for every other warning.
        self._paused_for_taunt = False
        self._section = 0
        self._step = 0
        self._next_warning = 1
        self._next_equalize = 1
        self._equalize_cycle = 0
        self._chart_invalid = False
        self._failure_sent = False
        self._reset_sent = False
        self._next_failure_sender = 1
        self._seal_queued = False
        self._boss_seen = False

    # --------------------------------------------------------------- chart
    @staticmethod
    def section_steps(section: int) -> Tuple[Step, ...]:
        if section == 0:
            return OPENING
        if section in (1, 3):
            return SECTION_ONE
        if section in (2, 4):
            return SECTION_TWO
        return ()

    @staticmethod
    def zone_owner(cycle: int) -> int:
        return ZONE_OWNERS[(cycle - 1) % len(ZONE_OWNERS)]

    def zone_clear_signal(self, attempt: int, cycle: int) -> str:
        return f"SPEAKER_ZONE_{attempt}_{cycle}_CLEAR"

    def chart_failure_signal(self, attempt: int) -> str:
        return f"SPEAKER_CHART_FAILURE_{attempt}"

    def chart_reset_signal(self, attempt: int) -> str:
        return f"SPEAKER_CHART_RESET_{attempt}"

    @staticmethod
    def warning_name(warning: str) -> str:
        return "Truth" if warning == TRUTH else (
            "Listen" if warning == LISTEN else "Unknown")

    # ------------------------------------------------------------ movement
    def at(self, x: int, y: int) -> bool:
        return (abs(int(getattr(self.bot.player, "X", 0)) - x) <= TOLERANCE
                and abs(int(getattr(self.bot.player, "Y", 0)) - y) <= TOLERANCE)

    async def start_movement(self, state: ZoneState, x: int, y: int,
                             arrival: str = "") -> None:
        state.moving = True
        state.x, state.y = x, y
        state.arrival = arrival
        await self.issue_movement(state)

    async def issue_movement(self, state: ZoneState) -> None:
        await self.cmd.walk_to(state.x, state.y, WALK_SPEED)
        state.confirm_at = time.time() + RETRY_MS / 1000.0

    async def start_initial_movement(self, state: ZoneState) -> None:
        if self.brute_force:
            await self.start_movement(state, SAFE_X, SAFE_Y)
        elif self.slot == self.zone_owner(1):
            await self.start_movement(state, RED_X, RED_Y)
        else:
            await self.start_movement(state, SAFE_X, SAFE_Y)

    async def restore_zone_after_death(self, state: ZoneState,
                                       attempt: int) -> None:
        state.moving = False
        state.arrival = ""
        state.confirm_at = 0.0
        state.waiting_sanctity = 0
        state.waiting_clear = 0
        if self.brute_force:
            await self.start_movement(state, SAFE_X, SAFE_Y)
            return
        next_cycle = self._equalize_cycle + 1
        if self.slot != self.zone_owner(next_cycle):
            await self.start_movement(state, SAFE_X, SAFE_Y)
            return
        if self._equalize_cycle == 0:
            await self.start_movement(state, RED_X, RED_Y)
            return
        signal = self.zone_clear_signal(attempt, self._equalize_cycle)
        owner = self.zone_owner(self._equalize_cycle)
        if self.sync.read(signal).get(owner):
            await self.start_movement(state, RED_X, RED_Y)
        else:
            await self.start_movement(state, SAFE_X, SAFE_Y)
            state.waiting_clear = self._equalize_cycle

    async def process_zone_state(self, state: ZoneState, attempt: int) -> bool:
        if self.bot.player.ISDEAD or not self.in_boss_room():
            return True
        if state.moving:
            if time.time() < state.confirm_at:
                return True
            if not self.at(state.x, state.y):
                await self.issue_movement(state)
                return True
            state.moving = False
            if state.arrival:
                signal = state.arrival
                state.arrival = ""
                self.sync.signal(signal, True)
                self.log(f"sent {signal}.")
            return True

        if self.brute_force:
            return True

        if state.waiting_sanctity:
            if self.self_aura(SANCTITY) is None:
                return True
            cycle = state.waiting_sanctity
            state.waiting_sanctity = 0
            await self.start_movement(state, SAFE_X, SAFE_Y,
                                      self.zone_clear_signal(attempt, cycle))
            return True

        if state.waiting_clear:
            cycle = state.waiting_clear
            owner = self.zone_owner(cycle)
            signal = self.zone_clear_signal(attempt, cycle)
            if not self.sync.read(signal).get(owner):
                return True
            state.waiting_clear = 0
            await self.start_movement(state, RED_X, RED_Y)
        return True

    # ------------------------------------------------------------- warnings
    def collect_warnings(self) -> None:
        """Drain the detector's history into the local queue."""
        for warning in self.warnings.drain_history():
            self._warning_queue.append(warning)

    def process_warnings(self) -> Tuple[bool, str]:
        """``ProcessWarningDetections``: walk the chart in order."""
        while self._warning_queue:
            steps = self.section_steps(self._section)
            if self._step >= len(steps):
                return False, (f"unexpected {self.warning_name(self._warning_queue[0])} "
                               f"before the next Equalize")
            expected = steps[self._step]
            detected = self._warning_queue.pop(0)
            if detected != expected.warning:
                return False, (f"expected {self.warning_name(expected.warning)} "
                               f"but detected {self.warning_name(detected)}")
            self._next_warning += 1
            self._step += 1

            fresh_owner = expected.fresh and self.slot == expected.owner
            if fresh_owner:
                self.request_taunt(SPEAKER)
                # The engine pauses until that taunt goes out (the reference
                # resumes only when the pane is *not* the fresh owner).
                self.suppress_rotation = True
                self._paused_for_taunt = True
                self.log(f"requested fresh {self.warning_name(expected.warning)} "
                         f"taunt.")
            else:
                self.suppress_rotation = False
                self._paused_for_taunt = False
                if not expected.fresh:
                    self.log(f"processed covered "
                             f"{self.warning_name(expected.warning)}.")

            if (not self.brute_force and expected.skill > 0
                    and self.slot == expected.skill_owner):
                self.priority_skill = expected.skill
                if expected.skill_owner == AP_PLAYER and expected.skill == 3:
                    self._seal_queued = False
                self.log(f"queued chart skill {expected.skill}.")
        return True, ""

    def process_equalize(self, attempt: int, state: ZoneState) -> Tuple[bool, str]:
        """``ProcessEqualizeDetections``: the red zone moves on."""
        while self._next_equalize <= self._equalize_events:
            if self._step != len(self.section_steps(self._section)):
                return False, (f"Equalize arrived before section "
                               f"{self._section} completed")
            cycle = self._next_equalize
            self._next_equalize += 1
            owner = self.zone_owner(cycle)
            if not self.brute_force and self.slot == owner and not self.at(
                    RED_X, RED_Y):
                return False, f"Equalize cycle {cycle} owner was not in the red zone"

            self._equalize_cycle = cycle
            self._section = ((cycle - 1) % 4) + 1
            self._step = 0

            if not self.brute_force:
                if self.slot == owner:
                    state.waiting_sanctity = cycle
                if self.slot == self.zone_owner(cycle + 1):
                    state.waiting_clear = cycle
            self.log(f"entered Equalize cycle {cycle} section {self._section}.")
        return True, ""

    async def report_chart_failure(self, attempt: int, reason: str) -> bool:
        self._chart_invalid = True
        self.log(f"chart mismatch: {reason}")
        if self._failure_sent:
            return True
        signal = self.chart_failure_signal(attempt)
        self.sync.signal(signal, True)
        self._failure_sent = True
        self.log(f"sent {signal}.")
        return True

    def publish_chart_reset(self, attempt: int) -> bool:
        if self.slot != 1 or self._reset_sent:
            return True
        failure = self.chart_failure_signal(attempt)
        reported = bool(self.sync.read(failure).get(self._next_failure_sender))
        self._next_failure_sender = self._next_failure_sender % 4 + 1
        if not reported:
            return True
        signal = self.chart_reset_signal(attempt)
        self.sync.signal(signal, True)
        self._reset_sent = True
        self.log(f"sent {signal}.")
        return True

    def has_chart_reset(self, attempt: int) -> bool:
        return bool(self.sync.read(self.chart_reset_signal(attempt)).get(1))

    def maintain_righteous_seal(self) -> None:
        """``MaintainArchPaladinRighteousSeal``: skill 4 into the last second."""
        if self.slot != AP_PLAYER:
            return
        expiry = self.target_aura_expiry(RIGHTEOUS_SEAL, SPEAKER)
        if expiry is None:
            self._seal_queued = False
            return
        if self._seal_queued or self.priority_skill:
            return
        remaining = (expiry - __import__("datetime").datetime.now()).total_seconds() * 1000
        if remaining <= 0 or remaining > SEAL_WINDOW_MS:
            return
        self.priority_skill = 4
        self._seal_queued = True
        self.log("queued skill 4 for Righteous Seal.")

    async def choose_divine_elixir(self) -> None:
        """``GetDivineElixir``: StoneCrusher prefers the Unstable Divine Elixir.

        The reference checks the inventory, then the bank, and only then falls
        back to the plain Divine Elixir.  (Its last resort -- farming quest
        1854 -- is not ported; the plain elixir is used instead.)
        """
        from dataclasses import replace
        if self.preset.cls != "StoneCrusher":
            return
        unstable, divine = "Unstable Divine Elixir", "Divine Elixir"
        if self.cmd.is_in_bank(unstable) and not await self.cmd.has_item(unstable):
            await self.cmd.bank_to_inv(unstable)
        if await self.cmd.has_item(unstable):
            self.preset = replace(self.preset, elixir=unstable)
            self.log(f"{unstable} already available.")
            return
        if self.cmd.is_in_bank(divine) and not await self.cmd.has_item(divine):
            await self.cmd.bank_to_inv(divine)
        self.log(f"using {divine}.")

    # ---------------------------------------------------------------- flow
    async def run(self) -> bool:
        if not await self.require_step("PREFLIGHT"):
            return False
        if not await self.validate_access():
            return False
        self.log(f"started as {self.alias}: {self.describe()}")
        if self.brute_force:
            self.log("Brute Force Method is enabled; the chart is ignored.")

        await self.join()
        if not await self.accept_quest():
            return False
        await self.choose_divine_elixir()
        if not await self.prepare(scroll=ENRAGE if self.is_taunter else None,
                                  drop_combat_potion=self.is_taunter):
            return False
        if not await self.require_step("SETUP_DONE"):
            return False

        try:
            if not await self.defeat_and_turn_in():
                return False
        finally:
            self.stop_systems()
        if not await self.sync.step("BOSS_DEFEATED"):
            return False
        if not await self.sync.step("FINISH"):
            return False

        if self.slot == 1:
            self.sync.signal("COMPLETE", True)
        self.log("finished.")
        return True

    def stop_systems(self) -> None:
        self.warnings.stop()
        self.zones.stop()
        self._warning_queue.clear()

    async def fight_attempts(self) -> bool:
        retries = max(1, int(self.options.retries))
        attempts = retries + 1
        for attempt in range(1, attempts + 1):
            await self.join()
            await self.use_potions(drop_combat_potion=self.is_taunter)
            if self.is_taunter:
                await scrolls.equip(self.cmd, ENRAGE)
            await self.precast_buffs()
            if not await self.require_step("FIGHT_READY"):
                return False

            if not self.warnings.start() or not self.zones.start():
                return self.abort("the Speaker packet detectors could not start")
            try:
                await self.jump_boss()
                if not await self.require_step("START_FIGHT"):
                    return False
                self.begin_attempt(attempt)
                result = await self.fight(attempt)
            finally:
                self.stop_systems()

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
        """``Fight``: the warning chart, the zone walk, the seal."""
        self._section = 0
        self._step = 0
        self._next_warning = 1
        self._next_equalize = 1
        self._equalize_cycle = 0
        self._equalize_events = 0
        self._chart_invalid = False
        self._failure_sent = False
        self._reset_sent = False
        self._next_failure_sender = 1
        self._seal_queued = False
        self._boss_seen = False
        state = ZoneState()

        await self.start_skills(SPEAKER, taunter=self.is_taunter)
        await self.start_initial_movement(state)
        self.log(f"started fighting attempt {attempt}.")

        while self.cmd.is_still_connected() and not self.sync.aborted():
            if self.in_boss_room():
                if self.cmd.is_monster_alive(SPEAKER):
                    self._boss_seen = True
                elif self._boss_seen:
                    return await self.finish_fight("defeated")

            if not self.brute_force and self.should_reset(attempt):
                return await self.finish_fight("reset")

            for zone in self.zones.drain():
                if zone == "A":
                    self._equalize_events += 1
            self.collect_warnings()

            if not self._chart_invalid:
                ok, mismatch = self.process_warnings()
                if not ok:
                    await self.report_chart_failure(attempt, mismatch)
                if not self._chart_invalid:
                    ok, mismatch = self.process_equalize(attempt, state)
                    if not ok:
                        await self.report_chart_failure(attempt, mismatch)

            if self._paused_for_taunt and not self.taunt_requested:
                self._paused_for_taunt = False
                self.suppress_rotation = False

            self.publish_chart_reset(attempt)
            if self.has_chart_reset(attempt):
                return await self.finish_fight("reset")

            if self.bot.player.ISDEAD:
                if not getattr(self, "_player_was_dead", False):
                    self._player_was_dead = True
                    self.note_death()
                    self.log("died.")
                await self.cmd.sleep(self.poll_ms)
                continue

            if getattr(self, "_player_was_dead", False):
                self._player_was_dead = False
                self.log("respawned.")
                if not self.in_boss_room():
                    await self.jump_boss()
                await self.restore_zone_after_death(state, attempt)

            if not await self.process_zone_state(state, attempt):
                return await self.finish_fight("stopped")

            if self.in_boss_room():
                self.target_priority = (SPEAKER,)
                if not self.brute_force:
                    self.maintain_righteous_seal()

            await self.cmd.sleep(self.poll_ms)

        return await self.finish_fight("stopped")

    async def finish_fight(self, result: str) -> str:
        await self.stop_skills()
        if not self.cmd.is_still_connected() or self.sync.aborted():
            return "stopped"
        return result


async def main(cmd, slot: int = 1, options: Optional[UltraOptions] = None) -> None:
    """Run one pane standalone (``python -m bot.ultra.v2.weeklies.speaker``)."""
    runner = UltraSpeaker(cmd, options or UltraOptions(), slot)
    okay = await runner.run()
    if not okay and runner.aborted:
        cmd.bot.log(f"[V2 Speaker] slot {slot} stopped: {runner.aborted}")
