"""Ultra Gramiel -- port of ``UltraGramiel_LW.cs``.

Two phases in one fight, and both are driven by raw packet fragments rather
than by the bot's own state:

* **Phase 1 -- the Grace Crystals** (``id.2`` and ``id.3``).  The party keeps
  them even: once their HP differ by more than 20 the balancers switch to the
  healthier crystal and stop again at a difference of 2.  Crystal charges are
  detected from ``ct`` packets (charge message, ``Charge`` animation, crystal A
  caster) and answered with taunts that alternate between the two panes that
  own odd/even cycles.
* **Phase 2 -- Gramiel** (``id.1``).  Each nuke cycle walks a detector chain:
  attack packets (up to attack 7) -> ``Liberator`` -> ``Charge2`` ->
  ``ChargeAttack2`` -> waiting for ``Invulnerable`` to fall.  Three cycles.
  Before each one, the party holds damage at a fixed Gramiel HP (75%, 45%, 15%)
  and casts only its healing skill; slots 1-2 keep skill 3, slots 3-4 skill 2.

Optimized runs a **Shaman** on slot 1 (Wizard/Elysium/Absolution): it queues
skill 4 on Gramiel -- once opening, once again after ``Safeguard`` -- and turns
skill 3 off while Gramiel is ``Invulnerable``.  Reliable's Verus DoomKnight
keeps skill 4 out of its rotation while ``Safeguard`` is on the target.

Pay2Win is not ported.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Tuple

from bot.ultra.v2 import scrolls
from bot.ultra.v2.core import V2Core
from bot.ultra.v2.options import UltraOptions, UltraSpec
from bot.ultra.v2.packets import MarkerWatcher

SPEC = UltraSpec(
    id="gramiel",
    title="Ultra Gramiel",
    quest=10301,
    prereq_quest=9986,
    prereq_name="Isa, Reversed - Realized",
    min_level=80,
    map="ultragramiel",
    safe_cell="Enter",
    safe_pad="Spawn",
    boss_cell="r2",
    boss_pad="Down",
    monster_id=1,                 # GramielMapId
)

GRAMIEL = "id.1"
CRYSTAL_A = "id.2"
CRYSTAL_B = "id.3"
ENRAGE = scrolls.ENRAGE

CRYSTAL_CHARGE_MESSAGE = "Grace Crystals are charging"
CHARGE_ANIM = '"animStr":"Charge"'
CRYSTAL_A_CASTER = '"cInf":"m:2"'
SAFEGUARD = "Safeguard"
GRACE_GIVEN = "Grace Given"
GRAMIEL_CASTER = '"cInf":"m:1"'
ATTACK_ANIM = '"animStr":"Attack'
CHARGE_TWO_ANIM = '"animStr":"Charge2"'
CHARGE_ATTACK_TWO_ANIM = '"animStr":"ChargeAttack2"'
LIBERATOR = "Liberator"
INVULNERABLE = "Invulnerable"

BALANCE_START = 20
BALANCE_STOP = 2
TAUNT_TARGET_HOLD_MS = 1500
NUKE_CYCLES = 3
HEAL_HOLD_THRESHOLDS = {1: 75, 2: 45}     # anything later is 15


class UltraGramiel(V2Core):
    """One pane of the Ultra Gramiel fight."""

    def __init__(self, cmd, options: UltraOptions, slot: int = 1):
        super().__init__(cmd, SPEC, options, slot)
        composition = options.composition
        self.is_shaman = composition == "Optimized" and self.slot == 1
        self.is_vdk = composition == "Reliable" and self.slot == 1
        self.detector = MarkerWatcher(
            self.bot, "ct",
            (CRYSTAL_CHARGE_MESSAGE, CHARGE_ANIM, CRYSTAL_A_CASTER))
        self.next_cycle = 1
        self.taunt_target_until = datetime.min
        self.crystal_balancing = False
        self.safeguard_active = False
        self.emergency_target = 0
        self._boss_seen = False
        if self.is_vdk:
            # Verus DoomKnight's skill 4 is off-limits while Safeguard is up.
            self.blocked_skill = 4
            self.blocked_skill_target_aura = SAFEGUARD

    # ----------------------------------------------------------------- roles
    def assigned_crystal(self) -> str:
        if self.options.composition in ("Default", "Optimized"):
            return CRYSTAL_A if self.slot in (1, 2) else CRYSTAL_B
        return CRYSTAL_A if self.slot in (1, 4) else CRYSTAL_B

    def owns_cycle(self, cycle: int) -> bool:
        opening_owner = self.slot in (1, 3)
        return (cycle % 2 == 1) == opening_owner

    def phase_two_taunt_attack(self) -> int:
        return {1: 1, 2: 3, 3: 5, 4: 7}[self.slot]

    def healing_hold_skills(self) -> Tuple[int, ...]:
        return (3,) if self.slot in (1, 2) else (2,)

    def is_balancer(self) -> bool:
        if self.options.composition == "Reliable":
            return self.slot in (2, 4)
        if self.options.composition == "Default":
            return self.slot == 4
        return self.slot in (1, 2)

    def safeguard_attacker(self) -> bool:
        return self.slot in (2, 3) if self.options.composition == "Default" \
            else True

    def crystal_hp(self, target: str) -> int:
        monster = self.cmd.get_monster(target)
        return int(getattr(monster, "current_hp", 0) or 0) if monster else 0

    def gramiel_hp_percent(self) -> float:
        monster = self.cmd.get_monster(GRAMIEL)
        if monster is None:
            return 100.0
        maximum = int(getattr(monster, "max_hp", 0) or 0)
        if maximum <= 0:
            return 100.0
        return int(getattr(monster, "current_hp", 0) or 0) * 100.0 / maximum

    # ----------------------------------------------------------------- flow
    async def run(self) -> bool:
        if not await self.require_step("PREFLIGHT"):
            return False
        if not await self.validate_access():
            return False
        self.log(f"started as {self.alias}: {self.describe()}")

        await self.join()
        if not await self.accept_quest():
            return False
        if not await self.prepare(scroll=ENRAGE, drop_combat_potion=True):
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
            await self.join()
            await self.use_potions(drop_combat_potion=True)
            await scrolls.equip(self.cmd, ENRAGE)
            await self.precast_buffs()
            if not self.detector.start():
                return self.abort("the crystal packet detector could not start")
            if not await self.require_step("FIGHT_READY"):
                return False

            await self.jump_boss()
            self.begin_attempt(attempt)
            result = await self.phase_one(attempt)
            if result == "completed":
                result = await self.phase_two(attempt)
                if result == "completed":
                    self.detector.stop()
                    return True
            self.detector.stop()
            if result == "stopped":
                return False
            if result == "reset":
                if not await self.handle_reset(attempt):
                    return False
                await self.use_potions(drop_combat_potion=True)
                await scrolls.equip(self.cmd, ENRAGE)

            if attempt >= attempts:
                self.log(f"failed after {attempts} fight attempt(s).")
                if self.slot == 1:
                    self.sync.stop("ATTEMPTS_EXHAUSTED")
                return self.abort(f"the party wiped {retries} time(s)")
        return False

    # --------------------------------------------------------------- phase 1
    def phase_one_rotation(self) -> Tuple[int, ...]:
        """The skills Phase 1 casts, without skill 0 (which has its own tick).

        The Shaman runs the reference's short 1-2-3 (its engine adds skill 4
        through ``maintain_shaman_skill_four``); everyone else keeps the class
        preset -- Verus DoomKnight's strict list included, which the strict
        engine walks from ``preset.skills``.
        """
        rotation = (1, 2, 3) if self.is_shaman else self.preset.skills
        return tuple(slot for slot in rotation if slot != 0)

    async def phase_one(self, attempt: int) -> str:
        self.skill_rotation = self.phase_one_rotation()
        await self.start_skills(GRAMIEL, taunter=True)
        self.next_cycle = 1
        self.crystal_balancing = False
        self.safeguard_active = False
        self.emergency_target = 0
        self.log("started Phase 1.")

        crystals_seen = False

        while self.cmd.is_still_connected() and not self.sync.aborted():
            a_hp = self.crystal_hp(CRYSTAL_A)
            b_hp = self.crystal_hp(CRYSTAL_B)

            if self.should_reset(attempt):
                await self.stop_skills()
                return "reset"

            if self.bot.player.ISDEAD:
                self.crystal_balancing = False
                self.safeguard_active = False
                self.taunt_target_until = datetime.min
                state = await self.wait_respawn(attempt)
                if state == "reset":
                    await self.stop_skills()
                    return "reset"
                if state == "stopped":
                    await self.stop_skills()
                    return "stopped"
                if not self.in_boss_room():
                    await self.jump_boss()
                self.advance_detections()
                continue

            if not crystals_seen:
                if a_hp > 0 and b_hp > 0:
                    crystals_seen = True
                    self.log("observed both Grace Crystals.")
                else:
                    await self.cmd.sleep(self.poll_ms)
                    continue

            if a_hp <= 0 and b_hp <= 0:
                break

            both = a_hp > 0 and b_hp > 0
            self.handle_crystal_detections(both)
            await self.maintain_phase_one_target(a_hp, b_hp)
            if self.is_shaman:
                await self.maintain_shaman_skill_four(both)
            await self.cmd.sleep(self.poll_ms)

        await self.stop_skills()
        if not self.cmd.is_still_connected() or self.sync.aborted():
            return "stopped"
        self.log("confirmed both Grace Crystals defeated.")
        return "completed"

    def handle_crystal_detections(self, both_alive: bool) -> None:
        """``HandleCrystalDetections``: taunt the assigned crystal per cycle."""
        while self.detector.running and self.detector.count >= self.next_cycle:
            cycle = self.next_cycle
            self.next_cycle += 1
            if not both_alive or not self.owns_cycle(cycle):
                continue
            crystal = self.assigned_crystal()
            self.target_priority = (crystal,)
            self.request_taunt(crystal)
            self.taunt_target_until = (datetime.now()
                                       + timedelta(milliseconds=TAUNT_TARGET_HOLD_MS))
            self.log(f"requested crystal taunt cycle {cycle} on {crystal}.")

    def advance_detections(self) -> None:
        while self.detector.running and self.detector.count >= self.next_cycle:
            self.next_cycle += 1

    async def maintain_phase_one_target(self, a_hp: int, b_hp: int) -> None:
        """``MaintainPhaseOneTarget``: survivors, Safeguard, then balancing."""
        if a_hp <= 0 or b_hp <= 0:
            survivor = CRYSTAL_A if a_hp > 0 else CRYSTAL_B
            if self.emergency_target != survivor:
                self.emergency_target = survivor
                self.log(f"focusing surviving Crystal {survivor}.")
            self.crystal_balancing = False
            self.safeguard_active = False
            self.target_priority = (survivor,)
            return

        self.emergency_target = 0
        assigned = self.assigned_crystal()

        if self.safeguard_attacker():
            current = self.target_aura(SAFEGUARD)
            if current != self.safeguard_active:
                self.safeguard_active = current
                self.log("detected Safeguard on Gramiel." if current
                         else "detected Safeguard ended.")
            if datetime.now() < self.taunt_target_until or current:
                self.target_priority = (assigned if datetime.now()
                                        < self.taunt_target_until else GRAMIEL,)
                return

        if not self.is_balancer() or datetime.now() < self.taunt_target_until:
            self.target_priority = (assigned,)
            return

        difference = abs(a_hp - b_hp)
        if not self.crystal_balancing and difference > BALANCE_START:
            self.crystal_balancing = True
            self.log(f"started crystal balancing at {a_hp}/{b_hp} HP.")
        if not self.crystal_balancing:
            self.target_priority = (assigned,)
            return
        if difference <= BALANCE_STOP:
            self.crystal_balancing = False
            self.log(f"finished crystal balancing at {a_hp}/{b_hp} HP.")
            self.target_priority = (assigned,)
            return
        self.target_priority = (CRYSTAL_A if a_hp >= b_hp else CRYSTAL_B,)

    async def maintain_shaman_skill_four(self, both_alive: bool) -> None:
        """``MaintainPhaseOneShamanSkillFour``: opening and Safeguard casts."""
        if not getattr(self, "_shaman_opening", False):
            self._shaman_opening = False
            self._shaman_safeguard = False
        if not self.safeguard_active:
            self._shaman_safeguard = False
        if (not both_alive or datetime.now() < self.taunt_target_until
                or not self.bot.player.canUseSkill(4)):
            return
        opening = not self._shaman_opening
        safeguard = (self._shaman_opening and self.safeguard_active
                     and not self._shaman_safeguard)
        if not opening and not safeguard:
            return
        if await self.cmd.use_skill(4, target_monsters=GRAMIEL):
            if opening:
                self._shaman_opening = True
                self.log("queued opening Phase 1 skill 4 on Gramiel.")
            else:
                self._shaman_safeguard = True
                self.log("queued Safeguard Phase 1 skill 4 on Gramiel.")

    # --------------------------------------------------------------- phase 2
    async def phase_two(self, attempt: int) -> str:
        """``FightPhaseTwo``: three nuke cycles, each with its healing hold."""
        normal = ((3, 4, 2, 1) if (self.slot == 1
                                   and self.options.composition == "Default")
                  else tuple(self.preset.skills))
        if self.is_shaman:
            normal = (1, 2, 3)
        self.skill_rotation = tuple(s for s in normal if s != 0)
        self.auto_attack_enabled = True
        self.suppress_rotation = False
        await self.start_skills(GRAMIEL, taunter=True)
        self.log("started Phase 2.")

        self._boss_seen = False
        grace_seen = False
        nuke_cycle = 1
        next_attack = 1
        owned_attack = self.phase_two_taunt_attack()
        state = "attacks"
        damage_hold = False
        shaman_blocked = False
        phase_detector = MarkerWatcher(
            self.bot, "ct", (GRAMIEL_CASTER, ATTACK_ANIM))

        while self.cmd.is_still_connected() and not self.sync.aborted():
            if self.should_reset(attempt):
                await self.finish_phase()
                phase_detector.stop()
                return "reset"

            if self.bot.player.ISDEAD:
                state_death = await self.wait_respawn(attempt)
                if state_death == "reset":
                    await self.finish_phase()
                    phase_detector.stop()
                    return "reset"
                if state_death == "stopped":
                    await self.finish_phase()
                    phase_detector.stop()
                    return "stopped"
                if not self.in_boss_room():
                    await self.jump_boss()

            if self.cmd.is_monster_alive(GRAMIEL):
                self._boss_seen = True
            elif self._boss_seen:
                await self.finish_phase()
                phase_detector.stop()
                self.log("confirmed Gramiel defeated.")
                return "completed"

            self.target_priority = (GRAMIEL,)

            if self.is_shaman:
                invulnerable = self.target_aura(INVULNERABLE)
                if invulnerable and not shaman_blocked:
                    shaman_blocked = True
                    self.skill_rotation = (1, 2)
                    self.log("playerOne disabled skill 3 while Gramiel has "
                             "Invulnerable.")
                elif not invulnerable and shaman_blocked:
                    shaman_blocked = False
                    self.skill_rotation = (1, 2, 3)
                    self.log("playerOne restored skill 3 after Gramiel's "
                             "Invulnerable ended.")

            if not grace_seen:
                if not self.target_aura(GRACE_GIVEN):
                    await self.cmd.sleep(self.poll_ms)
                    continue
                grace_seen = True
                if not phase_detector.start():
                    await self.finish_phase()
                    return "stopped"
                self.log("detected Grace Given and armed nuke cycle 1.")

            # Healing hold: stop damage and cast only the heal.
            if (not damage_hold
                    and (state == "attacks"
                         or (state == "liberator"
                             and not phase_detector.count >= 1))
                    and self.gramiel_hp_percent()
                    <= self.healing_hold_threshold(nuke_cycle)):
                if self.is_shaman or self.is_vdk:
                    self.suppress_rotation = True
                else:
                    self.skill_rotation = self.healing_hold_skills()
                self.auto_attack_enabled = False
                damage_hold = True
                self.log(f"started the nuke cycle {nuke_cycle} healing hold "
                         f"at {self.healing_hold_threshold(nuke_cycle)} "
                         f"percent Gramiel HP.")

            if state == "attacks":
                while phase_detector.count >= next_attack:
                    attack = next_attack
                    next_attack += 1
                    if attack == owned_attack:
                        self.request_taunt(GRAMIEL)
                        self.log(f"requested Gramiel taunt on nuke cycle "
                                 f"{nuke_cycle}, attack {attack}.")
                    if attack == 7:
                        phase_detector.stop()
                        phase_detector = MarkerWatcher(self.bot, "ct",
                                                       (LIBERATOR,))
                        if not phase_detector.start():
                            await self.finish_phase()
                            return "stopped"
                        state = "liberator"
                        self.log("reached attack 7 and started waiting for "
                                 "Liberator.")
                        break

            elif state == "liberator":
                if phase_detector.count >= 1:
                    if self.is_shaman or self.is_vdk:
                        self.suppress_rotation = False
                    else:
                        self.skill_rotation = tuple(s for s in normal
                                                    if s != 0)
                    damage_hold = False
                    self.auto_attack_enabled = True
                    self.log("detected Liberator.")
                    phase_detector.stop()
                    phase_detector = MarkerWatcher(
                        self.bot, "ct", (GRAMIEL_CASTER, CHARGE_TWO_ANIM))
                    if not phase_detector.start():
                        await self.finish_phase()
                        return "stopped"
                    state = "charge_two"

            elif state == "charge_two":
                if phase_detector.count >= 1:
                    self.log(f"entered nuke cycle {nuke_cycle} "
                             f"{'protected' if self.self_aura(INVULNERABLE) else 'without'} "
                             f"Invulnerable.")
                    phase_detector.stop()
                    phase_detector = MarkerWatcher(
                        self.bot, "ct",
                        (GRAMIEL_CASTER, CHARGE_ATTACK_TWO_ANIM))
                    if not phase_detector.start():
                        await self.finish_phase()
                        return "stopped"
                    state = "charge_attack_two"

            elif state == "charge_attack_two":
                if phase_detector.count >= 1:
                    await self.cmd.sleep(self.poll_ms)
                    phase_detector.stop()
                    self.log(f"handled ChargeAttack2 for nuke cycle "
                             f"{nuke_cycle}.")
                    state = "invulnerable_end"

            elif state == "invulnerable_end":
                if self.self_aura(INVULNERABLE) is None:
                    self.log(f"detected Invulnerable ended after nuke cycle "
                             f"{nuke_cycle}.")
                    if nuke_cycle >= NUKE_CYCLES:
                        self.skill_rotation = tuple(s for s in normal
                                                    if s != 0)
                        self.auto_attack_enabled = True
                        state = "finished"
                        self.log("completed all three Gramiel nuke cycles.")
                        break
                    nuke_cycle += 1
                    next_attack = 1
                    self.skill_rotation = tuple(s for s in normal if s != 0)
                    self.auto_attack_enabled = True
                    phase_detector.stop()
                    phase_detector = MarkerWatcher(
                        self.bot, "ct", (GRAMIEL_CASTER, ATTACK_ANIM))
                    if not phase_detector.start():
                        await self.finish_phase()
                        return "stopped"
                    state = "attacks"
                    self.log(f"armed Gramiel nuke cycle {nuke_cycle}.")

            await self.cmd.sleep(self.poll_ms)

        phase_detector.stop()
        await self.finish_phase()
        return "stopped"

    @staticmethod
    def healing_hold_threshold(cycle: int) -> int:
        return HEAL_HOLD_THRESHOLDS.get(cycle, 15)

    async def finish_phase(self) -> None:
        self.suppress_rotation = False
        self.auto_attack_enabled = True
        await self.stop_skills()


async def main(cmd, slot: int = 1, options: Optional[UltraOptions] = None) -> None:
    """Run one pane standalone (``python -m bot.ultra.v2.weeklies.gramiel``)."""
    runner = UltraGramiel(cmd, options or UltraOptions(), slot)
    okay = await runner.run()
    if not okay and runner.aborted:
        cmd.bot.log(f"[V2 Gramiel] slot {slot} stopped: {runner.aborted}")
