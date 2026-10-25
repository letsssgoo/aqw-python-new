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
        self.TEMPINVENTORY = []
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

    def get_item_temp_inventory(self, name):
        for item in self.temp.values():
            if item.item_name.lower() == name.lower():
                return item
        return None

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
        self.rewards = {}
        self.completed = set()
        self.accept = accept
        self.turn_in = turn_in
        self.calls = []

    async def is_completed_before(self, quest_id, timeout_sec=3.0):
        return quest_id in self.completed

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

    def get_quest_rewards(self, quest):
        return list(self.rewards.get(quest, []))

    async def join_map(self, name, room=None):
        self.calls.append(("join", name, room))

    async def get_map_item(self, item_id, qty=1):
        self.calls.append(("mapitem", item_id, qty))

    async def register_quest(self, quest):
        self.calls.append(("register", quest))
        return True

    async def has_item(self, name, qty=1, isTemp=False):
        return self.bot.player.get_item_inventory(name) is not None

    async def has_item_id(self, item_id):
        return self.bot.player.get_item_inventory_by_id(item_id) is not None

    async def sell_item(self, name, qty=1):
        self.calls.append(("sell", name, qty))

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

# ============================================================================
# 9. CoreBots helpers -- built on the real item/quest models
# ============================================================================
from model.inventory import ItemInventory  # noqa: E402
from model.quest import Quest as ModelQuest  # noqa: E402

sword = ItemInventory({"sName": "Sword", "sES": "Weapon", "ItemID": 1,
                       "iQty": 1})
helm = ItemInventory({"sName": "Helm", "sES": "he", "ItemID": 2, "iQty": 1,
                      "bEquip": 1})
check("weapon slot is a weapon", adv.is_weapon(sword), True)
check("helm slot is not a weapon", adv.is_weapon(helm), False)

cmd = Cand([sword, helm])
cmd.bot.player.temp["9"] = ItemInventory({"sName": "Sword", "ItemID": 1,
                                          "iQty": 2})
bots.farming_logger(cmd, "Sword", 5)
check("farming logger counts both bags", cmd.bot.logs[-1],
      "Farming Sword (3/5)")

run(bots.equip_items(cmd, "Helm", "Sword", "Missing"))
check("equip skips what is already worn",
      [c for c in cmd.calls if c[0] == "equip"], [("equip", "Sword")])
check("equip reports what is missing",
      any("not found" in line for line in cmd.bot.logs), True)

cmd = Cand()
cmd.rewards = {1: ["A", "B"], 2: ["B", "C"]}
check("quest rewards are merged without duplicates",
      bots.quest_rewards(cmd, 1, 2), ["A", "B", "C"])

picker = ModelQuest.from_payload({
    "QuestID": "777", "sName": "Pick One",
    "reward": [{"ItemID": "10", "iQty": 1, "iType": 2}],
    "oRewards": {"itemsC": [{"ItemID": "10", "sName": "Pick Me", "iStk": 1},
                            {"ItemID": "11", "sName": "Other", "iStk": 1}]},
})
cmd = Cand(quests={777: picker})
ok = run(bots.ensure_complete_choose(cmd, 777, "Nope", "Other"))
check("choose turns in with the offered reward",
      cmd.calls[-1], ("turnin", 777, 11))
check("choose returned", ok, True)

missing_name = run(bots.ensure_complete_choose(cmd, 777, "Nope"))
check("choose with no matching reward stops", missing_name, False)
check("choose says why",
      any("offers none" in line for line in cmd.bot.logs), True)

# ============================================================================
# 10. CoreStory -- the gate, the completion and the three quest shapes
# ============================================================================
from bot import core_story as story  # noqa: E402

cmd = Cand()
cmd.completed = {900}
check("progression: a done quest needs nothing",
      run(story.quest_progression(cmd, 900)), True)
check("progression: says it is already done",
      any("Already Completed" in line for line in cmd.bot.logs), True)
check("progression: nothing was farmed",
      [c for c in cmd.calls if c[0] in ("accept", "drop")], [])

cmd = Cand()
cmd.bot.player.INVENTORY.append(
    ItemInventory({"sName": "Shiny", "ItemID": 99, "iQty": 1}))
check("progression: a held reward skips the quest",
      run(story.quest_progression(cmd, 901, reward="Shiny")), True)
check("progression: says the reward is owned",
      any("Already have reward" in line for line in cmd.bot.logs), True)

cmd = Cand()
cmd.rewards = {902: ["A", "B"]}
check("progression: a quest that needs doing", run(
    story.quest_progression(cmd, 902)), False)
check("progression: whitelists the rewards",
      ("drop", ["A", "B"]) in cmd.calls, True)

ore = ModelQuest.from_payload({
    "QuestID": "910", "sName": "Ore Quest",
    "turnin": [{"ItemID": "10", "iQty": "2"}],
    "oItems": [{"ItemID": "10", "sName": "Ore", "iQty": "2"}],
})
cmd = Cand(quests={910: ore})
check("complete: missing requirement stops", run(
    story.try_complete(cmd, ore)), False)
