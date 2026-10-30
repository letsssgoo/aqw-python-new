"""Ultra V2: options, presets, potions, sync and the Warden rules.

    python tools/test_ultra_v2.py

Everything here is offline: the engine's packet layer is stubbed, so the suite
pins the parts that must not drift -- which compositions exist, which class each
slot wears, the potion recipe table, the slot-5 scroll/potion rule, the wipeout
threshold, and the retry cap.
"""
import asyncio
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bot.ultra.v2 import enhancements, options, potions, presets, scrolls, sync  # noqa: E402
from bot.ultra.v2.core import V2Core, WIPE_DEATHS  # noqa: E402
from bot.ultra.v2.dailies import warden  # noqa: E402

failures = []
passed = 0


def check(label, got, want):
    global passed
    if got == want:
        passed += 1
    else:
        failures.append(f"{label}: got {got!r}, want {want!r}")


def run(coro):
    return asyncio.run(coro)


class _StubBot:
    """Just enough Bot to construct a runner: no socket, no packets."""

    def __init__(self):
        self.logs = []
        self.player = type("P", (), {
            "LEVEL": 100, "CELL": "Enter", "PAD": "Spawn", "ISDEAD": False,
            "AURAS": [], "MANA": 100, "MAX_MP": 100, "CURRENT_HP": 100,
            "MAX_HP": 100, "GOLD": 0,
        })()

    def log(self, *args):
        self.logs.append(" ".join(map(str, args)))


class _StubCommand:
    def __init__(self):
        self.bot = _StubBot()

    def is_still_connected(self):
        return True

    def is_monster_alive(self, target="*"):
        return False          # nothing is in the cell: the boss never appeared

    async def sleep(self, ms):
        return None

    def is_in_inventory_or_bank(self, name, qty=1, operator=">=", isTemp=False):
        return True

    def can_turnin_quest(self, quest_id):
        # Default stub: the drop is still missing, so a retry is expected.
        return getattr(self, "turnin_ready", False)


# --- options ---------------------------------------------------------------
for ultra in ("warden", "ezrajal", "engineer", "tyndarius", "drakath", "drago",
              "nulgath", "dage", "darkon", "gramiel", "speaker"):
    table = options.compositions(ultra)
    expected = (["Default", "Reliable"] if ultra in ("gramiel", "speaker")
                else ["Default", "Reliable", "Stable"])
    check(f"{ultra}: ported compositions", sorted(table), expected)
    for name, slots in table.items():
        check(f"{ultra}/{name}: four slots", len(slots), 4)
        check(f"{ultra}/{name}: slot 2 is StoneCrusher", slots[1], "StoneCrusher")
        check(f"{ultra}/{name}: slot 4 is Lord of Order", slots[3], "Lord of Order")

check("default: slot 1 is Legion Revenant",
      options.compositions("warden")["Default"][0], "Legion Revenant")
check("stable: slot 1 is King's Echo",
      options.compositions("warden")["Stable"][0], "King's Echo")
check("reliable: slot 1 is Verus DoomKnight",
      options.compositions("warden")["Reliable"][0], "Verus DoomKnight")

line = options.composition_tooltip("warden")
check("tooltip: one line per composition", len(line.splitlines()), 3)
check("tooltip: lists the short names", "Default: LR / SC / AP / LOO" in line, True)
check("tooltip: speaker has no Stable",
      "Stable" in options.composition_tooltip("speaker"), False)

spec = warden.SPEC
check("schema: has the composition dropdown",
      [f["key"] for f in options.schema(spec)][:4],
      ["players", "composition", "private_room", "use_potions"])
check("schema: retries are 1..5",
      [c["value"] for f in options.schema(spec) if f["key"] == "retries"
       for c in f["choices"]], [1, 2, 3, 4, 5])

good = options.UltraOptions(players=("a", "b", "c", "d"))
check("validate: a filled form passes", options.validate(spec, good), [])
check("validate: an empty slot is named",
      any("slot 1" in problem for problem in
          options.validate(spec, options.UltraOptions())), True)
check("validate: retries outside 1..5 is refused",
      any("retries" in problem for problem in
          options.validate(spec, options.UltraOptions(
              players=("a", "b", "c", "d"), retries=6))), True)
check("validate: a private room below 1001 is refused",
      any("private room" in problem for problem in
          options.validate(spec, options.UltraOptions(
              players=("a", "b", "c", "d"), private_room=50))), True)
check("validate: Pay2Win is not ported",
      any("not ported" in problem for problem in
          options.validate(spec, options.UltraOptions(
              players=("a", "b", "c", "d"), composition="Pay2Win"))), True)
check("options: round-trips through a dict",
      options.UltraOptions.from_dict(good.to_dict()), good)

# --- presets ---------------------------------------------------------------
check("preset: LR keeps the reference rotation",
      presets.preset_for("warden", "Default", 1).skills, (3, 4, 2, 1))
check("preset: LR mode is simple",
      presets.preset_for("warden", "Default", 1).mode, presets.SIMPLE)
check("preset: King's Echo uses its own engine",
      presets.preset_for("warden", "Stable", 1).mode, presets.KINGS_ECHO)
check("preset: Verus DoomKnight is strict",
      presets.preset_for("warden", "Reliable", 1).mode, presets.STRICT)
check("preset: VDK rotation length", len(presets.VDK_ROTATION), 21)
check("preset: stonecrusher wears Absolution on the cape",
      presets.preset_for("warden", "Default", 2).cape, "Absolution")
