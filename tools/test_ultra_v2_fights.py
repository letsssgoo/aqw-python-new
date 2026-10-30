"""Ultra V2 dailies: Ezrajal, Engineer, Tyndarius and the shared pull rules.

    python tools/test_ultra_v2_fights.py
"""
from _ultra_v2_support import *  # noqa: F401,F403
from _ultra_v2_support import (check, finish, run, _StubBot,  # noqa: F401
                               _StubCommand)

# --- Ezrajal ---------------------------------------------------------------
from bot.ultra.v2.dailies import ezrajal  # noqa: E402
from bot.ultra.v2.registry import ORDER as V2_ORDER, REGISTRY as V2_REGISTRY  # noqa: E402

check("ezrajal: quest 8152 in ultraezrajal",
      (ezrajal.SPEC.quest, ezrajal.SPEC.map), (8152, "ultraezrajal"))
check("ezrajal: the boss is id.1", ezrajal.SPEC.monster_id, 1)
check("ezrajal: Skip Mana Lock is on by default",
      ezrajal.SPEC.extra_options[0]["default"], True)
check("ezrajal: it is registered", "ezrajal" in V2_ORDER, True)
check("ezrajal: the registry has a runner", sorted(V2_REGISTRY),
      ["drago", "drakath", "engineer", "ezrajal", "nulgath", "tyndarius",
       "warden"])
ezr = ezrajal.UltraEzrajal(_StubCommand(), options.UltraOptions(
    players=("a", "b", "c", "d")), 1)
check("ezrajal: the rotation respects the counter attack",
      ezr.respect_counter_attack, True)
check("ezrajal: its schema carries the mana-lock toggle",
      [f["key"] for f in options.schema(ezrajal.SPEC)][-1], "skip_mana_lock")
check("ezrajal: the default form disables the mana lock",
      ezr.skip_mana_lock, True)
off = ezrajal.UltraEzrajal(_StubCommand(), options.UltraOptions(
    players=("a", "b", "c", "d"), extras={"skip_mana_lock": False}), 1)
check("ezrajal: asking for the mana lock is honoured as a value",
      off.skip_mana_lock, False)
check("ezrajal: a wipe needs two panes, same as every ultra",
      ezr.should_reset(1), False)

# --- Engineer -------------------------------------------------------------
from bot.ultra.v2.dailies import engineer  # noqa: E402

check("engineer: quest 8154 in ultraengineer",
      (engineer.SPEC.quest, engineer.SPEC.map), (8154, "ultraengineer"))
check("engineer: the main boss is id.3", engineer.SPEC.monster_id, 3)
check("engineer: adds come first, in the reference's order",
      (engineer.FIRST_TARGET, engineer.SECOND_TARGET),
      ("Attack Drone", "Defense Drone"))
check("engineer: it is registered", V2_ORDER,
      ("warden", "ezrajal", "engineer", "tyndarius", "drakath", "nulgath",
       "drago"))
eng = engineer.UltraEngineer(_StubCommand(), options.UltraOptions(
    players=("a", "b", "c", "d")), 1)
check("engineer: the engine tries the adds before the boss",
      eng.target_priority, ("Attack Drone", "Defense Drone", "id.3"))
check("engineer: it uses the standard composition",
      eng.preset.cls, "Legion Revenant")

# Every V2 daily fights v1's literal rotation, skill 0 (auto attack) included.
check("rotation: auto attack is separate from the rotation",
      warden.build(_StubCommand(), options.UltraOptions(
          players=("a", "b", "c", "d")), 1).rotation, (1, 2, 3, 4))
check("rotation: ezrajal starts on skill 0",
      ezrajal.UltraEzrajal(_StubCommand(), options.UltraOptions(
          players=("a", "b", "c", "d")), 1).rotation, (1, 2, 3, 4))
check("rotation: engineer's rotation has no 0", eng.rotation[0], 1)
# VDK (strict) and KE (kings_echo) must cast skill 0 too, like every v1 daily.
vdk = warden.build(_StubCommand(), options.UltraOptions(
    players=("a", "b", "c", "d"), composition="Reliable"), 1)
ke = warden.build(_StubCommand(), options.UltraOptions(
    players=("a", "b", "c", "d"), composition="Stable"), 1)
check("rotation: Verus DoomKnight keeps the literal 0", (0 in vdk.rotation, vdk.preset.mode), (False, "strict"))
check("rotation: King's Echo keeps the literal 0", (0 in ke.rotation, ke.preset.mode), (False, "kings_echo"))