check("complete: names what is missing",
      any("Missing items" in line and "Ore x2" in line
          for line in cmd.bot.logs), True)

cmd = Cand([ItemInventory({"sName": "Ore", "ItemID": 10, "iQty": 2})],
           quests={910: ore})
check("complete: held requirement turns in",
      run(story.try_complete(cmd, ore)), True)
check("complete: turn-in went out", cmd.calls[-1], ("turnin", 910, -1))

completed_calls = []


async def fake_try(cmd, quest, auto_complete=True):
    completed_calls.append((quest, auto_complete))
    return True


async def fake_buy(cmd, shop_id, item, qty=1, map_name=None, shop_item_id=0):
    completed_calls.append(("buy", shop_id, item, qty, map_name))


saved = patch(story, try_complete=fake_try, buy_item=fake_buy)
try:
    cmd = Cand()
    cmd.completed = {912}
    run(story.chain_quest(cmd, 912))
    check("chain: a done quest is not accepted",
          [c for c in cmd.calls if c[0] == "accept"], [])

    completed_calls.clear()
    cmd = Cand(quests={913: ore})
    run(story.chain_quest(cmd, 913, auto_complete=False))
    check("chain: accepted", ("accept", 913) in cmd.calls, True)
    check("chain: then completed", len(completed_calls), 1)
    check("chain: auto_complete is forwarded",
          completed_calls[0][1], False)

    completed_calls.clear()
    cmd = Cand(quests={914: ore})
    run(story.buy_quest(cmd, 914, "mapx", 77, "Thing", 3))
    check("buy: accepted", ("accept", 914) in cmd.calls, True)
    check("buy: the shop call carries the map",
          completed_calls[0], ("buy", 77, "Thing", 3, "mapx"))
    check("buy: then completed", completed_calls[1], (ore, True))

    completed_calls.clear()
    cmd = Cand(quests={915: ore})
    check("quest_complete: turns in", run(story.quest_complete(cmd, 915)), True)
    check("quest_complete: accepted first", cmd.calls[0], ("accept", 915))
finally:
    restore(story, saved)

# ============================================================================
# 11. Vim / Examen / Anima / Pneuma -- the chain, its order and its guards
# ============================================================================
from bot.enhancements import vim as vim_mod  # noqa: E402
from bot.enhancements import anima as anima_mod  # noqa: E402
from bot.enhancements import examen as examen_mod  # noqa: E402
from bot.enhancements import pneuma as pneuma_mod  # noqa: E402

order = []


async def rec_forge(cmd, use_gold=False):
    order.append("forge_helm")


async def rec_rep(cmd, rank=10, use_gold=False, bulk=False):
    order.append(f"rep{rank}")


async def rec_gear(cmd, restore=False, enh_after=False):
    order.append(f"gear{int(restore)}")


async def rec_buy(cmd, shop, item, qty=1, map_name=None, shop_item_id=0):
    order.append(f"buy:{item}")


async def rec_rank(cmd, name="", item_id=0, gear_restore=True):
    order.append(f"rank:{name}")


async def rec_equip(cmd, solo=False):
    order.append("equip")


async def rec_hunt(cmd, item, qty, map_name, **kwargs):
    order.append(f"hunt:{item}x{qty}")


leaf = patch(vim_mod, forge_helm_enhancement=rec_forge,
             blacksmithing_rep=rec_rep, gear_store=rec_gear, buy_item=rec_buy,
             rank_up_class=rec_rank, equip_class=rec_equip, hunt_item=rec_hunt)
try:
    cmd = Cand()
    cmd.completed = {8824}
    order.clear()
    run(vim_mod.vim(cmd))
    check("vim: a done quest does nothing", order, [])
    check("vim: nothing was accepted",
          [c for c in cmd.calls if c[0] == "accept"], [])

    cmd = Cand()
    order.clear()
    run(vim_mod.vim(cmd))
    check("vim: the source's order", order, [
        "forge_helm", "rep7", "gear0", "buy:Rogue", "rank:Rogue", "gear1",
        "equip", "hunt:Ethereal Essencex250"])
    check("vim: accepted then turned in",
          [c[0] for c in cmd.calls if c[0] in ("accept", "turnin")],
          ["accept", "turnin"])
    check("vim: the turn-in is for 8824", cmd.calls[-1], ("turnin", 8824, -1))

    cmd = Cand()
    order.clear()
    run(vim_mod.vim(cmd, sell_quest_class=True))
    check("vim: sells the class when asked", cmd.calls[-1], ("sell", "Rogue", 1))

    # The chain: Pneuma pulls Anima -> Examen -> Vim, in that order.
    cmd = Cand()
    order.clear()
    run(pneuma_mod.pneuma(cmd))
    accepted = [c[1] for c in cmd.calls if c[0] == "accept"]
    check("chain: every quest in order", accepted, [8824, 8825, 8826, 8827])
    check("chain: each class is ranked",
          [entry for entry in order if entry.startswith("rank:")],
          ["rank:Rogue", "rank:Healer", "rank:Warrior", "rank:Mage"])
    check("chain: essence amounts",
          [entry for entry in order if entry.startswith("hunt:")],
          ["hunt:Ethereal Essencex250", "hunt:Ethereal Essencex250",
           "hunt:Ethereal Essencex650", "hunt:Ethereal Essencex650"])
    check("chain: Blacksmithing is farmed once",
          [entry for entry in order if entry.startswith("rep")], ["rep7"])

    cmd = Cand()
    cmd.completed = {8825, 8826, 8827}
    order.clear()
    run(examen_mod.examen(cmd))
    check("examen: a done quest does nothing", order, [])
    cmd = Cand()
    cmd.completed = {8827}
    order.clear()
    run(anima_mod.anima(cmd))
    check("anima: pulls examen only", order.count("rep7"), 1)
