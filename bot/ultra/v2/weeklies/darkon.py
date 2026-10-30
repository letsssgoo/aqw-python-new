"""Ultra Darkon -- port of ``UltraDarkon_LW.cs``.

One boss (``id.1``) and a packet cycle the party answers together:

* the boss's ``ct`` packets carry a caster marker plus an animation marker
  (``Attack2`` or ``Attack3``); **each detection is a cycle**;
* the **Enrage taunters** alternate on those cycles -- slots 1 and 2 on
  Default/Reliable (slot 1 opens), slots 2 and 3 on Stable (slot 2 opens) --
  and the taunt goes out 1250 ms after the cycle is seen;
* the **heal** for a cycle is a skill 2 queued 250 ms later, with the
  ordinary rotation suppressed until it lands;
* Stable relays ``Attack2`` from slot 1 to the ArchPaladin instead of letting
  it read the packet itself (``DARKON_ATTACK2_{attempt}_{cycle}``).

The ArchPaladin also runs three phases off the boss's auras:

=================  ==============  ==========================
phase              ``A Major``     skills
=================  ==============  ==========================
before ``Aria``    --              ``3, 1, 4``
after ``Aria``     yes             ``1``
after ``Aria``     no              ``1, 3``
=================  ==============  ==========================

and covers ``Righteous Seal`` with skill 4 in its last 1500 ms.

The Lord of Order holds skill 4 once the boss is at 10,000,000 HP (while it has
no ``Aria``) and releases it with absolute priority at 4,500,000.

Optimized (LightCaster) and Pay2Win are not ported.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Optional

from bot.ultra.v2 import scrolls
from bot.ultra.v2.core import V2Core
from bot.ultra.v2.options import UltraOptions, UltraSpec
from bot.ultra.v2.packets import MarkerWatcher

SPEC = UltraSpec(
    id="darkon",
    title="Ultra Darkon",
    quest=8746,
    prereq_quest=8733,
    prereq_name="The World",
    min_level=90,
    map="ultradarkon",
    safe_cell="Enter",
    safe_pad="Spawn",
    boss_cell="r2",
    boss_pad="Left",
    monster_id=1,                 # DarkonMapId
)

BOSS = "id.1"
ENRAGE = scrolls.ENRAGE
BOSS_CASTER = '"cInf":"m:1"'
ATTACK2 = '"animStr":"Attack2"'
ATTACK3 = '"animStr":"Attack3"'
ARIA = "Aria"
A_MAJOR = "A Major"
RIGHTEOUS_SEAL = "Righteous Seal"

LOO_HOLD_HP = 10_000_000
LOO_RELEASE_HP = 4_500_000
TAUNT_DELAY_MS = 1250
AP_HEAL_WINDOW_START_MS = 5000
AP_HEAL_WINDOW_MS = 1500
HEAL_DELAY_MS = 250
SEAL_WINDOW_MS = 1500

DEFAULT_RELIABLE = ("Default", "Reliable")
STABLE = "Stable"


class UltraDarkon(V2Core):
    """One pane of the Ultra Darkon fight."""

    def __init__(self, cmd, options: UltraOptions, slot: int = 1):
        super().__init__(cmd, SPEC, options, slot)
        self.composition = options.composition
        self.detector = MarkerWatcher(
            self.bot, "ct",
            (BOSS_CASTER, ATTACK2 if self.detects_attack2()
             else ATTACK3))
        self._taunt_cycle = 0
        self._taunt_at = 0.0
        self._ap_cycle = 0
        self._ap_window_start = 0.0
        self._heal_cycle = 0
        self._heal_attack = ""
        self._heal_at = 0.0
        self._loo_hold_logged = False
        self._loo_requested = False
        self._loo_released = False
        self._ap_phase_three = False
        self._ap_blocked = False
        self._boss_seen = False

    # ----------------------------------------------------------------- roles
    def uses_p1_p2_taunters(self) -> bool:
        return self.composition in DEFAULT_RELIABLE

    def uses_relayed_attack2(self) -> bool:
        return self.composition in (STABLE, "Optimized")

    def is_taunter(self) -> bool:
        return (self.slot in (1, 2) if self.uses_p1_p2_taunters()
                else self.slot in (2, 3))

    def is_arch_paladin(self) -> bool:
        return self.slot == 3

    def is_opening_owner(self) -> bool:
        return self.slot == (1 if self.uses_p1_p2_taunters() else 2)

    def detects_attack2(self) -> bool:
        return (self.slot == 1 if self.uses_relayed_attack2()
                else self.slot == 3)

    def attack2_signal(self, attempt: int, cycle: int) -> str:
        return f"DARKON_ATTACK2_{attempt}_{cycle}"

    # ---------------------------------------------------------------- auras
    def boss_aura(self, name: str) -> bool:
        return self.target_aura(name, BOSS)

    def boss_hp(self) -> int:
        monster = self.cmd.get_monster(BOSS)
        return int(getattr(monster, "current_hp", 0) or 0) if monster else 0

    # --------------------------------------------------------------- cycles
    def collect_cycles(self) -> None:
        for marker in self.detector.drain_history():
            cycle = self._next_cycle
            self._next_cycle += 1
            if self.uses_relayed_attack2() and self.slot == 1:
                self.sync.signal(self.attack2_signal(self._attempt, cycle), True)
                self.log(f"relayed Attack2 cycle {cycle}.")
                continue

            if self.is_arch_paladin() and not self.uses_relayed_attack2():
                self.schedule_heal("Attack2", cycle)
                self.schedule_ap_heal(cycle)
                continue

            if marker == ATTACK3 or self.uses_relayed_attack2():
                self.handle_taunt_cycle(cycle)
                if self.slot == 4 and (cycle == 1 or cycle % 2 == 0):
                    self.schedule_heal("Attack3", cycle)

    def handle_taunt_cycle(self, cycle: int) -> None:
        if not self.is_taunter():
            return
        owns = (cycle % 2 == 1) if self.is_opening_owner() else (cycle % 2 == 0)
        if owns:
            self._taunt_cycle = cycle
            self._taunt_at = time.time() + TAUNT_DELAY_MS / 1000.0
            self.log(f"detected owned Attack3 cycle {cycle}.")

    def schedule_heal(self, attack: str, cycle: int) -> None:
        self._heal_cycle = cycle
        self._heal_attack = attack
        self._heal_at = time.time() + HEAL_DELAY_MS / 1000.0
        self.suppress_rotation = True
        self.log(f"scheduled its {attack} heal for cycle {cycle}.")

    def try_delayed_heal(self) -> None:
        if not self._heal_cycle or time.time() < self._heal_at:
            return
        attack, cycle = self._heal_attack, self._heal_cycle
        self._heal_cycle, self._heal_attack, self._heal_at = 0, "", 0.0
        self.priority_skill = 2
        self.suppress_rotation = False
        self.log(f"queued its delayed {attack} heal for cycle {cycle}.")

    def schedule_ap_heal(self, cycle: int) -> None:
        self._ap_cycle = cycle
        self._ap_window_start = time.time() + AP_HEAL_WINDOW_START_MS / 1000.0

    def try_ap_extra_heal(self) -> None:
        if not self._ap_cycle:
            return
        now = time.time()
        if now < self._ap_window_start:
            return
        if self._ap_phase_three:
            cycle = self._ap_cycle
            self._ap_cycle, self._ap_window_start = 0, 0.0
            self.priority_skill = 2
            self.log(f"queued its mandatory Phase 3 midpoint heal for cycle "
                     f"{cycle}.")
            return
        if now >= self._ap_window_start + AP_HEAL_WINDOW_MS / 1000.0:
            self._ap_cycle, self._ap_window_start = 0, 0.0
            return
        if not self.bot.player.canUseSkill(2):
            return
        cycle = self._ap_cycle
        self._ap_cycle, self._ap_window_start = 0, 0.0
        self.priority_skill = 2
        self.log(f"queued its optional Attack2 heal for cycle {cycle}.")

    # ---------------------------------------------------- ArchPaladin phases
    def handle_arch_paladin(self) -> None:
        if not self.is_arch_paladin() or self.bot.player.ISDEAD:
            return
        phase_changed = False
        if not self._ap_phase_three and self.boss_aura(ARIA):
            self._ap_phase_three = True
            phase_changed = True
            self.log("switched to its Phase 3 skill array.")

        blocked = self.boss_aura(A_MAJOR)
        block_changed = blocked != self._ap_blocked
        if phase_changed or block_changed:
            if self._ap_phase_three:
                skills = (1,) if blocked else (1, 3)
            else:
                skills = (1, 4) if blocked else (3, 1, 4)
            self.skill_rotation = skills
            self._ap_blocked = blocked
            if block_changed:
                self.log("blocked skill 3 for A Major." if blocked
                         else "restored skill 3 after A Major.")

        if not self._ap_phase_three:
            return
        remaining = self.target_aura_expiry(RIGHTEOUS_SEAL, BOSS)
        if remaining is None or self.priority_skill:
            return
        left = (remaining - datetime.now()).total_seconds() * 1000
        if left <= 0 or left > SEAL_WINDOW_MS:
            return
        if not self.bot.player.canUseSkill(4):
            return
        self.priority_skill = 4
        self.log("queued skill 4 for Righteous Seal.")

    # ------------------------------------------------------ Lord of Order
    def release_loo_skill_four(self) -> None:
        """Hold skill 4 under 10M HP, release it with priority at 4.5M."""
        if self._loo_released:
            return
        if self._loo_requested:
            if self.priority_skill:
                return
            self._loo_requested = False
            self._loo_released = True
            self.log("released held skill 4.")
            return
        if self.boss_aura(ARIA):
            return
        health = self.boss_hp()
        if health <= LOO_HOLD_HP and not self._loo_hold_logged:
            self._loo_hold_logged = True
            self.log("is holding skill 4.")
        if health <= LOO_RELEASE_HP:
            self.priority_skill = 4
            self._loo_requested = True
            self.log("queued held skill 4 with absolute priority.")

    async def use_loo_skill_four_normally(self) -> None:
        if self.priority_skill:
            return
        aria = self.boss_aura(ARIA)
        health = self.boss_hp()
        if not aria and (health <= LOO_HOLD_HP or self._loo_released):
            return
        if self.bot.player.canUseSkill(4):
            await self.cmd.use_skill(4, target_monsters=BOSS)

    # ---------------------------------------------------------------- flow
    async def run(self) -> bool:
        if not await self.require_step("PREFLIGHT"):
            return False
        if not await self.validate_access():
            return False
        self.log(f"started as {self.alias}: {self.describe()}")

        await self.join()
        if not await self.accept_quest():
            return False
        if not await self.prepare(scroll=ENRAGE if self.is_taunter() else None,
                                  drop_combat_potion=self.is_taunter()):
            return False
        if not await self.require_step("SETUP_DONE"):
            return False

        try:
            if not await self.defeat_and_turn_in():
                return False
        finally:
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
            self._attempt = attempt
            await self.join()
            await self.use_potions(drop_combat_potion=self.is_taunter())
            if self.is_taunter():
                await scrolls.equip(self.cmd, ENRAGE)
            await self.precast_buffs()
            if not self.detector.start():
                return self.abort("the Darkon packet detector could not start")
            if not await self.require_step("FIGHT_READY"):
                return False

            await self.jump_boss()
            if not await self.require_step("START_FIGHT"):
                return False
            await self.start_skills(BOSS, taunter=self.is_taunter())
            self.target_priority = (BOSS,)
            self.begin_attempt(attempt)
            try:
                result = await self.fight(attempt)
            finally:
                self.detector.stop()

            if result == "defeated":
                return True
            if result == "stopped":
                return False
            if result == "reset":
                if not await self.handle_reset(attempt):
                    return False
                await self.use_potions(drop_combat_potion=self.is_taunter())
                if self.is_taunter():
                    await scrolls.equip(self.cmd, ENRAGE)

            if attempt >= attempts:
                self.log(f"failed after {attempts} fight attempt(s).")
                if self.slot == 1:
                    self.sync.stop("ATTEMPTS_EXHAUSTED")
                return self.abort(f"the party wiped {retries} time(s)")
        return False

    async def fight(self, attempt: int) -> str:
        self._attempt = attempt
        self._next_cycle = 1
        self._taunt_cycle = 0
        self._ap_cycle = 0
        self._heal_cycle = 0
        self._loo_hold_logged = False
        self._loo_requested = False
        self._loo_released = False
        self._ap_phase_three = False
        self._ap_blocked = False
        self._boss_seen = self.boss_alive()
        self.log("started fighting.")

        while self.cmd.is_still_connected() and not self.sync.aborted():
            if self.boss_alive():
                self._boss_seen = True
            elif self._boss_seen:
                await self.stop_skills()
                self.log("confirmed Ultra Darkon defeated.")
                return "defeated"

            if self.should_reset(attempt):
                await self.stop_skills()
                return "reset"

            if self.bot.player.ISDEAD:
                self.log("died.")
                self._taunt_cycle = 0
                self._ap_cycle = 0
                self._heal_cycle = 0
                self.suppress_rotation = False
                state = await self.wait_respawn(attempt)
                if state == "reset":
                    await self.stop_skills()
                    return "reset"
                if state == "stopped":
                    await self.stop_skills()
                    return "stopped"
                if not self.boss_alive() and self._boss_seen:
                    break
                if not self.in_boss_room():
                    await self.jump_boss()
                self.advance_detections()
                continue

            self.target_priority = (BOSS,)

            if self.slot == 4:
                self.release_loo_skill_four()

            self.collect_cycles()
            if self.uses_relayed_attack2() and self.is_arch_paladin():
                self.handle_attack2_signals()
            self.try_delayed_heal()
            self.handle_arch_paladin()
            if self.is_arch_paladin():
                self.try_ap_extra_heal()

            if self._taunt_cycle and time.time() >= self._taunt_at:
                self.request_taunt(BOSS)
                self.log(f"requested Darkon taunt cycle {self._taunt_cycle}.")
                self._taunt_cycle = 0

            if self.slot == 4:
                await self.use_loo_skill_four_normally()

            await self.cmd.sleep(self.poll_ms)

        await self.stop_skills()
        if not self.cmd.is_still_connected() or self.sync.aborted():
            return "stopped"
        self.log("confirmed Ultra Darkon defeated.")
        return "defeated"

    def advance_detections(self) -> None:
        while self.detector.count >= getattr(self, "_next_cycle", 1):
            self._next_cycle += 1

    def handle_attack2_signals(self) -> None:
        if not hasattr(self, "_next_signal"):
            self._next_signal = 1
        while self.sync.read(self.attack2_signal(self._attempt,
                                                 self._next_signal)).get(1):
            self.schedule_heal("Attack2", self._next_signal)
            self.schedule_ap_heal(self._next_signal)
            self._next_signal += 1

    def boss_alive(self) -> bool:
        return self.cmd.is_monster_alive(BOSS)


async def main(cmd, slot: int = 1, options: Optional[UltraOptions] = None) -> None:
    """Run one pane standalone (``python -m bot.ultra.v2.weeklies.darkon``)."""
    runner = UltraDarkon(cmd, options or UltraOptions(), slot)
    okay = await runner.run()
    if not okay and runner.aborted:
        cmd.bot.log(f"[V2 Darkon] slot {slot} stopped: {runner.aborted}")
