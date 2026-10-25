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
        self.BANK = []
        self.is_member = True
        self.LEVEL = 80
        self.GOLD = 0
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

    def request_relogin(self, reason=""):
        self.logs.append(f"relogin: {reason}")


class Cand:
    def __init__(self, inventory=(), quests=None, accept=True, turn_in=True):
        self.bot = Bot(Player(inventory))
        self.quests = quests or {}
        self.rewards = {}
        self.completed = set()
        self.ranks = {}
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

    def stop_aggro(self):
        self.calls.append(("stop_aggro",))

    def farming_logger(self, item, qty=1, is_temp=False):
        self.calls.append(("farming_logger", item, qty))

    def get_quant_item(self, item):
        held = self.bot.player.get_item_inventory(item)
        return int(held.qty) if held is not None else 0

    def pass_guard(self, label, max_quiet_passes=3):
        class Guard:
            def __init__(self):
                self.ticks = 0

            async def tick(self):
                self.ticks += 1
                return self.ticks < 2
        return Guard()

    def is_still_connected(self):
        return True

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

    async def jump_cell(self, cell, pad="Left"):
        self.calls.append(("cell", cell, pad))

    async def sleep(self, milliseconds):
        self.calls.append(("sleep", milliseconds))

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

    def get_faction_rank(self, name):
        return self.ranks.get(name.lower(), 0)


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

# ============================================================================
# 13. Throne of Darkness, the three classes and Blade of Awe
# ============================================================================
from bot.story.throne_of_darkness import core_tod as tod  # noqa: E402
from bot.other.classes import blood_sorceress as bs  # noqa: E402
from bot.other.classes import scarlet_sorceress as ss  # noqa: E402
from bot.other.classes import blaze_binder as bz  # noqa: E402
from bot import core_farms as farms_mod  # noqa: E402

tod_order = []


async def tod_kill(cmd, quest, map_name, monster):
    tod_order.append(f"kill{quest}")


async def tod_map(cmd, quest, map_name, item_ids, qty=1):
    tod_order.append(f"map{quest}")


async def tod_hunt(cmd, item, qty, map_name, **kwargs):
    tod_order.append(f"hunt:{item}")


async def tod_hunt_id(cmd, item_id, qty, map_name, **kwargs):
    tod_order.append(f"huntid:{item_id}@{kwargs.get('monster_map_id')}")


async def tod_equip(cmd, solo=False):
    tod_order.append(f"equip{int(solo)}")


leaf = patch(tod, kill_quest=tod_kill, map_item_quest=tod_map,
             hunt_item=tod_hunt, hunt_item_by_id=tod_hunt_id,
             equip_class=tod_equip,
             item_id_by_name=lambda cmd, quest, name: 9000 + quest)
try:
    cmd = Cand()
    cmd.completed = {5313, 5332}
    tod_order.clear()
    run(tod.tower_of_mirrors(cmd))
    check("tod: a done tower does nothing", tod_order, [])

    cmd = Cand()
    cmd.completed = {5313}
    tod_order.clear()
    run(tod.tower_of_mirrors(cmd))
    accepted = [c[1] for c in cmd.calls if c[0] == "accept"]
    check("tod: every tower quest in order", accepted,
          [5314, 5315, 5316, 5317, 5318, 5319, 5320, 5321, 5322, 5323, 5324,
           5325, 5326, 5327, 5328, 5329, 5332])
    check("tod: 5330/5331 go through the story helpers",
          [entry for entry in tod_order if entry in ("kill5330", "map5331")],
          ["kill5330", "map5331"])
    check("tod: the map-id bosses are hunted by id",
          [entry for entry in tod_order if entry.startswith("huntid:")],
          ["huntid:9000;a@36" if False else "huntid:" + str(9000 + q) + "@" + str(i)
           for q, i in ((5317, 36), (5320, 40), (5323, 45), (5326, 49),
                        (5329, 52), (5332, 32))])
finally:
    restore(tod, leaf)

bs_order = []


async def bs_hunt(cmd, item_id, qty, map_name, **kwargs):
    bs_order.append((item_id, qty, kwargs.get("cell"),
                     kwargs.get("monster_map_id")))


async def bs_rank(cmd, name="", item_id=0, gear_restore=True):
    bs_order.append(("rank", item_id or name))


async def bs_equip(cmd, solo=False):
    bs_order.append(("solo", solo))


leaf = patch(bs, hunt_item_by_id=bs_hunt, advance_class=bs_rank,
             equip_class=bs_equip)
