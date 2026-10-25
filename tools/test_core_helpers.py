"""The CoreBots / CoreAdvanced helpers added after the first port pass.

    python tools/test_core_helpers.py

Covers ``hunt_monster_quest`` (quest order, held requirements skipped, refused
accepts reported), ``get_map_items``, ``register_quests``, the ``SavedState``
timer, ``gear_store``, ``rank_up_class``'s early exits and the legacy id mappers.
"""
import asyncio
import pathlib
import sys
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bot import core_advanced as adv  # noqa: E402
from bot import core_bots as bots  # noqa: E402

failures = []
passed = 0


def check(label, got, want):
    global passed
    if got == want:
        passed += 1
    else:
        failures.append(f"{label}: got {got!r}, want {want!r}")


# --- stubs ------------------------------------------------------------------
class Item:
    def __init__(self, name, slot="Weapon", item_id=1, qty=1, equipped=False,
                 enh_level=100, upgrade=False, pattern=9, proc=9):
        self.item_name = name
        self.s_es = slot
        self.item_id = str(item_id)
        self.qty = qty
        self.is_equipped = equipped
        self.enh_level = enh_level
        self.is_upgrade = upgrade
        self.enh_pattern_id = pattern
        self.item_proc_id = proc


class Quest:
    def __init__(self, items, turn_in=None):
        self.items = items
        self.turn_in_requirements = turn_in if turn_in is not None else [
            {"ItemID": item["ItemID"], "iQty": item.get("iQty", "1"),
             "bTemp": item.get("bTemp", "0")}
            for item in items]
        self.turn_in_items = [(int(item["ItemID"]), int(item.get("iQty", 1)))
                              for item in items]


class Player:
    def __init__(self, inventory=()):
        self.INVENTORY = list(inventory)
        self.is_member = True
        self.LEVEL = 80
        self.temp = {}

    def get_item_inventory(self, name):
        for item in self.INVENTORY:
            if item.item_name.lower() == name.lower():
                return item
        return None

    def get_item_inventory_by_id(self, item_id):
        for item in self.INVENTORY:
            if str(item.item_id) == str(item_id):
                return item
        return None

    def get_item_temp_inventory_by_id(self, item_id):
        return self.temp.get(str(item_id))

    def get_item_bank(self, name):
        return None

    def get_item_bank_by_id(self, item_id):
        return None


class Bot:
    def __init__(self, player):
        self.player = player
        self.logs = []

    def log(self, *args):
        self.logs.append(" ".join(map(str, args)))


class Cand:
    def __init__(self, inventory=(), quests=None, accept=True, turn_in=True):
        self.bot = Bot(Player(inventory))
        self.quests = quests or {}
        self.accept = accept
        self.turn_in = turn_in
        self.calls = []

    # --- CoreBots surface ---
    def is_in_inventory(self, name, qty=1, operator=">=", isTemp=False):
        return self.bot.player.get_item_inventory(name) is not None

    def is_in_bank(self, name, qty=1, operator=">="):
        return False

    def add_drop(self, item):
        self.calls.append(("drop", item))

    def cancel_registered_quests(self):
        self.calls.append(("cancel_quests",))

    async def ensure_accept_quest(self, quest):
        self.calls.append(("accept", quest))
        return self.accept

    async def ensure_turn_in_quest(self, quest, item_id=-1):
        self.calls.append(("turnin", quest, item_id))
        return self.turn_in

    def get_loaded_quest(self, quest):
        return self.quests.get(quest)

    async def join_map(self, name, room=None):
        self.calls.append(("join", name, room))

    async def get_map_item(self, item_id, qty=1):
        self.calls.append(("mapitem", item_id, qty))

    async def register_quest(self, quest):
        self.calls.append(("register", quest))
        return True

    async def jump_cell(self, cell, pad="Left"):
        self.calls.append(("cell", cell, pad))

    async def equip_item(self, name):
        self.calls.append(("equip", name))
        item = self.bot.player.get_item_inventory(name)
        if item is not None:
            item.is_equipped = True
        return item is not None

    async def bank_to_inv(self, name):
        self.calls.append(("unbank", name))

    def get_equipped_class(self):
        for item in self.bot.player.INVENTORY:
            if item.s_es == "ar" and item.is_equipped:
                return item
        return None

    def get_player(self):
        return self.bot.player


