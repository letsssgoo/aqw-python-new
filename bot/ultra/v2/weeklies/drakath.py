"""Ultra Champion Drakath -- port of ``UltraDrakath_LW.cs``.

The fight is a boss-only pull against ``id.1``; the work is the **taunt ladder**:
the StoneCrusher (slot 2) and the ArchPaladin (slot 3) each take aggro once when
the boss crosses a fixed HP threshold, in order, so every big hit is covered by
a different pane instead of one taunter eating the whole fight.

Everything else is the shared shape:

* ``Prepare`` -- class, enhancements, potions, and the Scroll of Enrage for the
  two taunters (a taunter carries no combat potion: slot 5 is the scroll);
* ``PrepareSafeRoom`` -- potions, scroll and ``GenericPrebuff`` (skills 3, 2, 1
  with 750 ms between them, verbatim from ``CoreLoneWolf.GenericPrebuff``);
* ``RunFightAttempts`` -- join, prepare, ``FIGHT_READY``, jump to ``r2/Left``,
  ``START_FIGHT``, fight, ``FIGHT_RESET_{n}_SAFE`` after a wipe.

Cape overrides, from ``Run()``: the ArchPaladin always wears Penitence; slot 1
wears Penitence on Default/Reliable, and on Stable the King's Echo's Vainglory
becomes Lament.

Only ``Default`` / ``Stable`` / ``Reliable`` are ported (Optimized and the three
Pay2Win columns need classes the V2 presets do not carry).
"""
from __future__ import annotations

from typing import Optional, Tuple

from bot.ultra.v2 import scrolls
from bot.ultra.v2.core import V2Core
from bot.ultra.v2.options import UltraOptions, UltraSpec

SPEC = UltraSpec(
    id="drakath",
    title="Ultra Drakath",
    quest=8300,
    prereq_quest=3881,
    prereq_name="The Final Showdown!",
    min_level=80,
    map="championdrakath",
    safe_cell="Enter",
    safe_pad="Spawn",
    boss_cell="r2",
    boss_pad="Left",
    monster_id=1,
)

BOSS = "id.1"
ENRAGE = scrolls.ENRAGE

#: ``StoneCrusherTauntThresholds`` / ``ArchPaladinTauntThresholds`` and the
#: ``Adjusted*`` pair Stable uses, in the order the boss crosses them.
STONE_CRUSHER_THRESHOLDS = (16_500_000, 12_500_000, 6_200_000)
STONE_CRUSHER_STABLE_THRESHOLDS = (16_500_000, 12_500_000, 6_500_000)
ARCH_PALADIN_THRESHOLDS = (18_500_000, 14_500_000, 8_200_000, 4_200_000)
ARCH_PALADIN_STABLE_THRESHOLDS = (18_500_000, 14_500_000, 8_500_000,
                                  4_500_000)

#: The two panes that taunt: ``IsTaunterRole`` for the ported compositions.
TAUNTER_SLOTS = (2, 3)

#: ``GenericPrebuff``: skill 3, then 2, then 1, 750 ms apart.
PREBUFF_SKILLS = (3, 2, 1)
PREBUFF_GAP_MS = 750


class UltraDrakath(V2Core):
    """One pane of the Champion Drakath fight."""

    def __init__(self, cmd, options: UltraOptions, slot: int = 1):
        super().__init__(cmd, SPEC, options, slot)
        self.is_taunter = self.slot in TAUNTER_SLOTS
        #: Set in :meth:`fight`, like the reference's local ``tauntIndex``.
        self._taunt_index = 0

    # -------------------------------------------------------------- taunting
    def taunt_thresholds(self) -> Tuple[int, ...]:
        """``GetTauntThresholds`` for this slot and composition."""
        stable = self.options.composition == "Stable"
        if self.slot == 2:
            return (STONE_CRUSHER_STABLE_THRESHOLDS if stable
                    else STONE_CRUSHER_THRESHOLDS)
        if self.slot == 3:
            return (ARCH_PALADIN_STABLE_THRESHOLDS if stable
                    else ARCH_PALADIN_THRESHOLDS)
        return ()

    def boss_hp(self) -> int:
        """The boss's current HP; 0 when it is not in the cell."""
        monster = self.cmd.get_monster(BOSS)
        return int(getattr(monster, "current_hp", 0) or 0) if monster else 0

    def due_taunt(self) -> Optional[int]:
        """The threshold this poll crossed, or None (``RequestAbsolutePriorityTaunt``).

        The list is walked once per attempt, in order: the boss only ever loses
        HP, so ``tauntIndex`` in the reference advances exactly like this.
        """
        thresholds = self.taunt_thresholds()
        if self._taunt_index >= len(thresholds):
            return None
        health = self.boss_hp()
        if health <= 0 or health > thresholds[self._taunt_index]:
            return None
        threshold = thresholds[self._taunt_index]
        self._taunt_index += 1
        return threshold

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
            # ``GenericPrebuff`` runs in the safe room, before the barrier and
            # before the jump -- the pull is buffed on every attempt.
            await self.precast_buffs(skills=PREBUFF_SKILLS,
                                     gap_ms=PREBUFF_GAP_MS)
            if not await self.require_step("FIGHT_READY"):
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
        """``Fight``: hold ``id.1`` and spend the taunt ladder as HP falls."""
        self._taunt_index = 0
        await self.start_skills(BOSS, taunter=self.is_taunter)
        self.target_priority = (BOSS,)
        self.log("started fighting.")

        while self.cmd.is_still_connected() and not self.sync.aborted():
            if not self.cmd.is_monster_alive(BOSS):
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
                if not self.cmd.is_monster_alive(BOSS):
                    break
                if self.should_reset(attempt):
                    await self.stop_skills()
                    return "reset"
                # The reference does not re-precast here: the pane walks back
                # in and the skill engine (restarted by the respawn) carries on.
                if not self.in_boss_room():
                    await self.jump_boss()
                continue

            self.target_priority = (BOSS,)
            threshold = self.due_taunt()
            if threshold is not None:
                self.request_taunt(BOSS)
                self.log(f"requested taunt at {threshold:,} HP.")

            await self.cmd.sleep(self.poll_ms)

        await self.stop_skills()
        if not self.cmd.is_still_connected() or self.sync.aborted():
            return "stopped"
        self.log("confirmed Champion Drakath defeated.")
        return "defeated"


async def main(cmd, slot: int = 1, options: Optional[UltraOptions] = None) -> None:
    """Run one pane standalone (``python -m bot.ultra.v2.weeklies.drakath``)."""
    runner = UltraDrakath(cmd, options or UltraOptions(), slot)
    okay = await runner.run()
    if not okay and runner.aborted:
        cmd.bot.log(f"[V2 Drakath] slot {slot} stopped: {runner.aborted}")