try:
    cmd = Cand([ItemInventory({"sName": "Blood Sorceress", "ItemID": 36298,
                               "iQty": 1})])
    bs_order.clear()
    run(bs.get_bsorc(cmd))
    check("bsorc: owned -> ranked by id", bs_order, [("rank", 36298)])

    cmd = Cand()
    bs_order.clear()
    run(bs.get_bsorc(cmd, rank_up_class=False))
    check("bsorc: the groglurk at r16/Top", bs_order,
          [("solo", True), (36298, 1, "r16", 32)])
finally:
    restore(bs, leaf)

ss_order = []


async def ss_tower(cmd):
    ss_order.append("tower")


async def ss_bsorc(cmd, *args, **kwargs):
    ss_order.append("bsorc")
    # ``GetBSorc``'s own rank-up leaves the class at rank 10.
    cmd.bot.player.INVENTORY.append(
        ItemInventory({"sName": "Blood Sorceress", "sES": "ar",
                       "ItemID": 36298, "iQty": 302500}))


async def ss_chain(cmd, quest, item_id=-1):
    ss_order.append(f"chain{quest}")
    return True


async def ss_exp(cmd, level=100, rank_up_class=False):
    ss_order.append(f"exp{level}")


async def ss_rank(cmd, name="", item_id=0, gear_restore=True):
    ss_order.append(f"rank:{item_id or name}")


async def ss_enhance(cmd, item, type_, *args, **kwargs):
    ss_order.append(f"enh:{item}")


async def ss_wait(cmd, item, qty=1):
    ss_order.append(f"wait:{item}")


leaf = patch(ss, tower_of_mirrors=ss_tower, get_bsorc=ss_bsorc,
             chain_complete=ss_chain, farm_experience=ss_exp,
             advance_class=ss_rank, enhance_item=ss_enhance,
             wait_for_item=ss_wait)
try:
    cmd = Cand([ItemInventory({"sName": "Scarlet Sorceress", "ItemID": 1,
                               "iQty": 1})])
    ss_order.clear()
    run(ss.get_ssorc(cmd))
    check("scarlet: owned -> ranked", ss_order, ["rank:Scarlet Sorceress"])

    cmd = Cand()
    ss_order.clear()
    run(ss.get_ssorc(cmd, rank_up_class=False))
    check("scarlet: the source's order", ss_order, [
        "tower", "bsorc", "wait:Blood Sorceress", "enh:Blood Sorceress",
        "exp50", "chain6236", "wait:Scarlet Sorceress",
        "enh:Scarlet Sorceress"])
    check("scarlet: the class quest runs", "chain6236" in ss_order, True)
finally:
    restore(ss, leaf)

bz_order = []


async def bz_pyro(cmd):
    bz_order.append("pyromancer")


async def bz_kill(cmd, *args, **kwargs):
    bz_order.append("kill")


async def bz_gear(cmd, restore=False, enh_after=False):
    bz_order.append(f"gear{int(restore)}")


async def bz_buy(cmd, shop, item, qty=1, map_name=None, shop_item_id=0):
    bz_order.append(f"buy{shop}:{item}")


async def bz_rank(cmd, name="", item_id=0, gear_restore=True):
    bz_order.append(f"rank:{name}")


leaf = patch(bz, pyromancer=bz_pyro, kill_once=bz_kill, gear_store=bz_gear,
             buy_item=bz_buy, advance_class=bz_rank)
try:
    cmd = Cand([ItemInventory({"sName": "Blaze Binder", "ItemID": 2,
                               "iQty": 1})])
    bz_order.clear()
    run(bz.get_class(cmd))
    check("blaze: owned -> ranked", bz_order, ["rank:Blaze Binder"])

    cmd = Cand()
    bz_order.clear()
    run(bz.get_class(cmd, rank_up_class=False))
    check("blaze: pyro, one point, two sigils, the class", bz_order, [
        "pyromancer", "gear0", "kill", "gear1", "buy1142:Darkness Sigil",
        "buy1142:Flame Sigil", "buy1140:Blaze Binder",
        "rank:Blaze Binder"])
finally:
    restore(bz, leaf)

boa_order = []


async def boa_kill(cmd, *args, **kwargs):
    boa_order.append("kill")
    cmd.ranks["blade of awe"] = 10


def boa_save(cmd, on=True, previous_map=""):
    boa_order.append(f"save{int(on)}")


def boa_check(cmd):
    return False


async def boa_exec(cmd):
    boa_order.append("exec")


async def boa_hunt(cmd, item, qty, map_name, **kwargs):
    boa_order.append(f"hunt:{item}")