check("preset: lord of order uses Awe Blast",
      presets.preset_for("warden", "Default", 4).weapon, "Awe Blast")
try:
    presets.preset_for("warden", "Pay2Win", 1)
    raised = False
except KeyError:
    raised = True
check("preset: Pay2Win raises instead of guessing", raised, True)

# --- per-ultra differences (each script has its own GetClassPreset) --------
check("dage: slot 2 fights on StoneCrusher 2,4,1",
      presets.preset_for("dage", "Default", 2).skills, (2, 4, 1))
check("dage: slot 3 fights on ArchPaladin 3,1,4",
      presets.preset_for("dage", "Default", 3).skills, (3, 1, 4))
check("dage: slot 4 fights on Lord of Order 3,1,4",
      presets.preset_for("dage", "Default", 4).skills, (3, 1, 4))
check("warden: slot 2 keeps the preset rotation",
      presets.preset_for("warden", "Default", 2).skills, (3, 2, 4, 1))
check("darkon: Legion Revenant wears Penitence",
      presets.preset_for("darkon", "Default", 1).cape, "Penitence")
check("darkon: Lord of Order wears Absolution",
      presets.preset_for("darkon", "Default", 4).cape, "Absolution")
check("darkon: Lord of Order fights 3,1",
      presets.preset_for("darkon", "Default", 4).skills, (3, 1))
check("darkon: ArchPaladin fights 3,1,4",
      presets.preset_for("darkon", "Default", 3).skills, (3, 1, 4))
check("gramiel: Legion Revenant fights 3,4,2",
      presets.preset_for("gramiel", "Default", 1).skills, (3, 4, 2))
check("gramiel: ArchPaladin wears Penitence",
      presets.preset_for("gramiel", "Default", 3).cape, "Penitence")
check("gramiel: Reliable slot 1 is Verus DoomKnight",
      presets.preset_for("gramiel", "Reliable", 1).cls, "Verus DoomKnight")
check("speaker: StoneCrusher drinks the Divine Elixir",
      presets.preset_for("speaker", "Default", 2).elixir, "Divine Elixir")
check("speaker: Legion Revenant wears no helm",
      presets.preset_for("speaker", "Default", 1).helm, None)
check("speaker: ArchPaladin fights 2,1",
      presets.preset_for("speaker", "Default", 3).skills, (2, 1))
check("speaker: Lord of Order fights 2,3,1",
      presets.preset_for("speaker", "Default", 4).skills, (2, 3, 1))
check("speaker: brute force restores the preset rotation",
      presets.preset_for("speaker", "Default", 3,
                         {"brute_force": True}).skills, (3, 2, 1, 4))
check("ezrajal: Stable's King's Echo wears no cape",
      presets.preset_for("ezrajal", "Stable", 1).cape, None)
check("warden: Stable's King's Echo keeps its cape",
      presets.preset_for("warden", "Stable", 1).cape, "Vainglory")
check("tooltip: gramiel lists two rows",
      len(options.composition_tooltip("gramiel").splitlines()), 2)

# --- base (class-slot) enhancement resolution ------------------------------
# Skua resolves the base enhancement by *type* through fixed shop ids, not by a
# registry name -- this is the table from ``GetNormalEnhancementShop``.
check("base: Wizard uses shop 765 at level 50+",
      enhancements.NORMAL_ENHANCEMENT_SHOPS["Wizard"], (765, 144))
check("base: Lucky uses shop 763",
      enhancements.NORMAL_ENHANCEMENT_SHOPS["Lucky"], (763, 147))
check("base: the seven types the presets use",
      sorted(enhancements.NORMAL_ENHANCEMENT_SHOPS),
      ["Fighter", "Healer", "Hybrid", "Lucky", "SpellBreaker", "Thief",
       "Wizard"])
check("base: the class slot codes", enhancements.CLASS_SLOTS, ("ar", "co"))

# Skua's rule for the class slot: equip the class, look at what is socketed,
# and enhance only when it is different.
wizard = enhancements.best_base("Wizard", 100)
check("base: Wizard resolves to the level-100 class tier",
      (wizard.name, wizard.level, wizard.shop_id),
      ("Wizard Armor Enhancement", 100, 765))
check("base: a non-member gets the highest regular tier at or under 80",
      enhancements.best_base("Wizard", 80).level, 78)
check("base: a member gets the upgrade tier at level 80",
      enhancements.best_base("Wizard", 80, is_member=True).level, 80)
check("base: the upgrade tier is the rarity-6 one",
      enhancements.best_base("Wizard", 80, is_member=True).rarity, 6)
check("base: a non-member never gets a bUpg tier",
      any(row.is_upgrade for row in [enhancements.best_base("Wizard", 100)]),
      False)


class _ClassCommand:
    def __init__(self, enh_id=0):
        self.calls = []
        self.logs = []
        item = type("I", (), {
            "item_id": 5555, "item_name": "legion revenant", "is_equipped": True,
            "s_es": "ar", "level": 100, "enh_id": enh_id,
            "enh_pattern_id": wizard.pattern_id if enh_id else 0,
            "enh_rarity": wizard.rarity if enh_id else 0,
        })()
        self.player = type("P", (), {"INVENTORY": [item], "LEVEL": 100})()
        self.bot = type("B", (), {"player": self.player,
                                  "log": lambda _s, line: self.logs.append(line)})()
        self.maps = []

    def is_not_in_map(self, name):
        self.calls.append(("join-check", name))
        return True

    async def join_map(self, name, room=None):
        self.maps.append(name)
        self.calls.append(("join", name))

    async def ensure_load_shop(self, shop_id):
        self.calls.append(("shop", shop_id))
        return True

    async def enhance_item(self, item_id, enh_item_id, shop_id):
        self.calls.append(("enhance", item_id, enh_item_id, shop_id))


