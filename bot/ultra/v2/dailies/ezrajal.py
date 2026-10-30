"""Ultra Ezrajal, the four-player army fight -- port of ``UltraEzrajal_LW``.

The boss telegraphs a **counter attack**; the reference's fight loop pauses its
own rotation while that aura is on the target, which is the whole difference from
Warden.  ``SkipManaLock`` defaults to **true** in the reference, so the default
run here is the same one: no Battle Oracle Battlestaff swap, no mana-lock phase.
Asking for the mana lock (``SkipManaLock`` off) is reported as not ported yet
instead of being faked -- the weapon swap and its phase are a separate job.

Buffs go up before every pull, and again after a wipe: the buffs do not survive
death, so a reset attempt that walks back in without re-casting fights naked.
"""
from __future__ import annotations

from typing import Optional

from bot.ultra.v2 import scrolls
from bot.ultra.v2.core import V2Core
from bot.ultra.v2.options import UltraOptions, UltraSpec

SPEC = UltraSpec(
    id="ezrajal",
    title="Ultra Ezrajal",
    quest=8152,
    prereq_quest=8151,
    prereq_name="The Engineer",
    min_level=61,
    map="ultraezrajal",
    safe_cell="Enter",
    safe_pad="Spawn",
    boss_cell="r2",
    boss_pad="Left",
    monster_id=1,
    taunt_hp=0,
    extra_options=(
        {
            "key": "skip_mana_lock",
            "label": "Skip Mana Lock",
            "help": "The reference default: fight without the Battle Oracle "
                    "Battlestaff / Mana Vamp swap.  Turning it off needs the "
                    "mana-lock phase, which is not ported yet.",
            "default": True,
        },
    ),
)


class UltraEzrajal(V2Core):
    """One pane of the Ezrajal fight."""

    def __init__(self, cmd, options: UltraOptions, slot: int = 1):
        super().__init__(cmd, SPEC, options, slot)
        self.respect_counter_attack = True
        self.skip_mana_lock = bool(options.extras.get("skip_mana_lock", True))

    async def run(self) -> bool:
        """Gate, setup, attempts, turn-in -- the reference's ``Run``."""
        if not await self.sync.step("PREFLIGHT"):
            return False
        if not await self.validate_access():
            return False
        if not self.skip_mana_lock:
            return self.abort("the mana-lock phase is not ported yet; enable "
                              "'Skip Mana Lock' or wait for it")
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
        target = f"id.{self.spec.monster_id}"
        waited = 0
        while (self.cmd.is_still_connected()
               and not self.cmd.is_monster_alive(target) and waited < 10_000):
            await self.cmd.sleep(200)
            waited += 200
        if not self.cmd.is_monster_alive(target):
            # Ezrajal has a spawn delay of its own; a timeout means "not here
            # yet", never "already dead".
            self.abort(f"{target} never appeared in "
                       f"{self.spec.boss_cell}/{self.spec.boss_pad}")
            return "stopped"

        await self.start_skills(target, use_survival=True)
        self.log("started fighting.")
        holding = False

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
                await self.precast_buffs()
                continue

            active = self.counter_attack_active(target)
            if active and not holding:
                self.log("counter attack is up; holding the rotation "
                         "(buffs only).")
            elif not active and holding:
                self.log("counter attack is over; back on the rotation.")
            holding = active
            await self.cmd.sleep(self.poll_ms)

        await self.stop_skills()
        if not self.cmd.is_still_connected() or self.sync.aborted():
            return "stopped"
        self.log("confirmed Ultra Ezrajal defeated.")
        return "defeated"


async def main(cmd, slot: int = 1, options: Optional[UltraOptions] = None) -> None:
    """Run one pane standalone (``python -m bot.ultra.v2.dailies.ezrajal``)."""
    runner = UltraEzrajal(cmd, options or UltraOptions(), slot)
    okay = await runner.run()
    if not okay and runner.aborted:
        cmd.bot.log(f"[V2 Ezrajal] slot {slot} stopped: {runner.aborted}")