async def boa_equip(cmd, solo=False):
    boa_order.append(f"equip{int(solo)}")


async def boa_buy(cmd, shop, item, qty=1, map_name=None, shop_item_id=0):
    boa_order.append(f"buy{shop}")


leaf = patch(farms_mod, kill_once=boa_kill, saved_state=boa_save,
             check_save_state=boa_check, execute_save_state=boa_exec,
             hunt_item=boa_hunt, equip_class=boa_equip, buy_item=boa_buy)
from bot.nation import core_nation as nation_mod  # noqa: E402


async def boa_escherion(cmd, item, qty=1):
    boa_order.append(f"hunt:{item}")


real_escherion = nation_mod.kill_escherion
nation_mod.kill_escherion = boa_escherion
try:
    cmd = Cand()
    cmd.completed = {2937}
    boa_order.clear()
    run(farms_mod.blade_of_awe_rep(cmd))
    check("boa: unlocks already done -> only the rep + buy", boa_order,
          ["save1", "equip0", "kill", "save0", "buy631"])

    cmd = Cand()
    cmd.completed = {2933}
    boa_order.clear()
    run(farms_mod.blade_of_awe_rep(cmd, farm_boa=False))
    check("boa: quests skipped when done",
          [c[1] for c in cmd.calls if c[0] == "accept"],
          [2934, 2935, 2936, 2937])
    check("boa: the last quest hunts Escherion's rune",
          any(entry == "hunt:Runes Found!" for entry in boa_order), True)
finally:
    nation_mod.kill_escherion = real_escherion
    restore(farms_mod, leaf)

# ============================================================================
# 14. CoreVHL: the rank-up goes through the ported RankUpClass
# ============================================================================
from bot.nation.vhl import core_vhl as vhl  # noqa: E402

vhl_ranked = []
real_vhl_rank = vhl.rank_up


async def spy_vhl_rank(cmd, name="", item_id=0, gear_restore=True):
    vhl_ranked.append(name)


vhl.rank_up = spy_vhl_rank
try:
    owned = [ItemInventory({"sName": "Void Highlord", "sES": "ar",
                            "ItemID": 1, "iQty": 1})]
    run(vhl.get_vhl(Cand(owned)))
    check("vhl: owned -> the class is ranked", vhl_ranked, ["Void Highlord"])

    vhl_ranked.clear()
    run(vhl.get_vhl(Cand(owned), rank_up_class=False))
    check("vhl: rank_up_class=False -> no rank-up", vhl_ranked, [])
finally:
    vhl.rank_up = real_vhl_rank

# ============================================================================
# 15. Lair and Dragonslayer
# ============================================================================
from bot.story import lair as lair_mod  # noqa: E402
from bot.other.classes import dragonslayer as dsl  # noqa: E402

lair_order = []


async def lair_kill(cmd, quest, map_name, monster):
    lair_order.append(f"kill{quest}")


async def lair_map(cmd, quest, map_name, item_ids, qty=1):
    lair_order.append(f"map{quest}")


async def lair_chain(cmd, quest, item_id=-1):
    lair_order.append(f"chain{quest}")
    return True


leaf = patch(lair_mod, kill_quest=lair_kill, map_item_quest=lair_map,
             chain_complete=lair_chain)
try:
    cmd = Cand()
    cmd.completed = {169}
    lair_order.clear()
    run(lair_mod.galanoth(cmd))
    check("lair: 169 done -> the line is skipped", lair_order, [])

    cmd = Cand()
    lair_order.clear()
    run(lair_mod.do_all(cmd))
    check("lair: the source's order", lair_order, [
        "kill165", "kill166", "kill167", "kill168",
        "kill1492", "map1493", "kill1494", "map1495",
        "chain1502", "map1503", "kill1504", "kill1505", "kill1506", "kill1507"])

    cmd = Cand()
    cmd.bot.player.is_member = False
    lair_order.clear()
    run(lair_mod.duncan(cmd))
    check("lair: Duncan is members only", lair_order, [])
    check("lair: says so", any("Member" in line for line in cmd.bot.logs), True)
finally:
    restore(lair_mod, leaf)

dsl_order = []


async def dsl_gal(cmd):
    dsl_order.append("galanoth")


async def dsl_buy(cmd, shop, item, qty=1, map_name=None, shop_item_id=0):
    dsl_order.append(("buy", shop, item, map_name))


async def dsl_rank(cmd, name="", item_id=0, gear_restore=True):
    dsl_order.append(("rank", name))