already = _ClassCommand(enh_id=wizard.item_id)
check("base: gear that already carries it is left alone",
      run(enhancements._apply_base(already, "Wizard")), True)
check("base: and no packet is sent", already.calls, [])

different = _ClassCommand(enh_id=0)
check("base: gear with a different enhancement is enhanced",
      run(enhancements._apply_base(different, "Wizard")), True)
check("base: the class item and tier are named in the packet",
      different.calls, [("join-check", "battleontown"),
                        ("join", "battleontown"),
                        ("shop", 765),
                        ("enhance", 5555, wizard.item_id, 765)])

tiered = _ClassCommand(enh_id=0)
tiered.player.LEVEL = 80      # tiers follow the character level, not the item's
check("base: the tier follows the character level",
      run(enhancements._apply_base(tiered, "Wizard")), True)
check("base: level 80 gets the level-80 tier",
      tiered.calls[-1][2], enhancements.best_base("Wizard", 80).item_id)

# --- telemetry and cooldown pacing -----------------------------------------
class _TelemetryStub:
    def __init__(self):
        self.events = []

    def write(self, kind, **fields):
        self.events.append((kind, fields))


tele = _TelemetryStub()
tele_bot = _StubCommand()
tele_bot.bot.telemetry = tele
tele_runner = warden.build(tele_bot, options.UltraOptions(
    players=("a", "b", "c", "d")), 2)
tele_runner.abort("test stop")
check("telemetry: an abort is reported",
      [kind for kind, _ in tele.events], ["abort"])
check("telemetry: carrying the ultra, slot and class",
      tele.events[0][1].get("slot"), 2)

# Cooldowns are a *display*: the same server deadlines the solo menu draws.
from app import build_hub_app as hub  # noqa: E402  (imports pywebview lazily)

class _Skill:
    def __init__(self, seconds):
        from datetime import datetime, timedelta
        self.next_use = None if seconds is None else datetime.now() + \
            timedelta(seconds=seconds)


class _Player:
    SKILLS = [_Skill(None), _Skill(2.5), _Skill(0)]


readout = hub._skill_cooldowns(_Player())
check("ui cooldown: one row per skill slot", [row["slot"] for row in readout],
      [0, 1, 2])
check("ui cooldown: a ready slot reads 0", readout[0]["ready_in"], 0)
check("ui cooldown: a busy slot reports the wait",
      2000 < readout[1]["ready_in"] <= 2600, True)


# --- which monster the pane is hitting -------------------------------------
# The menu lists the cell's monsters; the fight also has to say which one it is
# attacking *now*, so a retarget (add -> boss) is visible instead of guessed.
class _Mon:
    def __init__(self, mid, name, hp, hp_max):
        self.mon_map_id = mid
        self.mon_name = name
        self.current_hp = hp
        self.max_hp = hp_max
        self.is_alive = hp > 0


class _MonsterBot:
    def __init__(self, monsters, last=None):
        self.monsters = monsters
        self.player = type("_P", (), {"last_target": last})()


_cell = [_Mon("2", "ultra avatar tyndarius", 600, 1000),
         _Mon("3", "ultra fire orb", 0, 700)]
check("ui monsters: the row carries the map id",
      hub._monster_readout(_MonsterBot(_cell))[0]["id"], "2")

_stored = _Mon("2", "ultra avatar tyndarius", 600, 1000)
_target = hub._target_readout(_MonsterBot(_cell, last=_stored))
check("ui target: names the monster being attacked",
      (_target.get("id"), _target.get("name")),
      ("2", "ultra avatar tyndarius"))
check("ui target: nothing attacked yet is an empty readout",
      hub._target_readout(_MonsterBot(_cell)), {})

_stored.current_hp = 999
_live = hub._target_readout(_MonsterBot([_Mon("2", "ultra avatar tyndarius",
                                              250, 1000)], last=_stored))
check("ui target: the HP shown is the live one", _live["hp"], 250)

_dead = _Mon("3", "ultra fire orb", 0, 700)
check("ui target: a dead target is not shown as alive",
      hub._target_readout(_MonsterBot([_dead], last=_dead))["alive"], False)

# --- potion packets --------------------------------------------------------
# Captured: an elixir is consumed with `serverUseItem`; a combat potion is
# equipped into slot 5 (`geia ... potion`) and cast with `gar`.
class _PotionCommand:
    def __init__(self):
        self.calls = []
        self.logs = []
        self.player = type("P", (), {
            "ISDEAD": False,
            "AURAS": [],
            "get_item_inventory": lambda _self, name: type(
                "I", (), {"qty": 5, "item_id": 12056})(),
        })()
        self.bot = type("B", (), {"player": self.player,
                                  "log": lambda _s, line: self.logs.append(line)})()

    async def has_item(self, name, qty=1, isTemp=False):
        return True

    def is_in_bank(self, name):
        return False

    async def use_item(self, name):
        self.calls.append(("use_item", name))
        return True

    async def equip_potion(self, name):
        self.calls.append(("equip_potion", name))
        return True

    async def use_skill(self, slot, **kwargs):
        self.calls.append(("skill", slot))
        return True