finally:
    restore(vim_mod, leaf)

# ============================================================================
# 12. Dragonslayer General and Burning Blade
# ============================================================================
from bot.other.classes import dragonslayer_general as dg  # noqa: E402
from bot.other.weapons import burning_blade as bb  # noqa: E402

ds_order = []


async def ds_gold(cmd, quant=0):
    ds_order.append(f"gold{quant}")


async def ds_kill(cmd, quest, map_name, monster):
    ds_order.append(f"story{quest}:{monster}")


async def ds_buy(cmd, shop, item, qty=1, map_name=None, shop_item_id=0):
    ds_order.append(f"buy{shop}:{item if isinstance(item, str) else 'id'}")


async def ds_rank(cmd, name="", item_id=0, gear_restore=True):
    ds_order.append(f"rank:{name}")


async def ds_gear(cmd, restore=False, enh_after=False):
    ds_order.append(f"gear{int(restore)}")


async def ds_hunt(cmd, item, qty, map_name, **kwargs):
    ds_order.append(f"hunt:{item}x{qty}")


async def ds_equip(cmd, solo=False):
    ds_order.append(f"equip:{int(solo)}")


leaf = patch(dg, farm_gold=ds_gold, kill_quest=ds_kill, buy_item=ds_buy,
             advance_class=ds_rank, gear_store=ds_gear, hunt_item=ds_hunt,
             equip_class=ds_equip, check_class_rank=lambda cmd, name: 0)
try:
    cmd = Cand([ItemInventory({"sName": "Dragonslayer General", "ItemID": 35996,
                               "iQty": 1})])
    ds_order.clear()
    run(dg.get_ds_general(cmd))
    check("dsg: owned -> only the rank-up", ds_order,
          ["gear0", "rank:Dragonslayer General"])

    cmd = Cand()
    ds_order.clear()
    run(dg.get_ds_general(cmd, rank_up_class=False))
    check("dsg: the source's order", ds_order, [
        "gear0", "gold30000",
        "story165:Wyvern", "story166:Bronze Draconian",
        "story167:Dark Draconian", "story168:Red Dragon",
        "gear0", "buy38:Dragonslayer", "rank:Dragonslayer", "gear1",
        "equip:0",
        "hunt:Enchanted Scalex75", "hunt:Dragon Clawx100",
        "buy1286:id"])
    check("dsg: the scale quest was registered",
          ("register", dg.SCALE_QUEST) in cmd.calls, True)
    check("dsg: registered quests cancelled",
          ("cancel_quests",) in cmd.calls, True)
    check("dsg: no rank-up when it is off",
          [entry for entry in ds_order if entry.startswith("rank:")],
          ["rank:Dragonslayer"])
finally:
    restore(dg, leaf)

bb_order = []


async def bb_hunt(cmd, item, qty, map_name, **kwargs):
    bb_order.append((item, qty, map_name, kwargs.get("cell"),
                     kwargs.get("monster_name")))


async def bb_wait(cmd, item, qty=1):
    bb_order.append(("wait", item))


async def bb_equip(cmd, solo=False):
    bb_order.append(("solo", solo))


leaf = patch(bb, hunt_item=bb_hunt, wait_for_item=bb_wait, equip_class=bb_equip)
try:
    cmd = Cand([ItemInventory({"sName": "Burning Blade", "ItemID": 31058,
                               "iQty": 1})])
    bb_order.clear()
    run(bb.get_burning_blade(cmd))
    check("blade: owned -> nothing", bb_order, [])

    cmd = Cand()
    bb_order.clear()
    run(bb.get_burning_blade(cmd))
    check("blade: kills the Warlord at r7/Left", bb_order, [
        ("solo", True),
        ("Burning Blade", 1, "lostruinswar", "r7", "Diabolical Warlord"),
        ("wait", "Burning Blade")])
finally:
    restore(bb, leaf)

print(f"passed {passed}   failed {len(failures)}")
if failures:
    for line in failures:
        print("FAIL", line)
    raise SystemExit(1)
print("core helpers tests OK")