leaf = patch(dsl, galanoth=dsl_gal, buy_item=dsl_buy, advance_class=dsl_rank)
try:
    cmd = Cand([ItemInventory({"sName": "Dragonslayer", "ItemID": 1,
                               "iQty": 1})])
    dsl_order.clear()
    run(dsl.get_dragonslayer(cmd))
    check("dragonslayer: owned -> ranked", dsl_order,
          [("rank", "Dragonslayer")])

    cmd = Cand()
    dsl_order.clear()
    run(dsl.get_dragonslayer(cmd, rank_up_class=False))
    check("dragonslayer: Galanoth then the shop", dsl_order,
          ["galanoth", ("buy", 38, "Dragonslayer", "lair")])
finally:
    restore(dsl, leaf)

# ============================================================================
# 16. Glacera's FrozenTower and Cryomancer
# ============================================================================
from bot.story import glacera as gla  # noqa: E402
from bot.other.classes import cryomancer as cryo  # noqa: E402

gla_order = []


async def gla_map(cmd, quest, map_name, item_ids, qty=1):
    gla_order.append(f"map{quest}")


async def gla_kill(cmd, quest, map_name, monster):
    gla_order.append(f"kill{quest}")


async def gla_hunt(cmd, item, qty, map_name, **kwargs):
    gla_order.append(f"hunt:{item}")


async def gla_prog(cmd, quest, *args, **kwargs):
    return False


async def gla_equip(cmd, solo=False):
    gla_order.append("equip")


leaf = patch(gla, map_item_quest=gla_map, kill_quest=gla_kill,
             hunt_item=gla_hunt, quest_progression=gla_prog,
             equip_class=gla_equip)
try:
    cmd = Cand()
    cmd.completed = {3937}
    gla_order.clear()
    run(gla.frozen_tower(cmd))
    check("glacera: a done tower does nothing", gla_order, [])

    cmd = Cand()
    gla_order.clear()
    run(gla.do_all(cmd, cryomancer=True))
    check("glacera: the tower starts at 3907", gla_order[:4],
          ["map3907", "kill3908", "map3909", "map3910"])
    check("glacera: the tower ends at 3937", gla_order[-1],
          "hunt:Fangbeasts defeated")
    check("glacera: the hand blocks are accepted in order",
          [c[1] for c in cmd.calls if c[0] == "accept"],
          [3911, 3919, 3920, 3921, 3925, 3935, 3936, 3937])
    check("glacera: a cryomancer run stops after the tower",
          any("are not ported yet" in line for line in cmd.bot.logs), False)

    cmd = Cand()
    gla_order.clear()
    run(gla.do_all(cmd))
    check("glacera: every region runs, none is skipped",
          any("are not ported" in line for line in cmd.bot.logs), False)
    check("glacera: the run ends in IceDungeon", gla_order[-1],
          "hunt:Kyanos' Approval")
finally:
    restore(gla, leaf)

cryo_order = []


async def cryo_glac(cmd, cryomancer=False):
    cryo_order.append(("glac", cryomancer))


async def cryo_daily(cmd):
    cryo_order.append("daily")


async def cryo_rank(cmd, name="", item_id=0, gear_restore=True):
    cryo_order.append(("rank", name))


leaf = patch(cryo, glacera_do_all=cryo_glac, daily_cryomancer=cryo_daily,
             advance_class=cryo_rank)
try:
    cmd = Cand([ItemInventory({"sName": "Cryomancer", "ItemID": 1, "iQty": 1})])
    cryo_order.clear()
    run(cryo.get_cryomancer(cmd))
    check("cryomancer: owned -> ranked", cryo_order, [("rank", "Cryomancer")])

    cmd = Cand()
    cryo_order.clear()
    run(cryo.get_cryomancer(cmd, rank_up_class=False))
    check("cryomancer: the tower, then the class daily", cryo_order,
          [("glac", True), "daily"])
finally:
    restore(cryo, leaf)

# ============================================================================
# 17. GlaceraREP dan Glacial Berserker
# ============================================================================
from bot.other.classes import glacial_berserker as gb  # noqa: E402

gb_order = []


async def gb_glac(cmd, cryomancer=False):
    gb_order.append(("glac", cryomancer))


async def gb_rep(cmd, rank=10):
    gb_order.append(("rep", rank))


async def gb_buy(cmd, shop, item, qty=1, map_name=None, shop_item_id=0):
    gb_order.append(("buy", shop, item, shop_item_id))


async def gb_rank(cmd, name="", item_id=0, gear_restore=True):
    gb_order.append(("rank", name))