elixir = _PotionCommand()
run(potions.use(elixir, "Potent Destruction Elixir"))
check("potion: an elixir is consumed from the bag",
      elixir.calls, [("use_item", "Potent Destruction Elixir")])

combat = _PotionCommand()
run(potions.use_loadout(combat, None, None, "Potent Honor Potion"))
check("potion: a combat potion is equipped into slot 5",
      combat.calls, [("equip_potion", "Potent Honor Potion")])

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
      ["drakath", "engineer", "ezrajal", "nulgath", "tyndarius", "warden"])
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
      ("warden", "ezrajal", "engineer", "tyndarius", "drakath", "nulgath"))
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
check("tyndarius: taunter panes are slots 3 and 4",
      (ty1.is_taunter, ty3.is_taunter), (False, True))
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

# --- potions ---------------------------------------------------------------
check("potion: Sage Tonic is a 2-voucher, rank-8 alchemy recipe",
      (potions.POTIONS["Sage Tonic"].voucher_qty,
       potions.POTIONS["Sage Tonic"].rank, potions.POTIONS["Sage Tonic"].potion_qty),
      (2, 8, 10))
check("potion: the filtre uses the 100k voucher",
      (potions.POTIONS["Felicitous Philtre"].voucher,
       potions.POTIONS["Felicitous Philtre"].voucher_cost,
       potions.POTIONS["Felicitous Philtre"].potion_qty),
      ("Gold Voucher 100k", 100_000, 25))
check("potion: Potent Honor wants Good rank 10",
      (potions.POTIONS["Potent Honor Potion"].faction,
       potions.POTIONS["Potent Honor Potion"].rank), ("Good", 10))
check("potion: the divine elixirs have no recipe",
      potions.POTIONS["Divine Elixir"].purchasable, False)
check("potion: twelve are whitelisted", len(potions.POTIONS), 12)
check("potion: the combat potion's aura is the Malice one",
      potions.aura_of("Potent Honor Potion"), "Potent Honor Malice")

# --- scrolls ---------------------------------------------------------------
check("scroll: Enrage stock is 80", scrolls.threshold(scrolls.ENRAGE), 80)
check("scroll: Decay stock is 10", scrolls.threshold(scrolls.DECAY), 10)
check("scroll: only three are supported", scrolls.SUPPORTED,
      (scrolls.ENRAGE, scrolls.DECAY, scrolls.MYSTIFY))

# --- warden rules ----------------------------------------------------------
check("warden: Default taunts from slot 1", warden.taunter_slot("Default"), 1)
check("warden: Stable taunts from slot 2", warden.taunter_slot("Stable"), 2)
check("warden: Reliable taunts from slot 1", warden.taunter_slot("Reliable"), 1)
check("warden: the taunt fires at 500k", warden.SPEC.taunt_hp, 500_000)
check("warden: quest 8153 behind 8151", (warden.SPEC.quest,
                                         warden.SPEC.prereq_quest), (8153, 8151))
check("warden: the boss is id.1", warden.SPEC.monster_id, 1)
check("warden: a Stable pane is not the taunter",
      warden.build(_StubCommand(),
                   options.UltraOptions(composition="Stable"), 1).is_taunter, False)
check("warden: Reliable slot 1 is",
      warden.build(_StubCommand(),
                   options.UltraOptions(composition="Reliable"), 1).is_taunter, True)
check("core: a wipe is the whole party down", WIPE_DEATHS, 4)
check("enhancements: every preset field has a slot",
      [slot for _field, slot in enhancements.SLOTS],
      ["class", "cape", "helm", "weapon"])

# --- enhancement buying ----------------------------------------------------
# Wear what is owned; only when nothing carries it does the module buy it.  A
# *basic* enhancement exists at every level, so the highest tier is the buy.
valiance = enhancements.best_entry("Valiance", "weapon")
check("enhancement: Valiance resolves to a shop entry", valiance is not None, True)
check("enhancement: and names its shop",
      bool(getattr(valiance, "shop_id", 0)), True)
awe = enhancements.best_entry("Awe Blast", "weapon")
check("enhancement: Awe Blast resolves", awe is not None, True)


class _EnhCommand:
    """A command whose equips miss until the enhancement was applied/bought."""

    def __init__(self):
        self.calls = []
        self.logs = []
        self.bot = type("B", (), {
            "GOLD": 10_000_000,
            "log": lambda _self, line: self.logs.append(line),
        })()
        self.player = self.bot.player = type("P", (), {"GOLD": 10_000_000})()
        self.applied = False
        self.bought = False

    async def equip_enhancement(self, name, slot=None, enhance_if_missing=False):
        self.calls.append(("equip", name, slot, enhance_if_missing))
        if enhance_if_missing:
            self.applied = True
            return self.bought        # applying only works once it is bought
        return self.bought

    async def ensure_load_shop(self, shop_id):
        self.calls.append(("shop", shop_id))
        return True

    def is_not_in_map(self, name):
        self.calls.append(("join-check", name))
        return True

    async def join_map(self, name, room=None):
        self.calls.append(("join", name))

    def is_still_connected(self):
        return True


class _Entry:
    name = "Valiance"
    item_id = 70752
    shop_id = 2126
    cost = 0
    source = "forge"


real_best = enhancements.best_entry
real_adv_buy = None
enhancements.best_entry = lambda name, slot: _Entry() if name == "Valiance" else None
from bot import core_advanced as _adv


