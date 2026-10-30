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
      ["engineer", "ezrajal", "warden"])
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
      ("warden", "ezrajal", "engineer"))
eng = engineer.UltraEngineer(_StubCommand(), options.UltraOptions(
    players=("a", "b", "c", "d")), 1)
check("engineer: the engine tries the adds before the boss",
      eng.target_priority, ("Attack Drone", "Defense Drone", "id.3"))
check("engineer: it uses the standard composition",
      eng.preset.cls, "Legion Revenant")

# Every V2 daily fights v1's literal rotation, skill 0 (auto attack) included.
check("rotation: warden starts on skill 0",
      warden.build(_StubCommand(), options.UltraOptions(
          players=("a", "b", "c", "d")), 1).rotation[0], 0)
check("rotation: ezrajal starts on skill 0",
      ezrajal.UltraEzrajal(_StubCommand(), options.UltraOptions(
          players=("a", "b", "c", "d")), 1).rotation[0], 0)
check("rotation: engineer starts on skill 0", eng.rotation[0], 0)
# VDK (strict) and KE (kings_echo) must cast skill 0 too, like every v1 daily.
vdk = warden.build(_StubCommand(), options.UltraOptions(
    players=("a", "b", "c", "d"), composition="Reliable"), 1)
ke = warden.build(_StubCommand(), options.UltraOptions(
    players=("a", "b", "c", "d"), composition="Stable"), 1)
check("rotation: Verus DoomKnight keeps the literal 0", (vdk.rotation[0],
                                                          vdk.preset.mode), (0, "strict"))
check("rotation: King's Echo keeps the literal 0", (ke.rotation[0],
                                                    ke.preset.mode), (0, "kings_echo"))

# Skill 0 is mandatory: a module that leaves it out gets it prepended.
class _NoZero(warden.UltraWarden):
    def __init__(self, cmd, options, slot=1):
        super().__init__(cmd, options, slot)
        self.skill_rotation = (1, 2, 3)


forced = _NoZero(_StubCommand(), options.UltraOptions(
    players=("a", "b", "c", "d")), 1)
check("rotation: skill 0 is put back when a module forgets it",
      forced.rotation, (0, 1, 2, 3))

check("rotation: all three use v1's string",
      [warden.build(_StubCommand(), options.UltraOptions(
           players=("a", "b", "c", "d")), 1).rotation,
       ezrajal.UltraEzrajal(_StubCommand(), options.UltraOptions(
           players=("a", "b", "c", "d")), 1).rotation,
       eng.rotation],
      [(0, 1, 2, 0, 3, 4)] * 3)

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
check("tyndarius: hidden until the LW port is done",
      "tyndarius" in V2_ORDER, False)
ty1 = tyndarius.UltraTyndarius(_StubCommand(), options.UltraOptions(
    players=("a", "b", "c", "d")), 1)
ty2 = tyndarius.UltraTyndarius(_StubCommand(), options.UltraOptions(
    players=("a", "b", "c", "d")), 2)
ty3 = tyndarius.UltraTyndarius(_StubCommand(), options.UltraOptions(
    players=("a", "b", "c", "d")), 3)
check("tyndarius: v1's literal rotation", ty1.rotation, (0, 1, 2, 0, 3, 4, 5))
check("tyndarius: slot 1 opens on crystal id.1",
      ty1.target_priority, (tyndarius.FIRST_CRYSTAL,))
check("tyndarius: slot 2 opens on crystal id.3",
      ty2.target_priority, (tyndarius.SECOND_CRYSTAL,))
check("tyndarius: slots 3-4 stay on the boss", ty3.target_priority, ())
check("tyndarius: heal below 60 on slots 3-4",
      (ty1.heal_below, ty1.heal_slots), (60, (3, 4)))

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

print(f"passed {passed}   failed {len(failures)}")
if failures:
    for line in failures:
        print("FAIL", line)
    raise SystemExit(1)
print("ultra v2 tests OK")