leaf = patch(gb, glacera_do_all=gb_glac, glacera_rep=gb_rep, buy_item=gb_buy,
             advance_class=gb_rank)
try:
    cmd = Cand([ItemInventory({"sName": "Glacial Berserker", "ItemID": 1,
                               "iQty": 1})])
    gb_order.clear()
    run(gb.get_gb(cmd))
    check("gberserker: owned -> ranked", gb_order,
          [("rank", "Glacial Berserker")])

    cmd = Cand()
    gb_order.clear()
    run(gb.get_gb(cmd, rank_up_class=False))
    check("gberserker: story, rep, then the shop", gb_order,
          [("glac", False), ("rep", 10),
           ("buy", 1339, "Glacial Berserker", 22266)])
finally:
    restore(gb, leaf)

rep_events = []
real_rep = {name: getattr(farms_mod, name) for name in
            ("saved_state", "check_save_state", "execute_save_state",
             "kill_once", "equip_class")}


def rep_save(cmd, on=True, previous_map=""):
    rep_events.append(("save", on, previous_map))


def rep_check(cmd):
    return False


async def rep_exec(cmd):
    rep_events.append(("exec",))


async def rep_kill(cmd, *args, **kwargs):
    rep_events.append(("kill",) + args[1:])
    cmd.ranks["glacera"] = 10


async def rep_equip(cmd, solo=False):
    rep_events.append(("equip",))


farms_mod.saved_state = rep_save
farms_mod.check_save_state = rep_check
farms_mod.execute_save_state = rep_exec
farms_mod.kill_once = rep_kill
farms_mod.equip_class = rep_equip
try:
    cmd = Cand()
    run(farms_mod.glacera_rep(cmd))
    check("glacera rep: locked quests are reported", rep_events, [])
    check("glacera rep: says what to run",
          any("not unlocked" in line for line in cmd.bot.logs), True)

    cmd = Cand()
    cmd.completed = {5601}
    rep_events.clear()
    run(farms_mod.glacera_rep(cmd))
    check("glacera rep: armed, one kill, disarmed",
          [entry[0] for entry in rep_events],
          ["equip", "save", "kill", "save"])
    check("glacera rep: the war quests are registered",
          [c[1] for c in cmd.calls if c[0] == "register"], [5597, 5598, 5599, 5600])
finally:
    for name, fn in real_rep.items():
        setattr(farms_mod, name, fn)

# ============================================================================
# 18. Yokai dan DragonSoul Shinobi
# ============================================================================
from bot.story import yokai as yok  # noqa: E402
from bot.other.classes import dragon_shinobi as dss  # noqa: E402

yok_order = []


async def yok_kill(cmd, quest, map_name, monster):
    yok_order.append(f"kill{quest}")


async def yok_map(cmd, quest, map_name, item_ids, qty=1):
    yok_order.append(f"map{quest}")


async def yok_hunt(cmd, item, qty, map_name, **kwargs):
    yok_order.append(f"hunt:{item}")


async def yok_hunt_id(cmd, item_id, qty, map_name, **kwargs):
    yok_order.append(f"huntid:{kwargs.get('monster_map_id')}")


async def yok_prog(cmd, quest, *args, **kwargs):
    return False


async def yok_buyq(cmd, quest, map_name, shop, item):
    yok_order.append(f"buyquest{quest}")


async def yok_equip(cmd, solo=False):
    yok_order.append(f"equip{int(solo)}")


leaf = patch(yok, kill_quest=yok_kill, map_item_quest=yok_map,
             hunt_item=yok_hunt, hunt_item_by_id=yok_hunt_id,
             quest_progression=yok_prog, buy_quest=yok_buyq,
             equip_class=yok_equip,
             item_id_by_name=lambda cmd, quest, name: 9000 + quest)
try:
    cmd = Cand()
    cmd.completed = {6459, 6472, 6494}
    yok_order.clear()
    run(yok.do_quests(cmd))
    check("yokai: a done story does nothing", yok_order, [])

    cmd = Cand()
    yok_order.clear()
    run(yok.do_quests(cmd))
    accepted = [c[1] for c in cmd.calls if c[0] == "accept"]
    check("yokai: starts at 6450 and reaches 6494",
          (accepted[0], max(accepted)), (6450, 6494))
    check("yokai: the map-id hunts use the right monsters",
          [entry for entry in yok_order if entry.startswith("huntid:")],
          ["huntid:8", "huntid:7", "huntid:25", "huntid:15", "huntid:31"])
    check("yokai: 6478 buys its Wasabi", "buyquest6478" in yok_order, True)
