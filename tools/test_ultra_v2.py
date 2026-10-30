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


# --- options ---------------------------------------------------------------
for ultra in ("warden", "ezrajal", "engineer", "tyndarius", "drakath", "drago",
              "nulgath", "dage", "darkon", "gramiel", "speaker"):
    table = options.compositions(ultra)
    check(f"{ultra}: three compositions are ported",
          sorted(table), ["Default", "Reliable", "Stable"]
          if ultra != "speaker" else ["Default", "Reliable"])
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
check("core: a wipe needs two panes down", WIPE_DEATHS, 2)
check("enhancements: every preset field has a slot",
      [slot for _field, slot in enhancements.SLOTS],
      ["class", "cape", "helm", "weapon"])

print(f"passed {passed}   failed {len(failures)}")
if failures:
    for line in failures:
        print("FAIL", line)
    raise SystemExit(1)
print("ultra v2 tests OK")
