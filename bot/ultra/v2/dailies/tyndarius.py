"""Ultra Tyndarius, the four-player army fight -- port of ``UltraTyndarius_LW``.

v1 (``bot/ultra/ultra_tyndarius.py``) is the reference for the fight itself:

* rotation ``0 1 2 0 3 4 5`` (auto-attack twice, skill 5 included),
* ``monster="id.2"`` -- the boss -- with the **crystals** coming from the
  loadout's ``monster_prio``: slot 1 opens on ``id.1``, slot 2 on ``id.3``, so
  each crystal dies before the boss; slots 3-4 stay on ``id.2``,
* heal below 60% on slots 3 and 4 (each with its own heal skill),
* no scroll.

The Warden/Ezrajal/Engineer wipe handling is reused unchanged: buffs before the
pull, reset only when the whole party is down, and the turn-in retries only when
the drop is actually missing.
"""
from __future__ import annotations

from typing import Optional

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
    monster_id=2,                    # id.2 is the boss
)

BOSS = "id.2"
FIRST_CRYSTAL = "id.1"
SECOND_CRYSTAL = "id.3"
HEAL_BELOW = 60


class UltraTyndarius(V2Core):
    """One pane of the Tyndarius fight."""

    def __init__(self, cmd, options: UltraOptions, slot: int = 1):
        super().__init__(cmd, SPEC, options, slot)
        # v1: ``attack_loop([0, 1, 2, 0, 3, 4, 5], monster="id.2",
        # heal_below=60, heal_skill=2)``.
        self.skill_rotation = (0, 1, 2, 0, 3, 4, 5)
        self.heal_below = HEAL_BELOW
        # The crystals are the loadout's ``monster_prio``: slot 1 takes id.1
        # first, slot 2 takes id.3, everyone else stays on the boss.
        if self.slot == 1:
            self.target_priority = (FIRST_CRYSTAL,)
        elif self.slot == 2:
            self.target_priority = (SECOND_CRYSTAL,)
        else:
            self.target_priority = ()

    def boss_alive(self) -> bool:
        """The boss, by map id (names can lag the definition packet)."""
        return self.cmd.is_monster_alive(BOSS)

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
        waited = 0
        while (self.cmd.is_still_connected()
               and not self.boss_alive() and waited < 10_000):
            await self.cmd.sleep(200)
            waited += 200
        if not self.boss_alive():
            self.abort(f"{BOSS} never appeared in "
                       f"{self.spec.boss_cell}/{self.spec.boss_pad}")
            return "stopped"

        await self.start_skills(BOSS)
        self.log("started fighting.")

        while self.cmd.is_still_connected() and not self.sync.aborted():
            if not self.boss_alive():
                # v1 re-enters the fight until the quest is turnable; the boss
                # leaving the cell between phases is not a kill.
                if self.cmd.can_turnin_quest(self.spec.quest):
                    break
                await self.cmd.sleep(500)
                if not self.in_boss_room():
                    await self.jump_boss()
                continue
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
                if not self.boss_alive():
                    continue
                if not self.in_boss_room():
                    await self.jump_boss()
                await self.precast_buffs()
                continue

            await self.cmd.sleep(self.poll_ms)

        await self.stop_skills()
        if not self.cmd.is_still_connected() or self.sync.aborted():
            return "stopped"
        self.log("confirmed Ultra Tyndarius defeated.")
        return "defeated"


async def main(cmd, slot: int = 1, options: Optional[UltraOptions] = None) -> None:
    """Run one pane standalone (``python -m bot.ultra.v2.dailies.tyndarius``)."""
    runner = UltraTyndarius(cmd, options or UltraOptions(), slot)
    okay = await runner.run()
    if not okay and runner.aborted:
        cmd.bot.log(f"[V2 Tyndarius] slot {slot} stopped: {runner.aborted}")