finally:
    restore(yok, leaf)

dss_order = []


async def dss_yokai(cmd, *args, **kwargs):
    dss_order.append("yokai")


async def dss_kill(cmd, *args, **kwargs):
    dss_order.append(("kill", args, kwargs.get("monster")))
    return True


async def dss_buy(cmd, shop, item, qty=1, map_name=None, shop_item_id=0):
    dss_order.append(("buy", shop, item, shop_item_id))


async def dss_rank(cmd, name="", item_id=0, gear_restore=True):
    dss_order.append(("rank", name))


async def dss_equip(cmd, solo=False):
    dss_order.append(("equip", solo))


leaf = patch(dss, yokai_quests=dss_yokai, kill_once=dss_kill, buy_item=dss_buy,
             advance_class=dss_rank, equip_class=dss_equip)
try:
    cmd = Cand([ItemInventory({"sName": "DragonSoul Shinobi", "ItemID": 59476,
                               "iQty": 1})])
    dss_order.clear()
    run(dss.get_dss(cmd))
    check("shinobi: owned -> ranked", dss_order,
          [("rank", "DragonSoul Shinobi")])

    cmd = Cand()
    dss_order.clear()
    run(dss.get_dss(cmd, rank_up_class=False))
    check("shinobi: Yokai first, then the token hunt", dss_order[:3],
          ["yokai", ("equip", True),
           ("kill", ("shadowfortress",), "1st Head of Orochi")])
    check("shinobi: then the shop", dss_order[-1],
          ("buy", 1968, 59476, 8078))
    check("shinobi: the token quest is registered and cancelled",
          [c[1] for c in cmd.calls if c[0] == "register"], [7924])
    check("shinobi: cancelled afterwards",
          ("cancel_quests",) in cmd.calls, True)
finally:
    restore(dss, leaf)

# ============================================================================
# 19. XansLair and ArchPaladin
# ============================================================================
from bot.story import xans_lair as xl  # noqa: E402
from bot.other.classes import arch_paladin as ap  # noqa: E402
from bot.other.classes import paladin as pal  # noqa: E402

xl_order = []


async def xl_kill(cmd, quest, map_name, monster):
    xl_order.append(f"kill{quest}")


async def xl_map(cmd, quest, map_name, item_ids, qty=1):
    xl_order.append(f"map{quest}")


async def xl_hunt(cmd, item, qty, map_name, **kwargs):
    xl_order.append(f"hunt:{item}")


async def xl_prog(cmd, quest, *args, **kwargs):
    return False


leaf = patch(xl, kill_quest=xl_kill, map_item_quest=xl_map,
             hunt_item=xl_hunt, quest_progression=xl_prog)
try:
    cmd = Cand()
    cmd.completed = {1261, 1739, 1740, 2157}
    xl_order.clear()
    run(xl.do_all(cmd))
    check("xanslair: a done story does nothing", xl_order, [])

    cmd = Cand()
    xl_order.clear()
    run(xl.do_all(cmd))
    check("xanslair: volcano starts at 1242", xl_order[0], "kill1242")
    check("xanslair: the four regions run in order",
          [c[1] for c in cmd.calls if c[0] == "accept"][:1], [1243])
    check("xanslair: xantown jumps to the safe cell",
          ("cell", "r12", "Left") in cmd.calls, True)
    check("xanslair: Warlic's cave is last",
          [entry for entry in xl_order if entry.startswith("map")][-1], "map2157")
finally:
    restore(xl, leaf)

ap_order = []


async def ap_good(cmd, rank=10):
    ap_order.append("good_rep")


async def ap_quest(cmd, quest_id, body):
    ap_order.append(f"quest{quest_id}")
    await body()


async def ap_hunt(cmd, item, qty, map_name, **kwargs):
    ap_order.append(f"hunt:{item}")


async def ap_buy(cmd, shop, item, qty=1, map_name=None, shop_item_id=0):
    ap_order.append(("buy", shop, item if isinstance(item, str) else "id"))


async def ap_rank(cmd, name="", item_id=0, gear_restore=True):
    ap_order.append(f"rank:{name}")


async def ap_gear(cmd, restore=False, enh_after=False):
    ap_order.append(f"gear{int(restore)}")


async def ap_paladin(cmd, *args, **kwargs):
    ap_order.append("paladin")


async def ap_member(cmd):
    return False


async def ap_equip(cmd, solo=False):
    ap_order.append(f"equip{int(solo)}")