async def _fake_adv_buy(cmd, shop_id, item, qty=1, **kwargs):
    cmd.calls.append(("adv-buy", shop_id, item))
    cmd.bought = True
    return True


real_adv_buy = _adv.buy_item
_adv.buy_item = _fake_adv_buy
try:
    buy_cmd = _EnhCommand()
    bought = run(enhancements._apply_one(buy_cmd, "weapon", ("Valiance",)))
finally:
    enhancements.best_entry = real_best
    _adv.buy_item = real_adv_buy
check("enhancement: a missing one is bought then worn", bought, True)
check("enhancement: apply-to-equipped is tried before buying",
      [c for c in buy_cmd.calls if c[0] == "equip"][:2],
      [("equip", "Valiance", "weapon", False),
       ("equip", "Valiance", "weapon", True)])
check("enhancement: the forge map is joined before its shop",
      buy_cmd.calls.index(("join-check", "forge")) <
      buy_cmd.calls.index(("shop", 2126)), True)
check("enhancement: the buy went to its shop",
      [c for c in buy_cmd.calls if c[0] == "adv-buy"],
      [("adv-buy", 2126, 70752)])
check("enhancement: it says it was bought",
      any("bought" in line for line in buy_cmd.logs), True)

# --- scroll crafting -------------------------------------------------------
check("scroll: gold at 1,000,000 takes the gold route",
      (scrolls.route(999_999), scrolls.route(1_000_000)), ("farm", "gold"))
check("scroll: Enrage needs 25 turn-ins from empty",
      scrolls.turns_for(0, 40, 1000), 25)
check("scroll: from 320 it needs 17", scrolls.turns_for(320, 40, 1000), 17)
check("scroll: an already-full stock needs none",
      scrolls.turns_for(1000, 40, 1000), 0)
check("scroll: Mystify has no farming route", scrolls.FARMABLE,
      (scrolls.ENRAGE, scrolls.DECAY))
check("scroll: Enrage needs SpellCrafting 5", scrolls.REQUIRED_RANK[scrolls.ENRAGE], 5)
check("scroll: Mystify needs SpellCrafting 8", scrolls.REQUIRED_RANK[scrolls.MYSTIFY], 8)
check("scroll: Enrage quest is 2330", scrolls.QUESTS[scrolls.ENRAGE], 2330)


class _ScrollCommand:
    def __init__(self, held=0):
        self.held = held
        self.calls = []
        self.logs = []
        self.player = type("P", (), {
            "GOLD": 2_000_000,
            "get_item_inventory": lambda _self, name: (
                type("I", (), {"qty": self.held})() if self.held else None),
        })()
        self.bot = type("B", (), {
            "player": self.player,
            "log": lambda _self, line: self.logs.append(line),
        })()

    def is_in_bank(self, name):
        return False

    def get_faction_rank(self, name):
        return 10

    def is_in_inventory(self, name):
        return bool(self.held)


full = _ScrollCommand(held=80)
check("scroll: a full stock returns without crafting",
      run(scrolls.prepare(full, scrolls.ENRAGE)), True)
check("scroll: and touches nothing", full.calls, [])
check("scroll: no scroll requested is fine",
      run(scrolls.prepare(_ScrollCommand(), None)), True)


class _NoRankCommand(_ScrollCommand):
    def get_faction_rank(self, name):
        return 1


check("scroll: a low SpellCrafting rank refuses",
      run(scrolls.prepare(_NoRankCommand(), scrolls.ENRAGE)), False)

# --- party barrier with a slot number --------------------------------------
# ``barrier`` was built for v1's usernames; Ultra V2 passes the slot number, and
# joining an int inline raised "'int' object is not iterable" on every run.
import os      # noqa: E402
import shutil  # noqa: E402

from bot.ultra import party as ultra_party  # noqa: E402

_barrier_run = "test_v2_barrier"
_previous = os.environ.get("AQW_RUN_ID")
os.environ["AQW_RUN_ID"] = _barrier_run
try:
    key_ok = isinstance(
        ultra_party.barrier("v2_test", 4, 1, timeout=0.2), bool)
finally:
    ultra_party.clear_abort("v2_test")
    shutil.rmtree(REPO_ROOT / "capture_logs" / "ultra" / _barrier_run,
                  ignore_errors=True)
    if _previous is None:
        os.environ.pop("AQW_RUN_ID", None)
    else:
        os.environ["AQW_RUN_ID"] = _previous
check("party: a slot number works as a barrier key", key_ok, True)

# --- one pane stops -> the whole party stops -------------------------------
# The reference's StopArmySync publishes the abort for every pane; a party that
# keeps fighting after one member gave up is a wasted pull.
import os      # noqa: E402
import shutil  # noqa: E402

from bot.ultra import party as ultra_party  # noqa: E402

_run_id = "test_v2_abort"
_previous_run = os.environ.get("AQW_RUN_ID")
os.environ["AQW_RUN_ID"] = _run_id
try:
    ultra_party.clear_abort("v2_warden")
    first = warden.build(_StubCommand(),
                         options.UltraOptions(players=("a", "b", "c", "d")), 2)
    check("party: sync is on with a run id", first.sync.enabled, True)
    first.abort("test stop")
    check("party: the abort is published for the party",
          ultra_party.any_abort("v2_warden"), "test stop")
    second = warden.build(_StubCommand(),
                          options.UltraOptions(players=("a", "b", "c", "d")), 3)
    check("party: another pane sees the abort",
          second.sync.aborted(), "test stop")
    check("party: so its next step refuses", run(second.sync.step("ANY")), False)
