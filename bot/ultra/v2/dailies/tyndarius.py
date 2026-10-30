"""Ultra Tyndarius -- port of ``Dailies/UltraTyndarius_LW.cs``.

The reference fight, in the order its own code runs it:

1. **Prepare** -- class, enhancements, potions; a taunter also stocks the
   Scroll of Enrage and drops its combat potion (slot 5 belongs to the scroll).
2. **PrepareSafeRoom** -- drink the potions, equip the scroll, prebuff.
3. **Righteous Seal** -- the ArchPaladin pane alone walks into ``Boss/Left``,
   keeps the boss targeted and casts skill 3 until the boss carries the
   ``Righteous Seal`` aura; then it publishes ``RIGHTEOUS_n``.  Every other pane
   waits for that signal before moving in.
4. **Fight** -- the two adds are hit before the boss: ``GetPriorityTarget`` is
   SecondAdd (id.3) -> FirstAdd (id.1) -> MainBoss (id.2).  The taunter panes
   hold aggro; everyone else deals damage on the same priority.
5. Death is recovered in place (respawn, walk back, keep fighting); only a whole
   party wipe resets, and a reset retries from potions + prebuff.
"""
from __future__ import annotations

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

#: ``UltraTyndarius_LW`` constants.
FIRST_ADD = 1
SECOND_ADD = 3
MAIN_BOSS = 2
BOSS = "id.2"                # the same target as a string, for the tests/logs
RIGHTEOUS_SEAL = "Righteous Seal"
FOCUS = "Focus"
HEAL_BELOW = 60
ARCH_PALADIN_SLOT = 3        # GetArchPaladinPlayerNumber() for the ported comps


def _id(map_id: int) -> str:
    return f"id.{map_id}"


class UltraTyndarius(V2Core):
    """One pane of the Tyndarius fight."""

    def __init__(self, cmd, options: UltraOptions, slot: int = 1):
        super().__init__(cmd, SPEC, options, slot)
        self.skill_rotation = (0, 1, 2, 0, 3, 4)
        self.heal_below = HEAL_BELOW
        self.is_taunter = self.slot >= 3      # IsTaunterRole: slots 3 and 4
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

    # ------------------------------------------------------------------ setup
    async def prepare(self, *, scroll: Optional[str] = None,
                      drop_combat_potion: bool = False) -> bool:
        return await super().prepare(
            scroll=scroll, drop_combat_potion=drop_combat_potion or self.is_taunter)

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
        if not await self.sync.step("PREFLIGHT"):
            return False
        if not await self.validate_access():
            return False
        self.log(f"started as {self.alias}: {self.describe()}")

        await self.join()
        if not await self.accept_quest():
            return False
        if not await self.prepare(scroll=scrolls.ENRAGE if self.is_taunter
                                  else None):
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
        attempts = retries + 1
        for attempt in range(1, attempts + 1):
            await self.join()
            await self.use_potions(drop_combat_potion=self.is_taunter)
            if self.is_taunter:
                await scrolls.equip(self.cmd, scrolls.ENRAGE)
            if not await self.sync.step("FIGHT_READY"):
                return False

            # Righteous Seal gate: the ArchPaladin seals, the rest wait.
            seal_signal = f"RIGHTEOUS_{attempt}"
            if self.is_arch_paladin:
                if not await self.righteous_seal():
                    return False
                self.sync.signal(seal_signal, True)
                await self.jump_boss()
            else:
                self.sync.wait_signal(seal_signal, timeout=120)
                await self.jump_boss()
            await self.precast_buffs()
            if not await self.sync.step("BUFFS_DONE"):
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
        waited = 0
        while (self.cmd.is_still_connected()
               and not any(self.cmd.is_monster_alive(_id(m))
                           for m in (FIRST_ADD, SECOND_ADD, MAIN_BOSS))
               and waited < 10_000):
            await self.cmd.sleep(200)
            waited += 200

        await self.start_skills(_id(MAIN_BOSS), taunter=self.is_taunter)
        self.log("started fighting.")

        while self.cmd.is_still_connected() and not self.sync.aborted():
            if not self.boss_alive():
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
                if not self.in_boss_room():
                    await self.jump_boss()
                await self.precast_buffs()
                continue

            # The taunter keeps skill 5 on the highest-priority monster.
            if self.is_taunter and self.bot.player.canUseSkill(5):
                self.request_taunt()

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
