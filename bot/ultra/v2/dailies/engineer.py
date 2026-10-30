"""Ultra Engineer, the four-player army fight -- port of ``UltraEngineer_LW``.

The boss comes with two adds, and the reference's fight loop re-reads which of
the three is alive every pass, in a fixed order:

    FirstTargetMapId (id.2) -> SecondTargetMapId (id.1) -> MainBossMapId (id.3)

The fight ends when the **main boss** dies, not when the last add does.  No
taunter, no scroll: Engineer is the simplest of the four dailies after Warden.
"""
from __future__ import annotations

from typing import Optional

from bot.ultra.v2.core import V2Core
from bot.ultra.v2.options import UltraOptions, UltraSpec

SPEC = UltraSpec(
    id="engineer",
    title="Ultra Engineer",
    quest=8154,
    prereq_quest=8151,
    prereq_name="The Engineer",
    min_level=61,
    map="ultraengineer",
    safe_cell="Enter",
    safe_pad="Spawn",
    boss_cell="r2",
    boss_pad="Left",
    monster_id=3,                 # MainBossMapId
)

#: The two drones, in the reference's order.  v1 targets them **by name**
#: ("Attack Drone,Defense Drone"); the boss is only the fallback.
FIRST_TARGET = "Attack Drone"
SECOND_TARGET = "Defense Drone"
BOSS_NAME = "Ultra Engineer"

#: v1 heals below 60% with skill 2 (``attack_loop(..., heal_below=60,
#: heal_skill=2)``); the heal check itself runs on slots 3 and 4, v1's
#: ``support_slots`` default.
HEAL_BELOW = 60
HEAL_SKILL = 2


class UltraEngineer(V2Core):
    """One pane of the Engineer fight."""

    def __init__(self, cmd, options: UltraOptions, slot: int = 1):
        super().__init__(cmd, SPEC, options, slot)
        # Boss is the fallback; the drones are tried first while they live.
        self.target_priority = (FIRST_TARGET, SECOND_TARGET)
        # v1: ``attack_loop([0, 1, 2, 0, 3, 4], heal_below=60, heal_skill=2)``
        # -- the literal rotation; the heal check runs on slots 3 and 4 only
        # (v1's ``support_slots``), each with its own heal skill.
        self.skill_rotation = (0, 1, 2, 0, 3, 4)
        self.heal_below = HEAL_BELOW
        # Two panes down is not a wipe here: the survivors keep the ring while
        # the others respawn.
        self.wipe_deaths = 4

    async def run(self) -> bool:
        if not await self.sync.step("PREFLIGHT"):
            return False
        if not await self.validate_access():
            return False
        self.log(f"started as {self.alias}: {self.describe()}")

        await self.join()
        if not await self.accept_quest():
            return False
        if not await self.prepare():
            return False
        if not await self.sync.step("SETUP_DONE"):
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
        for attempt in range(1, retries + 1):
            await self.join()
            await self.use_potions()
            if not await self.sync.step("FIGHT_READY"):
                return False

            await self.precast_buffs()
            if not await self.sync.step("BUFFS_DONE"):
                return False

            await self.jump_boss()
            if not await self.sync.step("START_FIGHT"):
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

            if attempt >= retries:
                self.log(f"failed after {retries} fight attempt(s).")
                if self.slot == 1:
                    self.sync.stop("ATTEMPTS_EXHAUSTED")
                return self.abort(f"the party wiped {retries} time(s)")
        return False

    async def fight(self, attempt: int) -> str:
        boss = BOSS_NAME
        waited = 0
        while (self.cmd.is_still_connected()
               and not self.cmd.is_monster_alive(boss) and waited < 10_000):
            await self.cmd.sleep(200)
            waited += 200
        if not self.cmd.is_monster_alive(boss):
            # Never appeared: the fight cannot be called a win.  Reporting
            # "defeated" here is how a run turns in a quest it never did.
            self.abort(f"{boss} never appeared in "
                       f"{self.spec.boss_cell}/{self.spec.boss_pad}")
            return "stopped"

        await self.start_skills(boss)
        self.log("started fighting.")

        while self.cmd.is_still_connected() and not self.sync.aborted():
            if not self.cmd.is_monster_alive(boss):
                break
            if self.should_reset(attempt):
                await self.stop_skills()
                return "reset"

            if self.bot.player.ISDEAD:
                self.note_death()
                state = await self.wait_respawn(attempt)
                if state == "reset":
                    return "reset"
                if state == "stopped":
                    break
                if not self.cmd.is_monster_alive(boss):
                    break
                if self.should_reset(attempt):
                    return "reset"
                if not self.in_boss_room():
                    await self.jump_boss()
                # The buffs went with the death; cast them again.
                await self.precast_buffs()
                continue

            # The skill engine re-reads the add order every tick; nothing else
            # to do here but keep the loop alive while the boss stands.
            await self.cmd.sleep(self.poll_ms)

        await self.stop_skills()
        if not self.cmd.is_still_connected() or self.sync.aborted():
            return "stopped"
        self.log("confirmed Ultra Engineer defeated.")
        return "defeated"


async def main(cmd, slot: int = 1, options: Optional[UltraOptions] = None) -> None:
    """Run one pane standalone (``python -m bot.ultra.v2.dailies.engineer``)."""
    runner = UltraEngineer(cmd, options or UltraOptions(), slot)
    okay = await runner.run()
    if not okay and runner.aborted:
        cmd.bot.log(f"[V2 Engineer] slot {slot} stopped: {runner.aborted}")