def run(coro):
    return asyncio.run(coro)


def patch(module, **replacements):
    original = {name: getattr(module, name) for name in replacements}
    for name, value in replacements.items():
        setattr(module, name, value)
    return original


def restore(module, original):
    for name, value in original.items():
        setattr(module, name, value)


# ============================================================================
# 1. hunt_monster_quest
# ============================================================================
hunts = []


async def fake_hunt(cmd, item, qty, map_name, **kwargs):
    hunts.append((item, qty, map_name, kwargs.get("monster_name"),
                  kwargs.get("is_temp")))


async def fake_equip(cmd, solo=False):
    hunts.append(("equip", "solo" if solo else "farm"))
    return True


saved = patch(bots, hunt_item=fake_hunt, equip_class=fake_equip)
try:
    quest = Quest(items=[
        {"ItemID": "501", "sName": "Alpha Hide", "iQty": "2", "bTemp": "1"},
        {"ItemID": "502", "sName": "Beta Fang", "iQty": "1", "bTemp": "0"},
    ])
    cmd = Cand(quests={900: quest})
    cmd.bot.player.temp["501"] = Item("Alpha Hide", qty=2)   # already held
    ok = run(bots.hunt_monster_quest(
        cmd, 900, ("mapA", "Alpha", True), ("mapB", "Beta", False)))
    check("hmq returned", ok, True)
    check("hmq accepted first", cmd.calls[0], ("accept", 900))
    check("hmq skipped the held requirement",
          [h for h in hunts if h[0] == "Alpha Hide"], [])
    check("hmq hunted the missing one",
          [h for h in hunts if h[0] == "Beta Fang"],
          [("Beta Fang", 1, "mapB", "Beta", False)])
    check("hmq equipped the farm class",
          [h for h in hunts if h[0] == "equip"], [("equip", "farm")])
    check("hmq turned in", cmd.calls[-1], ("turnin", 900, -1))

    # A refused accept must report and farm nothing.
    hunts.clear()
    cmd = Cand(quests={900: quest}, accept=False)
    ok = run(bots.hunt_monster_quest(cmd, 900, ("mapA", "Alpha", True)))
    check("hmq refused: not ok", ok, False)
    check("hmq refused: no hunt", hunts, [])
    check("hmq refused: says why",
          any("cannot be accepted" in line for line in cmd.bot.logs), True)

    # The single-target overload applies one map/monster to every requirement.
    hunts.clear()
    wide = Quest(items=[
        {"ItemID": "601", "sName": "Ruby Shard", "iQty": "1"},
        {"ItemID": "602", "sName": "Ruby Dust", "iQty": "3"},
    ])
    cmd = Cand(quests={901: wide})
    ok = run(bots.hunt_monster_quest_single(cmd, 901, "greed", "Cursed One",
                                            solo=True))
    check("hmq single returned", ok, True)
    check("hmq single hunted every requirement",
          [(h[0], h[2], h[3]) for h in hunts if h[0] != "equip"],
          [("Ruby Shard", "greed", "Cursed One"),
           ("Ruby Dust", "greed", "Cursed One")])
    check("hmq single equipped solo",
          [h for h in hunts if h[0] == "equip"],
          [("equip", "solo"), ("equip", "solo")])
finally:
    restore(bots, saved)

# ============================================================================
# 2. get_map_items / register_quests
# ============================================================================
cmd = Cand()
run(bots.get_map_items(cmd, [(11, 2), (12, 1)], map_name="somewhere"))
check("map items joined first", cmd.calls[0], ("join", "somewhere", None))
check("map items one call per pair",
      [c for c in cmd.calls if c[0] == "mapitem"],
      [("mapitem", 11, 2), ("mapitem", 12, 1)])

cmd = Cand()
run(bots.register_quests(cmd, 9316, 9349))
check("register_quests plural",
      [c for c in cmd.calls if c[0] == "register"],
      [("register", 9316), ("register", 9349)])