# Skill 0 is mandatory: a module that leaves it out gets it prepended.
class _NoZero(warden.UltraWarden):
    def __init__(self, cmd, options, slot=1):
        super().__init__(cmd, options, slot)
        self.skill_rotation = (1, 2, 3)


forced = _NoZero(_StubCommand(), options.UltraOptions(
    players=("a", "b", "c", "d")), 1)
check("rotation: skill 0 never appears in the rotation",
      (0 in forced.rotation, forced.rotation), (False, (1, 2, 3)))

check("rotation: all three keep v1's string minus the auto attack",
      [warden.build(_StubCommand(), options.UltraOptions(
           players=("a", "b", "c", "d")), 1).rotation,
       ezrajal.UltraEzrajal(_StubCommand(), options.UltraOptions(
           players=("a", "b", "c", "d")), 1).rotation,
       eng.rotation],
      [(1, 2, 3, 4)] * 3)

# Heal check follows v1's ``support_slots`` default (slots 3 and 4), and the
# heal **skill** is per class: AP and LoO cast 2, Legion Revenant casts 3.
check("heal: v1's support slots are 3 and 4", eng.heal_slots, (3, 4))
check("heal: ArchPaladin heals with 2",
      engineer.UltraEngineer(_StubCommand(), options.UltraOptions(
          players=("a", "b", "c", "d")), 3).heal_skill, 2)
lr_heal = warden.build(_StubCommand(), options.UltraOptions(
    players=("a", "b", "c", "d")), 1)
check("heal: Legion Revenant heals with 3, not 2", lr_heal.heal_skill, 3)
sc_heal = warden.build(_StubCommand(), options.UltraOptions(
    players=("a", "b", "c", "d")), 2)
check("heal: StoneCrusher has no listed heal, so none is cast",
      sc_heal.heal_skill, None)

# --- Tyndarius (v1: rotation 0 1 2 0 3 4 5, crystals before the boss) ------
from bot.ultra.v2.dailies import tyndarius  # noqa: E402

check("tyndarius: quest 8245 in ultratyndarius",
      (tyndarius.SPEC.quest, tyndarius.SPEC.map), (8245, "ultratyndarius"))
check("tyndarius: the boss is id.2", tyndarius.BOSS, "id.2")
check("tyndarius: registered after the LW port",
      "tyndarius" in V2_ORDER, True)
ty1 = tyndarius.UltraTyndarius(_StubCommand(), options.UltraOptions(
    players=("a", "b", "c", "d")), 1)
ty2 = tyndarius.UltraTyndarius(_StubCommand(), options.UltraOptions(
    players=("a", "b", "c", "d")), 2)
ty3 = tyndarius.UltraTyndarius(_StubCommand(), options.UltraOptions(
    players=("a", "b", "c", "d")), 3)
check("tyndarius: v1's rotation minus the auto attack", ty1.rotation,
      (1, 2, 3, 4))
check("tyndarius: slot 1 keeps the first add, then the second, then the boss",
      ty1.add_priority(), ("id.1", "id.3", "id.2"))
check("tyndarius: slot 2 keeps the second add, then the first, then the boss",
      ty2.add_priority(), ("id.3", "id.1", "id.2"))
check("tyndarius: with nothing alive the slot still names the boss",
      ty1.priority_target(), "id.2")
# IsTaunterRole arms every pane on Default/Reliable (each carries the scroll);
# this is what decides who drops the combat potion, not who casts taunt 5.
check("tyndarius: Default arms every pane as a taunter",
      (ty1.is_taunter, ty3.is_taunter), (True, True))
check("tyndarius: the ArchPaladin slot is 3", ty3.is_arch_paladin, True)
loo = tyndarius.UltraTyndarius(_StubCommand(), options.UltraOptions(
    players=("a", "b", "c", "d")), 4)
check("tyndarius: Lord of Order holds its heal and lifts it at 75",
      (loo.spam_heal, loo.heal_below, loo.heal_gap_ms), (False, 75, 0))
check("tyndarius: and skill 2 is not in the Lord of Order rotation",
      2 in loo.rotation, False)
check("tyndarius: ArchPaladin keeps its heal for under 60, no extra gap",
      (ty3.spam_heal, ty3.heal_below, ty3.heal_gap_ms), (False, 60, 0))
check("tyndarius: and skill 2 is not in the ArchPaladin rotation",
      2 in ty3.rotation, False)