finally:
    ultra_party.clear_abort("v2_warden")
    shutil.rmtree(REPO_ROOT / "capture_logs" / "ultra" / _run_id,
                  ignore_errors=True)
    if _previous_run is None:
        os.environ.pop("AQW_RUN_ID", None)
    else:
        os.environ["AQW_RUN_ID"] = _previous_run

# --- barriers only count panes that are waiting *now* ----------------------
# The run log showed every barrier passing instantly on the first pull: the
# party folder had been reused (same AQW_RUN_ID), so attempt 1 found the four
# markers a previous run left behind and pulled while one pane was still in
# setup.  A marker is only a peer if it was written since we arrived.
_fresh_run = "test_v2_fresh"
_previous_fresh = os.environ.get("AQW_RUN_ID")
os.environ["AQW_RUN_ID"] = _fresh_run
try:
    _directory = ultra_party._dir()
    for _slot in (1, 2, 3, 4):
        (_directory / f"v2_testfresh.STALE.{_slot}.ready").write_text(
            "0", encoding="utf-8")
    check("party: stale markers do not fill a barrier",
          run(sync.Sync("testfresh", 1).step("STALE", timeout=2, strict=True)),
          False)

    async def _late_pane():
        early = [sync.Sync("testfresh", slot) for slot in (1, 2, 3)]
        last = sync.Sync("testfresh", 4)

        async def late():
            await asyncio.sleep(1.5)
            return await last.step("LATE", timeout=10)

        return await asyncio.gather(
            *(pane.step("LATE", timeout=10) for pane in early), late())

    check("party: a waiting pane keeps its marker fresh for a late pane",
          run(_late_pane()), [True, True, True, True])

    (_directory / "v2_testfresh.OLDSEAL.3.sig").write_text(
        '{"value": true, "t": 0}', encoding="utf-8")
    check("party: a signal from an earlier run is not a yes",
          run(sync.Sync("testfresh", 2).wait_signal("OLDSEAL", key=3,
                                                    timeout=1)), False)
finally:
    shutil.rmtree(REPO_ROOT / "capture_logs" / "ultra" / _fresh_run,
                  ignore_errors=True)
    if _previous_fresh is None:
        os.environ.pop("AQW_RUN_ID", None)
    else:
        os.environ["AQW_RUN_ID"] = _previous_fresh

# --- every stop deletes the run folder -------------------------------------
# The markers left behind are what let a later run's barriers pass on their
# own; the user asked for the whole run folder to go on any stop condition.
_run_clean = "test_v2_clean"
_previous_clean = os.environ.get("AQW_RUN_ID")
os.environ["AQW_RUN_ID"] = _run_clean
try:
    _folder = REPO_ROOT / "capture_logs" / "ultra" / _run_clean
    (_folder / "party").mkdir(parents=True, exist_ok=True)
    (_folder / "party" / "v2_test.STEP.1.ready").write_text("1",
                                                            encoding="utf-8")
    (_folder / "slot1_acc.jsonl").write_text("{}", encoding="utf-8")

    class _Telemetry:
        closed = False

        def close(self):
            self.closed = True

    class _Thread:
        def __init__(self):
            self.bot_instance = type("_B", (), {"telemetry": _Telemetry()})()

    _thread = _Thread()
    hub._clear_run_folder([_thread], tag="test")
    check("stop: the whole run folder is deleted", _folder.exists(), False)
    check("stop: each pane's telemetry is closed first",
          _thread.bot_instance.telemetry.closed, True)
finally:
    shutil.rmtree(REPO_ROOT / "capture_logs" / "ultra" / _run_clean,
                  ignore_errors=True)
    if _previous_clean is None:
        os.environ.pop("AQW_RUN_ID", None)
    else:
        os.environ["AQW_RUN_ID"] = _previous_clean

# --- Ultra Drakath (weekly) ------------------------------------------------
# The fight is boss-only; what matters is the taunt ladder: StoneCrusher (slot
# 2) and ArchPaladin (slot 3) each take aggro once as the boss crosses fixed HP
# thresholds, in order, and Stable moves those numbers (``Adjusted*``).
from bot.ultra.v2.weeklies import drakath  # noqa: E402

check("drakath: quest 8300 in championdrakath",
      (drakath.SPEC.quest, drakath.SPEC.map), (8300, "championdrakath"))
check("drakath: pulled from r2/Left, boss id.1",
      (drakath.SPEC.boss_cell, drakath.SPEC.boss_pad, drakath.BOSS),
      ("r2", "Left", "id.1"))
check("drakath: level 80 gate", drakath.SPEC.min_level, 80)
check("drakath: registered for the menu", "drakath" in V2_ORDER, True)


def _drakath(slot, composition="Default"):
    return drakath.UltraDrakath(_StubCommand(), options.UltraOptions(
        players=("a", "b", "c", "d"), composition=composition), slot)


check("drakath: slots 2 and 3 taunt",
      [(_drakath(slot).is_taunter) for slot in (1, 2, 3, 4)],
      [False, True, True, False])
check("drakath: slot 1 and 4 never taunt",
      (_drakath(1).taunt_thresholds(), _drakath(4).taunt_thresholds()),
      ((), ()))
check("drakath: StoneCrusher ladder",
      _drakath(2).taunt_thresholds(),
      (16_500_000, 12_500_000, 6_200_000))
check("drakath: Stable's StoneCrusher ladder",
      _drakath(2, "Stable").taunt_thresholds(),
      (16_500_000, 12_500_000, 6_500_000))