# ============================================================================
# 3. SavedState
# ============================================================================
cmd = Cand()
bots.saved_state(cmd, True)                       # no map -> refused
check("save state needs a map",
      getattr(cmd.bot, "save_state_enabled", False), False)
bots.saved_state(cmd, True, "seavoice")
check("save state armed", cmd.bot.save_state_enabled, True)
check("save state timer in 30-60 min",
      bots.SAVE_STATE_MIN_S <= cmd.bot.save_state_next - time.time()
      <= bots.SAVE_STATE_MAX_S + 2, True)
check("save state not due yet", bots.check_save_state(cmd), False)
cmd.bot.save_state_next = time.time() - 1
check("save state due", bots.check_save_state(cmd), True)

run(bots.execute_save_state(cmd))
check("save state hopped out", ("join", "whitemap", 100000) in cmd.calls, True)
check("save state came back", ("join", "seavoice", None) in cmd.calls, True)
check("save state rescheduled", bots.check_save_state(cmd), False)

bots.saved_state(cmd, False)
check("save state disarmed without a map", cmd.bot.save_state_enabled, False)
check("disarmed = never due", bots.check_save_state(cmd), False)

# ============================================================================
# 4. legacy id mappers
# ============================================================================
check("weapon id 0", adv.weapon_from_id(0), "Forge")
check("weapon id 1", adv.weapon_from_id(1), "None")
check("weapon id 9", adv.weapon_from_id(9), "Valiance")
check("weapon id 99", adv.weapon_from_id(99), "None")
check("helm id 28", adv.helm_from_id(28), "Anima")
check("helm id 0", adv.helm_from_id(0), "None")

# ============================================================================
# 5. current_class_enh
# ============================================================================
check("class enh pattern 6", adv.current_class_enh(
    Cand([Item("DoT", slot="ar", equipped=True, pattern=6)])), "Wizard")
check("class enh pattern 23 folds to Lucky", adv.current_class_enh(
    Cand([Item("DoT", slot="ar", equipped=True, pattern=23)])), "Lucky")
check("class enh unknown -> Lucky", adv.current_class_enh(
    Cand([Item("DoT", slot="ar", equipped=True, pattern=44)])), "Lucky")
check("no class -> Lucky", adv.current_class_enh(Cand([])), "Lucky")

# ============================================================================
# 6. gear_store
# ============================================================================
helmet = Item("Wizard Helm", slot="he", item_id=7, equipped=True, pattern=28)
cape = Item("Cape", slot="ba", item_id=8, equipped=True, pattern=24)
weapon = Item("Sword", slot="Weapon", item_id=9, equipped=True, proc=9)
klass = Item("ArchPaladin", slot="ar", item_id=10, equipped=True, pattern=6)
cmd = Cand([helmet, cape, weapon, klass])
enhanced = []


async def fake_enhance_equipped(cmd, type_, cape_="None", helm="None",
                                weapon_="None"):
    enhanced.append((type_, cape_, helm, weapon_))


saved = patch(adv, enhance_equipped=fake_enhance_equipped)
try:
    run(adv.gear_store(cmd))
    saved_state = cmd.bot.gear_store_saved
    check("gear saved the worn items", len(saved_state["items"]), 4)
    check("gear saved the class enh", saved_state["class_enh"], "Wizard")
    check("gear saved the helm special", saved_state["helm"], "Anima")
    check("gear saved the cape special", saved_state["cape"], "Vainglory")
    check("gear saved the weapon special", saved_state["weapon"], "Valiance")

    for item in cmd.bot.player.INVENTORY:
        item.is_equipped = False
    run(adv.gear_store(cmd, restore=True, enh_after=True))
    check("gear put the items back",
          [c for c in cmd.calls if c[0] == "equip"],
          [("equip", "Wizard Helm"), ("equip", "Cape"), ("equip", "Sword"),
           ("equip", "ArchPaladin")])
    check("gear re-enhanced after restore", enhanced,
          [("Wizard", "Vainglory", "Anima", "Valiance")])

    empty = Cand([])
    run(adv.gear_store(empty, restore=True))
    check("gear restore without a save reports",
          any("nothing was saved" in line for line in empty.bot.logs), True)