# Potions, scroll and prebuff belong to the safe room: the party must not move
# to the boss cell until they are done (LW's PrepareSafeRoom -> FIGHT_READY ->
# jump).  The reference's GenericPrebuff is skill 3, 2, 1.
class _OrderCommand(_StubCommand):
    def __init__(self):
        super().__init__()
        self.events = []
        self.bot.player.CELL = "Boss"      # the push lands in the boss cell

    async def use_skill(self, slot, **kwargs):
        self.events.append(("skill", slot))
        return True

    async def jump_cell(self, cell, pad):
        self.events.append(("jump", str(cell)))

    async def join_map(self, name, room=None):
        self.events.append(("join", name))

    async def sleep(self, ms):
        # Real time, not zero: a skill loop that never waits starves the loop
        # it shares with the test, so the cancel that ends it never runs.
        await asyncio.sleep(0.001)

    async def has_item(self, name, qty=1, isTemp=False):
        return True

    async def equip_scroll(self, name):
        self.events.append(("scroll", name))
        return True


_order = _OrderCommand()
_prebuff = tyndarius.UltraTyndarius(_order, options.UltraOptions(
    players=("a", "b", "c", "d"), use_potions=False), 1)
run(_prebuff.fight_attempts())
_skills = [value for kind, value in _order.events if kind == "skill"]
_boss_jumps = [index for index, (kind, value) in enumerate(_order.events)
               if kind == "jump" and value == "Boss"]
check("tyndarius: GenericPrebuff is 3, 2, 1", _skills[:3], [3, 2, 1])
# A dead add must not end the engine: it has to idle and pick the next target
# (or the same one when it respawns), like the fight loop expects.
class _LoopCommand(_StubCommand):
    def __init__(self):
        super().__init__()
        self.alive = set()
        self.casts = []
        self.bot.player.canUseSkill = lambda slot: True
        self.bot.player.SKILLS = [dict(cd=0, tgt="h", tgtMax=1, anim="")
                                  for _ in range(6)]
        self.bot.player.getAura = lambda name: None
        self.bot.player.MANA = 100
        self.bot.player.MAX_MP = 100
        self.bot.player.CURRENT_HP = 100
        self.bot.player.MAX_HP = 100

    def is_monster_alive(self, target="*"):
        return str(target) in self.alive

    async def use_skill(self, slot, **kwargs):
        self.casts.append(slot)
        return True

    async def sleep(self, ms):
        await asyncio.sleep(0.001)


async def _engine_survives():
    cmd = _LoopCommand()
    runner = warden.build(cmd, options.UltraOptions(
        players=("a", "b", "c", "d")), 1)
    await runner.start_skills("id.3")
    await asyncio.sleep(0.4)
    stayed_alive = not runner._skill_task.done()
    cmd.alive = {"id.3"}
    await asyncio.sleep(0.6)
    acted = bool(cmd.casts)
    await runner.stop_skills()
    return stayed_alive, acted


check("engine: no target idles instead of ending the skill loop",
      run(_engine_survives()), (True, True))
check("tyndarius: the buffs land before the jump to the boss",
      bool(_boss_jumps) and _boss_jumps[0] > 2, True)

# Skill 0 is mandatory in every preset, and a strict list still walks only the
# real skills: the auto attack has its own tick.
check("presets: the new Chaos Slayer list carries skill 0",
      presets.preset_for_class("Chaos Slayer Berserker").skills[0], 0)
check("presets: the new Dragon of Time list carries skill 0",
      presets.preset_for_class("Dragon of Time").skills[0], 0)
# Skill 0 is pressed even while a heal is due: the auto attack has its own tick
# and never queues behind another skill.
class _HealOrderCommand(_StubCommand):
    def __init__(self):
        super().__init__()
        self.casts = []
        self.bot.player.canUseSkill = lambda slot: True
        self.bot.player.SKILLS = [dict(cd=0, tgt="h", tgtMax=1, anim="")
                                  for _ in range(6)]
        self.bot.player.getAura = lambda name: None
        low = type("A", (), {"str_username": "ally", "int_hp": 300,
                             "int_hp_max": 1000,
                             "is_hp_below": lambda self, pct: True})()
        self.bot.player_in_area = [low]

    def is_monster_alive(self, target="*"):
        return True

    async def use_skill(self, slot, **kwargs):
        self.casts.append(slot)
        return True

    async def sleep(self, ms):
        await asyncio.sleep(0.001)


async def _auto_before_heal():
    cmd = _HealOrderCommand()
    runner = tyndarius.UltraTyndarius(cmd, options.UltraOptions(
        players=("a", "b", "c", "d")), 3)      # ArchPaladin: heal on 2
    await runner.start_skills("id.2")
    await asyncio.sleep(0.05)
    await runner.stop_skills()
    return cmd.casts[:2]


check("bill: the auto attack fires before the heal",
      run(_auto_before_heal()), [0, 2])