check("drakath: ArchPaladin ladder",
      _drakath(3).taunt_thresholds(),
      (18_500_000, 14_500_000, 8_200_000, 4_200_000))
check("drakath: Stable's ArchPaladin ladder",
      _drakath(3, "Stable").taunt_thresholds(),
      (18_500_000, 14_500_000, 8_500_000, 4_500_000))
check("drakath: GenericPrebuff is 3, 2, 1 at 750 ms",
      (drakath.PREBUFF_SKILLS, drakath.PREBUFF_GAP_MS),
      ((3, 2, 1), 750))

# The ladder is walked once per attempt, in order, only when the HP is crossed.
class _Boss:
    def __init__(self, hp):
        self.current_hp = hp


class _BossCommand(_StubCommand):
    def __init__(self, hp):
        super().__init__()
        self.boss = _Boss(hp)

    def get_monster(self, target="*"):
        return self.boss

    def is_monster_alive(self, target="*"):
        return True


_ap = drakath.UltraDrakath(_BossCommand(19_000_000), options.UltraOptions(
    players=("a", "b", "c", "d")), 3)
check("drakath: nothing to taunt above the first threshold",
      _ap.due_taunt(), None)
_ap.cmd.boss.current_hp = 18_400_000
check("drakath: the first threshold fires", _ap.due_taunt(), 18_500_000)
check("drakath: and is not asked again", _ap.due_taunt(), None)
_ap.cmd.boss.current_hp = 14_000_000
check("drakath: the second threshold fires next", _ap.due_taunt(), 14_500_000)

# ``Fight`` starts its own ``tauntIndex`` at zero, so a wipeout and retry walks
# the ladder from the top again -- the boss comes back at full HP.
_retry = drakath.UltraDrakath(_BossCommand(18_000_000), options.UltraOptions(
    players=("a", "b", "c", "d")), 3)
_retry._taunt_index = 2
_retry.cmd.is_monster_alive = lambda target="*": False
run(_retry.fight(2))
check("drakath: a retry starts the taunt ladder over", _retry._taunt_index, 0)
# A pane that already died and respawned this attempt must publish its next
# death too, or the wipe detector never counts four panes down.
_wr_run = "test_v2_deaths"
_previous_wr = os.environ.get("AQW_RUN_ID")
os.environ["AQW_RUN_ID"] = _wr_run
try:
    from bot.ultra import party as _party  # noqa: E402
    _dead_cmd = _BossCommand(0)
    _dead_cmd.bot.player.ISDEAD = True
    _dead = drakath.UltraDrakath(_dead_cmd, options.UltraOptions(
        players=("a", "b", "c", "d")), 3)
    _dead.note_death()
    _party.clear_death(_dead.sync.name, 3)          # it respawned
    _dead.note_death()                              # and died again
    check("deaths: a second death is published again",
          _party.death_times(_dead.sync.name, (3,)).get(3) is not None, True)
    check("deaths: but the log line stays once per attempt",
          _dead._death_reported, True)
finally:
    shutil.rmtree(REPO_ROOT / "capture_logs" / "ultra" / _wr_run,
                  ignore_errors=True)
    if _previous_wr is None:
        os.environ.pop("AQW_RUN_ID", None)
    else:
        os.environ["AQW_RUN_ID"] = _previous_wr

# Capes: AP always Penitence, slot 1 by composition, Stable's KE on Lament.
check("drakath: ArchPaladin wears Penitence in every composition",
      [presets.preset_for("drakath", composition, 3).cape
       for composition in ("Default", "Stable", "Reliable")],
      ["Penitence"] * 3)
check("drakath: slot 1 capes per composition",
      [presets.preset_for("drakath", composition, 1).cape
       for composition in ("Default", "Stable", "Reliable")],
      ["Penitence", "Lament", "Penitence"])

# --- Ultra Nulgath (weekly) ------------------------------------------------
# Blade id.1 / Nulgath id.2; the taunt relay hangs off an ``Abyss!`` packet
# detector on slot 4, and the target table is per slot *and* composition.
from bot.ultra.v2.weeklies import nulgath  # noqa: E402
from bot.ultra.v2.packets import PacketDetector  # noqa: E402

check("nulgath: quest 8692 in ultranulgath",
      (nulgath.SPEC.quest, nulgath.SPEC.map), (8692, "ultranulgath"))
check("nulgath: pulled from Boss/Right, boss id.2",
      (nulgath.SPEC.boss_cell, nulgath.SPEC.boss_pad, nulgath.SPEC.monster_id),
      ("Boss", "Right", 2))
check("nulgath: level 80 gate", nulgath.SPEC.min_level, 80)
check("nulgath: registered for the menu", "nulgath" in V2_ORDER, True)


class _TwoBossCommand(_StubCommand):
    """Blade id.1 and Nulgath id.2, with the Blade's HP under our control."""

    def __init__(self, blade_hp=1_000_000, blade_alive=True):
        super().__init__()
        self.blade = _Boss(blade_hp)
        self.blade_alive = blade_alive

    def get_monster(self, target="*"):
        return self.blade

    def is_monster_alive(self, target="*"):
        return str(target) != "id.1" or self.blade_alive


def _nulgath(slot, composition="Default"):
    return nulgath.UltraNulgath(_TwoBossCommand(), options.UltraOptions(
        players=("a", "b", "c", "d"), composition=composition), slot)