async def ap_chain(cmd, quest, item_id=-1):
    ap_order.append(f"chain{quest}")
    return True


async def _ap_gold(cmd, quant=0):
    ap_order.append("farm_gold")


async def _ap_bu(cmd, *args, **kwargs):
    ap_order.append("battle_under_b")


async def _ap_blod(cmd, *args, **kwargs):
    ap_order.append("unlock_mine_crafting")


async def _ap_kitten(cmd, *args, **kwargs):
    ap_order.append("doom_kitten")


async def _ap_xan(cmd, *args, **kwargs):
    ap_order.append("xans_lair")


async def _ap_sc(cmd, rank=10):
    ap_order.append("spellcrafting_rep")


leaf = patch(ap, good_rep=ap_good, _quest=ap_quest, hunt_item=ap_hunt,
             buy_item=ap_buy, advance_class=ap_rank, gear_store=ap_gear,
             get_paladin=ap_paladin, equip_class=ap_equip,
             chain_complete=ap_chain, farm_gold=_ap_gold,
             battle_under_b=_ap_bu, unlock_mine_crafting=_ap_blod,
             kill_doom_kitten=_ap_kitten, xans_lair_do_all=_ap_xan,
             spellcrafting_rep=_ap_sc)
try:
    cmd = Cand([ItemInventory({"sName": "ArchPaladin", "ItemID": 36920,
                               "iQty": 1})])
    ap_order.clear()
    run(ap.get_ap(cmd))
    check("archpaladin: owned -> ranked", ap_order, ["rank:ArchPaladin"])

    cmd = Cand()
    cmd.bot.player.is_member = False
    ap_order.clear()
    run(ap.get_ap(cmd, rank_up_class=False))
    check("archpaladin: Good rep first", ap_order[0], "good_rep")
    check("archpaladin: the quests in the source's order",
          [entry for entry in ap_order
           if isinstance(entry, str) and entry.startswith("quest")],
          ["quest5463", "quest5464", "quest5465", "quest5466", "quest5467",
           "quest5468", "quest5469", "quest5470"])
    check("archpaladin: bought at darkthronehub 1303",
          ap_order[-1], ("buy", 1303, "id"))

    cmd = Cand()                       # member by default in the stub
    ap_order.clear()
    run(ap.get_ap(cmd, rank_up_class=False))
    check("archpaladin: the member path uses Paladin + the oaths",
          [entry for entry in ap_order
           if isinstance(entry, str) and entry.startswith("chain54")],
          ["chain5471", "chain5472", "chain5473"])
    check("archpaladin: the member aptitude is 5474",
          "quest5474" in ap_order, True)
finally:
    restore(ap, leaf)

pal_order = []


async def pal_buy(cmd, shop, item, qty=1, map_name=None, shop_item_id=0):
    pal_order.append(item)


async def pal_rank(cmd, name="", item_id=0, gear_restore=True):
    pal_order.append(f"rank:{name}")


async def pal_rep(cmd, rank=10):
    pal_order.append(f"good{rank}")


leaf = patch(pal, buy_item=pal_buy, advance_class=pal_rank, good_rep=pal_rep)
try:
    cmd = Cand()
    run(pal.get_paladin(cmd))
    check("paladin: Warrior, Healer, rank both, rep, then the class", pal_order,
          ["Warrior", "Healer", "rank:Warrior", "rank:Healer", "good5",
           "Paladin", "rank:Paladin"])

    cmd = Cand()
    cmd.bot.player.is_member = False
    pal_order.clear()
    run(pal.get_paladin(cmd))
    check("paladin: members only", pal_order, [])
finally:
    restore(pal, leaf)

# ============================================================================
# 20. Mazumi, Tutorial badges, and the free boosts
# ============================================================================
from bot.story import mazumi as mz  # noqa: E402
from bot.story import tutorial as tut  # noqa: E402
from bot.core_farms import get_boost  # noqa: E402
from bot import core_farms as cf  # noqa: E402
from bot.other import free_boosts as fb  # noqa: E402

mz_order = []


async def mz_kill(cmd, quest, map_name, monster):
    mz_order.append(f"kill{quest}")


async def mz_hunt(cmd, item, qty, map_name, **kwargs):
    mz_order.append((item, kwargs.get("cell")))


async def mz_prog(cmd, quest, *args, **kwargs):
    return False


async def mz_equip(cmd, solo=False):
    mz_order.append(f"equip{int(solo)}")


leaf = patch(mz, kill_quest=mz_kill, hunt_item=mz_hunt,
             quest_progression=mz_prog, equip_class=mz_equip)