check("presets: strict mode never walks skill 0",
      presets.preset_for_class("Dragon of Time").skills.count(0), 1)

# IsTaunterRole arms every pane on Default/Reliable (each carries the scroll);
# this decides who drops the combat potion, not who casts taunt 5.
check("tyndarius/default: every pane carries the scroll",
      [tyndarius.UltraTyndarius(_StubCommand(), options.UltraOptions(
          players=("a", "b", "c", "d")), slot).is_taunter
       for slot in (1, 2, 3, 4)],
      [True, True, True, True])
check("tyndarius: no Fast column without the Arcana Invoker engine",
      "Fast" in options.compositions("tyndarius"), False)
check("nulgath: no Fast column without the Arcana Invoker engine",
      "Fast" in options.compositions("nulgath"), False)

check("tyndarius: the party heals below 60",
      (ty1.heal_below, ty1.heal_slots), (60, ()))
check("tyndarius: the Lord of Order lifts its guard to 75",
      loo.heal_below, 75)
check("tyndarius: the ArchPaladin stays at 60", ty3.heal_below, 60)
check("tyndarius: the other panes keep 60", ty2.heal_below, 60)
# The script puts Valiance on its Lord of Order instead of the preset's Awe
# Blast, and that stays inside Tyndarius -- the base preset is untouched.
check("tyndarius: Lord of Order wears Valiance in every composition",
      [presets.preset_for("tyndarius", composition, 4).weapon
       for composition in ("Default", "Stable", "Reliable")],
      ["Valiance"] * 3)
check("tyndarius: the base Lord of Order preset still uses Awe Blast",
      presets.preset_for_class("Lord of Order").weapon, "Awe Blast")
check("tyndarius: another ultra keeps the base weapon",
      presets.preset_for("warden", "Stable", 4).weapon, "Awe Blast")

# --- the heal guard reads live HP, and only the living ---------------------
# ``player_in_area``'s self entry is written once when the map loads, so a
# healer that trusted it never saw itself drop; a dead member at 0 HP is not
# wounded, and treating it as one spent the heal away from the party.
class _AreaPlayer:
    def __init__(self, name, hp, hp_max):
        self.str_username = name
        self.int_hp = hp
        self.int_hp_max = hp_max

    def is_hp_below(self, percent):
        if self.int_hp_max <= 0:
            return False
        return (self.int_hp / self.int_hp_max) * 100 < percent


class _HealBot:
    def __init__(self, user, hp, hp_max, area):
        self.player = type("_P", (), {"USER": user, "CURRENT_HP": hp,
                                      "MAX_HP": hp_max})()
        self.player_in_area = area


class _HealCommand(_StubCommand):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot


def _healer(hp):
    area = [_AreaPlayer("ap_player", hp, 1000),   # stale self entry: full HP
            _AreaPlayer("low_ally", 300, 1000),
            _AreaPlayer("dead_ally", 0, 1000),
            _AreaPlayer("fine_ally", 900, 1000)]
    bot = _HealBot("ap_player", hp, 1000, area)
    runner = tyndarius.UltraTyndarius(_HealCommand(bot), options.UltraOptions(
        players=("a", "b", "c", "d")), 4)
    return runner


check("heal: a wounded ally is found", _healer(1000).wounded_allies(),
      ["low_ally"])
check("heal: the pane's own live HP counts, not the stale area entry",
      _healer(500).wounded_allies(), ["ap_player", "low_ally"])
check("heal: a dead member is not a heal target",
      "dead_ally" in _healer(1000).wounded_allies(), False)
check("heal: nobody wounded means no cast", _healer(1000).wounded_allies() != [],
      True)

# RequestImmediateTaunt only succeeds when skill 5 is ready (LW returns false).
class _TauntCommand(_StubCommand):
    def __init__(self, ready):
        super().__init__()
        self.bot.player.canUseSkill = lambda slot: ready

    def is_monster_alive(self, target="*"):
        return True


blocked = tyndarius.UltraTyndarius(_TauntCommand(False), options.UltraOptions(
    players=("a", "b", "c", "d")), 1)
check("tyndarius: a taunt without skill 5 is refused",
      run(blocked.immediate_taunt("id.1")), False)
allowed = tyndarius.UltraTyndarius(_TauntCommand(True), options.UltraOptions(
    players=("a", "b", "c", "d")), 1)
check("tyndarius: a ready taunt is requested without repointing the rotation",
      (run(allowed.immediate_taunt("id.1")), allowed.target_priority),
      (True, ()))