check("nulgath: Default taunters are slots 1 and 4",
      [_nulgath(slot).is_taunter for slot in (1, 2, 3, 4)],
      [True, False, False, True])
check("nulgath: Stable/Reliable taunters are slots 3 and 4",
      [(_nulgath(slot, composition).is_taunter)
       for composition in ("Stable", "Reliable") for slot in (3, 4)],
      [True, True, True, True])
check("nulgath: slot 4 is the packet watcher",
      [_nulgath(slot).is_watcher for slot in (1, 2, 3, 4)],
      [False, False, False, True])

# GetTargetMapId, the part that differs per slot and composition.
check("nulgath: Default slot 2 chips the Blade while it is healthy",
      _nulgath(2).target_map_id(), "id.1")
_weak = nulgath.UltraNulgath(_TwoBossCommand(blade_hp=700_000),
                             options.UltraOptions(
                                 players=("a", "b", "c", "d")), 2)
check("nulgath: Default slot 2 leaves the Blade under 750k",
      _weak.target_map_id(), "id.2")
check("nulgath: Default's other slots hit Nulgath",
      [_nulgath(slot).target_map_id() for slot in (1, 3, 4)],
      ["id.2", "id.2", "id.2"])
check("nulgath: Stable slot 1 chips the Blade above 500k",
      _nulgath(1, "Stable").target_map_id(), "id.1")
_stable_weak = nulgath.UltraNulgath(_TwoBossCommand(blade_hp=400_000),
                                    options.UltraOptions(
                                        players=("a", "b", "c", "d"),
                                        composition="Stable"), 1)
check("nulgath: Stable slot 1 leaves it under 500k",
      _stable_weak.target_map_id(), "id.2")
check("nulgath: Stable slot 2 stays on the Blade while it lives",
      _nulgath(2, "Stable").target_map_id(), "id.1")
check("nulgath: Reliable slot 1 stays on the Blade while it lives",
      _nulgath(1, "Reliable").target_map_id(), "id.1")
_gone = nulgath.UltraNulgath(_TwoBossCommand(blade_alive=False),
                             options.UltraOptions(
                                 players=("a", "b", "c", "d"),
                                 composition="Reliable"), 1)
check("nulgath: a dead Blade sends the slot to Nulgath",
      _gone.target_map_id(), "id.2")

# The Abyss relay: slot 4 sees the packet, waits 2 s, taunts and signals; the
# taunter one answers each signal 5 s later.
from datetime import datetime, timedelta  # noqa: E402

try:
    from bot.ultra import party as _party  # noqa: E402

    _abyss_run = "test_v2_nulgath"
    _previous_abyss = os.environ.get("AQW_RUN_ID")
    os.environ["AQW_RUN_ID"] = _abyss_run

    watcher = _nulgath(4)

    async def _handler(msg):
        return None

    watcher.bot.handle_server_response = _handler
    opened = watcher.detector.start()
    watcher.detector.inspect(
        '{"b":{"o":{"cmd":"ct","sarsa":{"ty":"h","t":2,"c":"Abyss!"}}}}')
    check("nulgath: the detector counts an Abyss packet",
          (opened, watcher.detector.count), (True, 1))
    watcher.detector.stop()
    check("nulgath: and stops counting when disarmed",
          watcher.detector.seen(1), False)

    watcher.detector.start()
    watcher.start_taunt_cycle()
    now = datetime.now()
    watcher.detector.inspect(
        '{"b":{"o":{"cmd":"ct","sarsa":{"ty":"h","t":2,"c":"Abyss!"}}}}')
    watcher.player_four_step(1, now)
    check("nulgath: slot 4 schedules a taunt on the detection",
          watcher._taunt_scheduled, True)
    watcher.player_four_step(1, now + timedelta(milliseconds=2500))
    check("nulgath: and sends ABYSS_TAUNT_DONE_1_1 when it fires",
          watcher.sync.read("ABYSS_TAUNT_DONE_1_1").get(4), True)
    check("nulgath: the cycle advances", watcher._abyss_cycle, 2)

    taunter = _nulgath(3, "Stable")
    taunter.start_taunt_cycle()
    later = datetime.now() + timedelta(milliseconds=6000)
    taunter.taunter_one_step(7, later)
    check("nulgath: the taunter one opens with a taunt after 5 s",
          taunter.taunt_requested, True)
    taunter.taunt_requested = False
    taunter.taunter_one_step(7, later)
    check("nulgath: the next step waits for the slot 4 signal",
          taunter._taunt_scheduled, False)
    _party.publish(f"{taunter.sync.name}.ABYSS_TAUNT_DONE_7_1", 4, True)
    taunter.taunter_one_step(7, later)
    check("nulgath: a signal schedules the answer taunt",
          (taunter._taunt_scheduled, taunter._taunt_at > later), (True, True))
finally:
    shutil.rmtree(REPO_ROOT / "capture_logs" / "ultra" / _abyss_run,
                  ignore_errors=True)
    if _previous_abyss is None:
        os.environ.pop("AQW_RUN_ID", None)
    else:
        os.environ["AQW_RUN_ID"] = _previous_abyss

check("nulgath: GenericPrebuff is 3, 2, 1 at 750 ms",
      (nulgath.PREBUFF_SKILLS, nulgath.PREBUFF_GAP_MS), ((3, 2, 1), 750))

print(f"passed {passed}   failed {len(failures)}")
if failures:
    for line in failures:
        print("FAIL", line)
    raise SystemExit(1)
print("ultra v2 tests OK")