try:
    cmd = Cand()
    cmd.completed = {92}
    mz_order.clear()
    run(mz.mazumi_quests(cmd))
    check("mazumi: a done chain does nothing", mz_order, [])

    cmd = Cand()
    mz_order.clear()
    run(mz.mazumi_quests(cmd))
    check("mazumi: quest 90 first", mz_order[0], "kill90")
    check("mazumi: quest 91 keeps the Frogzard in West3",
          ("Frogzard's Lint Hoard", "West3") in mz_order, True)
    check("mazumi: quest 92 is fought as solo", "equip1" in mz_order, True)
finally:
    restore(mz, leaf)

tut_sent = []


async def tut_set(cmd, achievement_id, ia="ia0"):
    tut_sent.append(achievement_id)


leaf = patch(tut, set_achievement=tut_set)
try:
    cmd = Cand()
    run(tut.badges(cmd))
    check("tutorial: badges 22-31 in order", tut_sent, list(range(22, 32)))
    check("tutorial: goes to oaklore", ("join", "oaklore", None) in cmd.calls,
          True)
finally:
    restore(tut, leaf)

try:
    cmd = Cand([ItemInventory({"sName": "XP Boost! (10 min)", "iQty": 1})])
    run(get_boost(cmd, "XP", 1))
    check("boost: a stocked stack returns at once", cmd.calls, [])
    check("boost: and logs nothing", cmd.bot.logs, [])

    fished, hunted = [], []

    async def boost_fish(cmd, item_id, quant, quest):
        fished.append((item_id, quest))
        cmd.bot.player.INVENTORY.append(
            ItemInventory({"sName": "XP Boost! (10 min)", "iQty": quant}))

    async def boost_hunt(cmd, item, qty, map_name, **kwargs):
        hunted.append(item)

    async def boost_equip(cmd, solo=False):
        return None

    leaf = patch(cf, get_fish=boost_fish, hunt_item=boost_hunt,
                 equip_class=boost_equip)
    try:
        cmd = Cand()
        cmd.completed = {1615}
        cmd.ranks["fishing"] = 2
        run(get_boost(cmd, "XP", 1))
        check("boost: quest 1614 is the XP one", fished, [(10850, 1614)])
        check("boost: slime sauce is the quest's other drop", hunted,
              ["Slime Sauce"])
    finally:
        restore(cf, leaf)

    # the reference's stale `allQuantitiesMet` is recomputed: three stacks and
    # the loop is over on the first look
    cmd = Cand([ItemInventory({"sName": fb.GOLD_BOOST, "iQty": 10}),
                ItemInventory({"sName": fb.CLASS_BOOST, "iQty": 10})])
    hunted = []

    async def fb_hunt(cmd, quest, *targets, log=True):
        hunted.append(quest)

    async def fb_equip(cmd, solo=False):
        return None

    leaf = patch(fb, hunt_monster_quest=fb_hunt, equip_class=fb_equip)
    try:
        run(fb.get_boosts_select(cmd, 10, 10, 0))
        check("boosts: 0 rep boosts needs nothing", hunted, [])
    finally:
        restore(fb, leaf)
finally:
    pass

# ============================================================================
# 21. SynderesMerge
# ============================================================================
from bot.other.merge_shops import synderes_merge as sy  # noqa: E402

merged = []


async def sy_merge(cmd, map_name, shop_id, find_ingredients=None,
                   buy_only_this=None, item_blacklist=(), shop_item_id=0):
    merged.append((map_name, shop_id, buy_only_this))


leaf = patch(sy, start_buy_all_merge=sy_merge)
try:
    cmd = Cand()
    run(sy.no_bots_armor(cmd))
    check("synderes: the armor is the only entry asked for", merged,
          [("enemyforest", 332, "NO BOTS Armor")])

    cmd = Cand([ItemInventory({"sName": "NO BOTS Armor", "iQty": 1})])
    merged.clear()
    run(sy.no_bots_armor(cmd))
    check("synderes: an owned armor merges nothing", merged, [])

    cmd = Cand()
    await_unknown = run(sy.find_ingredients(cmd, 1, "Some Other Item", 1))
    check("synderes: an unknown ingredient says so",
          "The bot hasn't been taught how to get Some Other Item."
          in cmd.bot.logs, True)
finally:
    restore(sy, leaf)

print(f"passed {passed}   failed {len(failures)}")
if failures:
    for line in failures:
        print("FAIL", line)
    raise SystemExit(1)
print("core helpers tests OK")