# Each taunter holds its own add and moves on only when that add is down.
class _AddCommand(_StubCommand):
    def __init__(self, alive):
        super().__init__()
        self.alive = set(alive)

    def is_monster_alive(self, target="*"):
        return str(target) in self.alive


def _taunter(slot, alive):
    cmd = _AddCommand(alive)
    runner = tyndarius.UltraTyndarius(cmd, options.UltraOptions(
        players=("a", "b", "c", "d")), slot)
    runner.aim_at_add()
    return runner


_first = _taunter(1, {"id.1", "id.3", "id.2"})
check("tyndarius: slot 1 opens on id.1", _first.priority_target(), "id.1")
_first.cmd.alive = {"id.3", "id.2"}
check("tyndarius: id.1 down, slot 1 takes id.3", _first.priority_target(),
      "id.3")
_first.cmd.alive = {"id.2"}
check("tyndarius: both adds down, slot 1 attacks the boss",
      _first.priority_target(), "id.2")
_second = _taunter(2, {"id.1", "id.3", "id.2"})
check("tyndarius: slot 2 opens on id.3", _second.priority_target(), "id.3")
_second.cmd.alive = {"id.1", "id.2"}
check("tyndarius: id.3 down, slot 2 takes id.1", _second.priority_target(),
      "id.1")
check("tyndarius: the pull aims each taunter at its own add",
      [runner.target_priority for runner in
       (_taunter(1, {"id.1", "id.3"}), _taunter(2, {"id.1", "id.3"}))],
      [("id.1", "id.3", "id.2"), ("id.3", "id.1", "id.2")])

# A boss that never appears must never be reported as defeated: the timeout
# before the pull is the only place that can tell "not here" from "already dead".
never = warden.build(_StubCommand(), options.UltraOptions(
    players=("a", "b", "c", "d")), 1)
check("pull: a boss that never spawns is not a win",
      run(never.fight(1)), "stopped")
check("pull: and it says why",
      "never appeared" in never.aborted, True)
never_eng = engineer.UltraEngineer(_StubCommand(), options.UltraOptions(
    players=("a", "b", "c", "d")), 1)
check("pull: the same for Engineer", run(never_eng.fight(1)), "stopped")
check("pull: Engineer names its own boss cell",
      "r2/Left" in never_eng.aborted, True)

# --- the prerequisite probe is gone; the turn-in decides -------------------
gate = warden.build(_StubCommand(), options.UltraOptions(
    players=("a", "b", "c", "d")), 1)
calls = {"probe": 0}

async def _probe(quest_id, timeout_sec=3.0):
    calls["probe"] += 1
    return False        # the answer the engine cannot trust

gate.cmd.is_completed_before = _probe
check("gate: no prerequisite probe", run(gate.validate_access()), True)
check("gate: and it never asked", calls["probe"], 0)

# A won fight with a still-short quest pulls the party again, per retry.
attempts = {"fight": 0, "finish": 0, "results": []}
retry = warden.build(_StubCommand(), options.UltraOptions(
    players=("a", "b", "c", "d"), retries=2), 1)


async def _fight():
    attempts["fight"] += 1
    return True


async def _finish():
    attempts["finish"] += 1
    return attempts["finish"] > 1      # turnable on the second round


retry.fight_attempts = _fight
retry.finish_quest = _finish
check("turn-in: a short drop pulls again", run(retry.defeat_and_turn_in()), True)
check("turn-in: two pulls, two turn-in tries",
      (attempts["fight"], attempts["finish"]), (2, 2))

stuck = warden.build(_StubCommand(), options.UltraOptions(
    players=("a", "b", "c", "d"), retries=2), 1)
tries = {"fight": 0}


async def _fight2():
    tries["fight"] += 1
    return True


async def _never():
    return False


stuck.fight_attempts = _fight2
stuck.finish_quest = _never
check("turn-in: it gives up after the retries",
      run(stuck.defeat_and_turn_in()), False)
check("turn-in: one pull per retry", tries["fight"], 2)
check("turn-in: and it says why", "never became turnable" in stuck.aborted, True)

# Items in hand but the server refused: no more pulls, just stop.
ready = warden.build(_StubCommand(), options.UltraOptions(
    players=("a", "b", "c", "d"), retries=3), 1)
ready.cmd.turnin_ready = True
pulls = {"n": 0}


async def _fight3():
    pulls["n"] += 1
    return True


ready.fight_attempts = _fight3
ready.finish_quest = _never
check("turn-in: a refusal with the items in hand is not retried",
      run(ready.defeat_and_turn_in()), False)
check("turn-in: exactly one pull", pulls["n"], 1)

finish('ultra v2 fight tests')
