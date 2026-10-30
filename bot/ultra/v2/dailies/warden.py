"""Ultra Warden, the four-player army fight -- port of ``Dailies/UltraWarden_LW``.

The simplest of the eleven: one boss (``id.1``), one Enrage taunt below 500,000 HP,
and no scroll cycles or packet detectors.  It is the vertical slice that proves
the V2 engine (gear, potions, sync, wipeout, quest gates) before the rest follow.

Roles, from the reference:

* ``Default`` / ``Reliable`` -- **slot 1** is the taunter;
* ``Stable`` -- **slot 2** is the taunter (King's Echo cannot hold the aggro
  itself, so StoneCrusher takes it);
* a taunter carries no combat potion: slot 5 belongs to the Scroll of Enrage.
"""
from __future__ import annotations

from typing import Optional

from bot.ultra.v2 import scrolls
from bot.ultra.v2.core import V2Core
from bot.ultra.v2.options import UltraOptions, UltraSpec
from bot.ultra.v2.presets import preset_for

SPEC = UltraSpec(
    id="warden",
    title="Ultra Warden",
    quest=8153,
    prereq_quest=8151,
    prereq_name="The Engineer",
    min_level=61,
    map="ultrawarden",
    safe_cell="Enter",
    safe_pad="Spawn",
    boss_cell="r2",
    boss_pad="Left",
    monster_id=1,
    taunt_hp=500_000,
)


def taunter_slot(composition: str) -> int:
    """Which slot holds aggro in this composition."""
    return 2 if composition == "Stable" else 1


class UltraWarden(V2Core):
    """One pane of the Warden fight."""

    def __init__(self, cmd, options: UltraOptions, slot: int = 1):
        super().__init__(cmd, SPEC, options, slot)
        # v1: ``attack_loop([0, 1, 2, 0, 3, 4], heal_below=5, heal_skill=2)``
        # -- the rotation starts on the auto attack and repeats it, which is
        # what keeps the attack chain (and its mana) alive.
        self.skill_rotation = (0, 1, 2, 0, 3, 4)
        self.heal_below = 5
        self.is_taunter = self.slot == taunter_slot(options.composition)

    async def run(self) -> bool:
        """The reference's ``Run``: gate, setup, attempts, turn-in, sync."""
        if not await self.require_step("PREFLIGHT"):
            return False
        if not await self.validate_access():
            return False
        self.log(f"started as {self.alias}: {self.describe()}")

        await self.join()
        if not await self.accept_quest():
            return False
        if not await self.prepare(scroll=scrolls.ENRAGE if self.is_taunter else None,
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
        """``RunFightAttempts``: one attempt per retry the option allows."""
        retries = max(1, int(self.options.retries))
        # One first attempt plus the wipeout retries, so "1" still means "go
        # back in once" -- a reset must not end the run by itself.
        attempts = retries + 1
        for attempt in range(1, attempts + 1):
            await self.join()
            await self.use_potions(drop_combat_potion=self.is_taunter)
            if self.is_taunter:
                await scrolls.equip(self.cmd, scrolls.ENRAGE)
            if not await self.require_step("FIGHT_READY"):
                return False

            # Buffs go up *before* the jump: bosses that provoke on aggro
            # punish a party that walks in unbuffed.  All four cast first, then
            # the party pulls together.
            await self.precast_buffs()
            if not await self.require_step("BUFFS_DONE"):
                return False

            await self.jump_boss()
            if not await self.require_step("START_FIGHT"):
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
                # A wipe retries from the potions up: nothing is re-equipped
                # (the gear never left), only the consumed buffs and slot 5.
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
        """``Fight``: hold the boss down until it dies, we die, or we reset."""
        target = f"id.{self.spec.monster_id}"
        use_survival = self.options.composition != "Stable"

        # The boss is not in the cell the instant the jump lands; wait for it so
        # the loop cannot read "no monster" as "already defeated".
        waited = 0
        while (self.cmd.is_still_connected() and not self.cmd.is_monster_alive(target)
               and waited < 10_000):
            await self.cmd.sleep(200)
            waited += 200
        if not self.cmd.is_monster_alive(target):
            # A timeout is not a kill: without this the loop below reads "no
            # monster" as "already defeated" and turns the quest in for nothing.
            self.abort(f"{target} never appeared in "
                       f"{self.spec.boss_cell}/{self.spec.boss_pad}")
            return "stopped"

        await self.start_skills(target, use_survival=use_survival,
                               taunter=self.is_taunter)
        self.log("started fighting.")
        taunt_requested = False

        while self.cmd.is_still_connected() and not self.sync.aborted():
            if not self.cmd.is_monster_alive(target):
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
                if not self.cmd.is_monster_alive(target):
                    break
                if self.should_reset(attempt):
                    return "reset"
                if not self.in_boss_room():
                    await self.jump_boss()
                # The buffs died with us: cast them again before attacking.
                await self.precast_buffs()
                continue

            health = self.cmd.get_monster_hp(target)
            if (self.is_taunter and not taunt_requested and health > 0
                    and health <= self.spec.taunt_hp):
                self.request_taunt()
                taunt_requested = True
                self.log("requested the Warden taunt.")

            await self.cmd.sleep(self.poll_ms)

        await self.stop_skills()
        if not self.cmd.is_still_connected():
            return "stopped"
        self.log("confirmed Ultra Warden defeated.")
        return "defeated"


def build(cmd, options: Optional[UltraOptions] = None,
          slot: int = 1) -> UltraWarden:
    """Construct one pane, with the reference's defaults when none are given."""
    return UltraWarden(cmd, options or UltraOptions(), slot)


async def main(cmd, slot: int = 1, options: Optional[UltraOptions] = None) -> None:
    """Run one pane standalone (``python -m bot.ultra.v2.dailies.warden``)."""
    runner = build(cmd, options, slot)
    okay = await runner.run()
    if not okay and runner.aborted:
        cmd.bot.log(f"[V2 Warden] slot {slot} stopped: {runner.aborted}")