finally:
    restore(adv, saved)

# ============================================================================
# 7. rank_up_class
# ============================================================================
async def no_gear_store(cmd, restore=False, enh_after=False):
    cmd.calls.append(("gear_store", restore))


async def no_smart(cmd, name):
    cmd.calls.append(("smart", name))


async def no_arena(cmd, level, rank_up_class=False, keep_class=False):
    cmd.calls.append(("arena", level, rank_up_class, keep_class))


saved = patch(adv, gear_store=no_gear_store, smart_enhance=no_smart,
              icestorm_arena=no_arena)
try:
    # Already Rank 10.
    cmd = Cand([Item("ArchPaladin", slot="ar", item_id=10, equipped=True,
                     qty=302500)])
    run(adv.rank_up_class(cmd, "ArchPaladin"))
    check("rank10: arena not run", [c for c in cmd.calls if c[0] == "arena"], [])
    check("rank10: says so",
          any("already Rank 10" in line for line in cmd.bot.logs), True)

    # Unrankable.
    cmd = Cand([Item("No Class", slot="ar", item_id=11, equipped=True)])
    run(adv.rank_up_class(cmd, "No Class"))
    check("unrankable: says so",
          any("past Rank 1" in line for line in cmd.bot.logs), True)

    # Not owned.
    cmd = Cand([])
    run(adv.rank_up_class(cmd, "ArchPaladin"))
    check("missing: says so",
          any("don't own it" in line for line in cmd.bot.logs), True)

    # Happy path: equip, arena with keep_class, then restore.
    cmd = Cand([Item("ArchPaladin", slot="ar", item_id=10, qty=1000)])
    run(adv.rank_up_class(cmd, "ArchPaladin"))
    check("rank: smart enhanced", ("smart", "ArchPaladin") in cmd.calls, True)
    check("rank: equipped the class", ("equip", "ArchPaladin") in cmd.calls, True)
    check("rank: arena kept the class",
          [c for c in cmd.calls if c[0] == "arena"],
          [("arena", 80, True, True)])
    check("rank: gear stored then restored",
          [c for c in cmd.calls if c[0] == "gear_store"],
          [("gear_store", False), ("gear_store", True)])
finally:
    restore(adv, saved)

# ============================================================================
# 8. the SeaVoice merge waits in the regular inventory
# ----------------------------------------------------------------------------
# Bioluminessence and its three siblings are inventory items ("add items ..."
# with a CharItemID), so an ``isTemp=True`` wait never ends -- the fight ran
# past x30 and kept going.  The reference passes ``isTemp: true``; this port
# does not.
# ============================================================================
from bot.other.merge_shops import sea_voice_merge as svm  # noqa: E402

waits = []


async def fake_farm(cmd, quest, item, qty, farm_pass, is_temp=False, **_kw):
    waits.append(("farm_quest_reward", item, qty, is_temp))
    await farm_pass()


async def fake_kill(cmd, map_name, item, item_used, quant=1, is_temp=False):
    waits.append(("kill_thing", item, quant, is_temp))


async def fake_equip(cmd, solo=False):
    return True


async def fake_smart(cmd, name):
    return None


saved = patch(svm, farm_quest_reward=fake_farm, kill_thing=fake_kill,
              equip_class=fake_equip, smart_enhance=fake_smart)
try:
    cmd = Cand([Item("Chaos Avenger", slot="ar", item_id=1)])
    run(svm._attack_voice_in_the_sea(cmd, "Bioluminessence", 30))
    check("seavoice: the fight waits in the inventory",
          [c for c in waits if c[0] == "kill_thing"],
          [("kill_thing", "Bioluminessence", 30, False)])
    check("seavoice: the quest reward waits there too",
          [(c[1], c[2], c[3]) for c in waits if c[0] == "farm_quest_reward"],
          [("Bioluminessence", 30, False)])
finally:
    restore(svm, saved)

print(f"passed {passed}   failed {len(failures)}")
if failures:
    for line in failures:
        print("FAIL", line)
    raise SystemExit(1)
print("core helpers tests OK")
