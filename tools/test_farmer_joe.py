"""Farmer Joe kit: class resolution, the level ladder, the extras.

    python tools/test_farmer_joe.py

Optional suite: it is not part of ``AGENTS.md``'s "green before done" list, so run
it when this kit changes.  ``test_imports.py`` already imports the modules, and
``tools/check_log_scope.py`` covers the log rule.

``bot/other/farm_joe_kits/core_farmer_joe.py`` is the port of the reference's
Kit core.  What matters here is the decisions it makes before any packet -- which
class it resolves to, when it decides there is nothing to redo, which bracket
handlers it calls and in what order, and that every log line it emits is the
reference's own text.

Everything runs against a stub Command, so nothing touches the network.
"""
import asyncio
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bot.other.farm_joe_kits import core_farmer_joe as joe  # noqa: E402
from model.inventory import ItemType  # noqa: E402


class _Item:
    """An inventory item: slot, name and quantity are what get read."""

    def __init__(self, name, qty=1, slot=None):
        self.s_name = name
        self.item_name = name.lower()
        self.s_es = slot or ItemType.CLASS.value
        self.qty = qty
        self.is_equipped = False
        #: Read by ``core_advanced.rank_up_class`` when a class is resolved.
        self.item_id = "0"
        self.is_upgrade = False
        self.enh_level = 100


class _Player:
    def __init__(self, level=30):
        self.USER = "me"
        self.LEVEL = level
        self.INVENTORY = []
        self.BANK = []

    def _find(self, source, name):
        for item in source:
            if item.item_name == name.lower():
                return item
        return None

    def get_item_inventory(self, name):
        return self._find(self.INVENTORY, name)

    def get_item_temp_inventory(self, name):
        return None

    def get_item_bank(self, name):
        return self._find(self.BANK, name)


class _ShopItem:
    """Mirrors ``ItemInventory`` as a shop entry."""

    def __init__(self, name, item_id=0, shop_item_id=None, faction="None",
                 required_rep=0, level=0, cost=0, is_acs=False):
        self.item_name = name.lower()
        self.item_id = item_id
        self.shop_item_id = item_id if shop_item_id is None else shop_item_id
        self.required_faction = faction
        self.required_rep = required_rep
        self.required_quest = ""
        self.level = level
        self.cost = cost
        self.is_acs = is_acs


class _Shop:
    def __init__(self, shop_id, items):
        self.shop_id = shop_id
        self.items = [i if isinstance(i, _ShopItem) else _ShopItem(i)
                      for i in items]


class _Bot:
    def __init__(self):
        self.farmClass = None
        self.soloClass = None
        self.player = _Player()
        self.logs = []
        self.sent = []
        self.loaded_shop_datas = []

    def write_message(self, msg):
        self.sent.append(msg)

    def log(self, *args):
        self.logs.append(" ".join(map(str, args)))

    def debug(self, *args):
        self.logs.append(" ".join(map(str, args)))


class Stub:
    """Duck-typed Command: records calls, never touches the network."""

    def __init__(self, inventory=None, level=30, solo=None, farm=None,
                 classes_held=(), items=(), shops=()):
        self.bot = _Bot()
        self.bot.player.LEVEL = level
        self.bot.farmClass = farm
        self.bot.soloClass = solo
        self.inv = dict(inventory or {})
        held = (dict(classes_held) if isinstance(classes_held, dict)
                else {name: 1 for name in classes_held})
        self.bot.player.INVENTORY = [_Item(name, qty)
                                     for name, qty in held.items()]
        self.bot.player.INVENTORY += list(items)
        self.bot.loaded_shop_datas = list(shops)
        self.calls = []

    # --- logging --------------------------------------------------------
    def kinds(self):
        return [c[0] for c in self.calls]

    # --- sync -----------------------------------------------------------
    def get_player(self):
        return self.bot.player

    def get_solo_class(self):
        return self.bot.soloClass

    def get_farm_class(self):
        return self.bot.farmClass

    def get_quant_item(self, name):
        return self.inv.get(name, 0)

    def is_in_inventory(self, name, qty=1, operator=">=", isTemp=False):
        if self.inv.get(name, 0) >= qty:
            return True
        found = self.bot.player.get_item_inventory(name)
        return found is not None and found.qty >= qty

    def is_in_bank(self, name, qty=1, operator=">="):
        return False

    def is_in_inventory_or_bank(self, name, qty=1, operator=">=",
                                isTemp=False):
        return self.is_in_inventory(name, qty, operator, isTemp)

    def is_still_connected(self):
        return True

    def is_not_in_map(self, map_name):
        return map_name != getattr(self, "_map", None)

    def is_not_in_cell(self, cell):
        return False

    def farming_logger(self, *args):
        self.calls.append(("farming_logger", args))

    def add_drop(self, names):
        self.calls.append(("add_drop", names))
        self._wanted = names if isinstance(names, str) else names[0]

    def get_equipped_class(self):
        return None

    def can_turnin_quest(self, quest_id):
        return False

    # --- async ----------------------------------------------------------
    async def sleep(self, ms):
        pass

    async def equip_item(self, name):
        self.calls.append(("equip_item", name))
        return True

    async def join_map(self, map_name, room=None, safe_leave=True):
        self.calls.append(("join_map", map_name))
        self._map = map_name

    async def jump_cell(self, cell, pad):
        self.calls.append(("jump_cell", cell, pad))

    async def jump_to_monster(self, *args, **kwargs):
        self.calls.append(("jump_to_monster",))

    async def leave_combat(self, safe_leave=True):
        self.calls.append(("leave_combat",))

    async def bank_to_inv(self, names):
        self.calls.append(("bank_to_inv", names))

    async def sell_item(self, name, qty=1):
        self.calls.append(("sell_item", name))
        self.inv[name] = max(0, self.inv.get(name, 0) - qty)

    async def inv_to_bank(self, names):
        self.calls.append(("inv_to_bank", tuple(names)))

    async def has_item(self, name, qty=1, operator=">=", isTemp=False):
        return self.is_in_inventory(name, qty)

    async def has_any_item(self, names):
        for name in names:
            if await self.has_item(name):
                return True
        return False

    async def has_item_id(self, item_id):
        self.calls.append(("has_item_id", item_id))
        return False

    async def use_next_skill(self, *args, **kwargs):
        self.calls.append(("use_next_skill",))
        if getattr(self, "_wanted", None):
            self.inv[self._wanted] = self.inv.get(self._wanted, 0) + 1

    async def ensure_accept_quest(self, quest_id, max_attempts=3):
        self.calls.append(("ensure_accept_quest", quest_id))
        return True

    async def ensure_turn_in_quest(self, quest_id, item_id=-1, amount=1):
        self.calls.append(("ensure_turn_in_quest", quest_id))
        return True

    async def ensure_load_shop(self, shop_id):
        self.calls.append(("ensure_load_shop", shop_id))
        return True

    async def buy_item(self, shop_id, item_name, qty=1, shop_item_id=0):
        self.calls.append(("buy_item", shop_id, item_name, qty, shop_item_id))


def main() -> None:
    joe._reported.clear()

    # ``rank_up_class`` drives the arena and probes enhancement unlocks; the
    # rank-up itself is covered in test_core_helpers, so here it is recorded.
    ranked_classes: list = []
    real_rank_up = joe.rank_up_class

    async def spy_rank_up(cmd, name="", item_id=0, gear_restore=True):
        ranked_classes.append(name or item_id)

    joe.rank_up_class = spy_rank_up

    # --- AnyRank10 ------------------------------------------------------
    ranked = Stub(classes_held={"Master Ranger": joe.RANK_10_CLASS_POINTS})
    assert joe.any_rank10(ranked, ["Master Ranger"]) is True
    short = Stub(classes_held={"Master Ranger": 1000})
    assert joe.any_rank10(short, ["Master Ranger"]) is False
    assert joe.any_rank10(short, ["Nothing At All"]) is False
    print("rank10     : class points at the cap only")

    # --- ResolveClass ---------------------------------------------------
    held = Stub(inventory={"King's Echo": 0, "ArchPaladin": 1})
    assert joe._resolve_class(held, "ArchPaladin", joe.SOLO_CLASSES) \
        == "ArchPaladin"
    # not held -> the first pool entry the account does have, in pool order
    assert joe._resolve_class(held, "Cryomancer", joe.SOLO_CLASSES) \
        == "ArchPaladin"
    # empty, "Generic" and out-of-pool names are all equally invalid
    for current in (None, "", "Generic", "Some Random Class"):
        assert joe._resolve_class(held, current, joe.SOLO_CLASSES) \
            == "ArchPaladin"
    nothing = Stub()
    assert joe._resolve_class(nothing, "Cryomancer", joe.SOLO_CLASSES) \
        == "Cryomancer"
    print("resolve    : held + in-pool wins, else the first held pool entry")

    # --- set_class ------------------------------------------------------
    stub = Stub(solo="Cryomancer", farm="ArchMage",
                inventory={"King's Echo": 1, "Legion Revenant": 1},
                classes_held=["King's Echo", "Legion Revenant"])
    asyncio.run(joe.set_class(stub))
    assert stub.bot.soloClass == "King's Echo", stub.bot.soloClass
    assert stub.bot.farmClass == "Legion Revenant", stub.bot.farmClass
    assert ("equip_item", "King's Echo") in stub.calls, stub.calls
    assert any("SoloClass resolved -> King's Echo" == line
               for line in stub.bot.logs), stub.bot.logs
    assert ranked_classes == ["King's Echo", "Legion Revenant"], ranked_classes
    print("setclass   : resolves both pools, ranks them, equips the solo one")

    # nothing changed -> nothing redone (the reference's ShouldSkipSetClass)
    before = len(stub.calls)
    asyncio.run(joe.set_class(stub))
    assert len(stub.calls) == before, stub.calls[before:]
    print("setclass   : same level and classes -> no second pass")

    # --- BankAllUnusedClasses -------------------------------------------
    banking = Stub(solo="King's Echo", farm="Legion Revenant",
                   classes_held=["King's Echo", "Legion Revenant", "Ninja"])
    asyncio.run(joe.bank_all_unused_classes(banking))
    assert ("inv_to_bank", ("Ninja",)) in banking.calls, banking.calls
    assert "Banking unused classes: Ninja" in banking.bot.logs, banking.bot.logs
    empty = Stub(solo="King's Echo", classes_held=["King's Echo"])
    asyncio.run(joe.bank_all_unused_classes(empty))
    assert ("inv_to_bank", ()) not in empty.calls, empty.calls
    assert "No unused classes to bank" in empty.bot.logs, empty.bot.logs
    print("banking    : banks the unused classes, and says so when there are none")

    # --- ServersAreDown -------------------------------------------------
    have = Stub(inventory={"The Server is Down": 1})
    asyncio.run(joe.servers_are_down(have))
    assert have.calls == [], have.calls
    print("serverdown : already held -> no calls")

    helm = Stub(solo="King's Echo", classes_held=["King's Echo"])
    asyncio.run(joe.servers_are_down(helm))
    assert ("join_map", "undergroundlabb") in helm.calls, helm.calls
    assert ("equip_item", "The Server is Down") in helm.calls, helm.calls
    print("serverdown : hunts the hamster in /undergroundlabb, then wears it")

    # --- Pets: the source ignores its parameter (Â§16, a (iii) defect) ----
    none = Stub()
    asyncio.run(joe.pets(none, joe.PET_HOT_MAMA))
    assert none.calls == [], none.calls
    print("pets       : the parameter is ignored, as the source ignores it")

    real_choice = joe.PET_CHOICE
    try:
        joe.PET_CHOICE = joe.PET_HOT_MAMA
        mama = Stub(solo="King's Echo", classes_held=["King's Echo"])
        asyncio.run(joe.pets(mama, joe.PET_HOT_MAMA))
        assert ("join_map", "battleundere") in mama.calls, mama.calls
        assert ("equip_item", joe.HOT_MAMA) in mama.calls, mama.calls

        joe.PET_CHOICE = joe.PET_AKRILOTH
        akriloth = Stub(solo="King's Echo", classes_held=["King's Echo"])
        asyncio.run(joe.pets(akriloth, joe.PET_AKRILOTH))
        assert ("join_map", "gravestrike") in akriloth.calls, akriloth.calls
        assert ("equip_item", joe.AKRILOTH_PET) in akriloth.calls, akriloth.calls
    finally:
        joe.PET_CHOICE = real_choice
    print("pets       : with the option set, that pet is fetched and worn")

    # --- the level ladder -----------------------------------------------
    # the two things that would touch the network are replaced, so what is left
    # to check is the ladder itself: order, the daily, and the handlers
    ladder = Stub(level=30, solo="King's Echo",
                  classes_held=["King's Echo", "Ninja"])
    levels, dailies, vhl, porters = [], [], [], []
    real_exp, real_daily = joe.farm_experience, joe.elders_blood
    real_vhl = joe.get_vhl
    real_porters = {name: getattr(joe, name) for name in
                    ("forge_helm_enhancement", "lacerate", "smite", "afdl",
                     "smart_enhance", "vim", "pneuma", "examen", "anima",
                     "get_ds_general", "get_burning_blade", "blade_of_awe_rep",
                     "get_ssorc", "get_blaze_binder", "get_dragonslayer",
                     "get_cryomancer", "get_gb", "get_dss", "get_ap")}

    async def fake_exp(cmd, level=100, rank_up_class=False):
        levels.append(level)

    async def fake_daily(cmd):
        dailies.append("elders")

    async def fake_vhl(cmd, rank_up_class=True):
        vhl.append("get_vhl")

    async def fake_porter(cmd, *args, **kwargs):
        porters.append("ran")

    joe.farm_experience, joe.elders_blood = fake_exp, fake_daily
    joe.get_vhl = fake_vhl
    for name in real_porters:
        setattr(joe, name, fake_porter)
    try:
        asyncio.run(joe.level_30_to_75(ladder))
    finally:
        joe.farm_experience, joe.elders_blood = real_exp, real_daily
        joe.get_vhl = real_vhl
        for name, fn in real_porters.items():
            setattr(joe, name, fn)

    assert levels == list(joe.LEVEL_BRACKETS), levels
    assert dailies == ["elders"], dailies
    assert vhl == ["get_vhl"], vhl          # bracket 80 is the ported CoreVHL
    # the ported enhancement/gear helpers each ran for the bracket that asks
    assert len(porters) >= 3, porters
    assert [c[1] for c in ladder.calls if c[0] == "inv_to_bank"], ladder.calls
    for level in joe.LEVEL_BRACKETS:
        assert f"Level Handler: {level} bracket" in ladder.bot.logs, ladder.bot.logs
    # the reference's own bracket line, word for word
    assert any(line.startswith("Joe will handle each level bracket (0-30")
               for line in ladder.bot.logs), ladder.bot.logs
    # and the bracket 80 log line, including the reference's own slip in it
    assert any(line.startswith("Bracket level [80]; Attemping to aquire VHL")
               for line in ladder.bot.logs), ladder.bot.logs
    print("ladder     : brackets 30..80, the daily first, VHL at 80")

    # --- BeginnerItems: the guard, and a fresh account -------------------
    def fresh_run():
        """Module state as a new run finds it: the class cache is empty."""
        joe._reported.clear()
        joe._class_cache.clear()
        joe._last_checked_level, joe._last_solo, joe._last_farm = 0, None, None

    fresh_run()
    veteran = Stub(classes_held=["Void Highlord", "ArchMage"])
    asyncio.run(joe.beginner_items(veteran))
    assert veteran.calls == [], veteran.calls
    assert "Acc is lvl 30+, skipping beginner items." in veteran.bot.logs
    print("beginner   : a class in both pools -> skipped, as it says")

    # both beginner classes at rank 10 counts too, but only from level 30
    points = {name: joe.RANK_10_CLASS_POINTS for name in ("Ninja", "Mage")}
    fresh_run()
    ranked = Stub(level=30, inventory={"Ninja": 1, "Mage": 1},
                  classes_held=points)
    asyncio.run(joe.beginner_items(ranked))
    assert ranked.calls == [], ranked.calls
    fresh_run()
    low = Stub(level=1, inventory={"Ninja": 1, "Mage": 1}, classes_held=points)
    seen = []
    real_exp = joe.farm_experience

    async def spy_exp(cmd, level=100, rank_up_class=False):
        seen.append(level)

    joe.farm_experience = spy_exp
    real_badges_low = joe.tutorial_badges
    real_mazumi_low = joe.mazumi_quests

    async def noop(cmd):
        return None

    joe.tutorial_badges = noop
    joe.mazumi_quests = noop
    try:
        asyncio.run(joe.beginner_items(low))
    finally:
        joe.farm_experience = real_exp
        joe.tutorial_badges = real_badges_low
        joe.mazumi_quests = real_mazumi_low
    assert seen == [10], seen
    print("beginner   : beginner classes at rank 10 skip it from level 30 only")

    fresh = Stub(
        level=1, inventory={"Default Sword": 1},
        items=[_Item("Default Sword", slot="Weapon")],
        shops=[_Shop(299, ["Battle Oracle Hood", "Battle Oracle Wings",
                           "Battle Oracle Battlestaff"]),
               _Shop(172, ["Rogue"]),
               _Shop(178, ["Ninja"]),
               _Shop(174, [_ShopItem("Mage", 15653, 9845)])])
    fresh_run()
    levels = []

    async def spy_exp2(cmd, level=100, rank_up_class=False):
        levels.append(level)

    joe.farm_experience = spy_exp2
    ranked_up = []
    real_rank = joe.rank_up_class

    async def spy_rank(cmd, *args, **kwargs):
        ranked_up.append(args)

    joe.rank_up_class = spy_rank
    badges, mazumi = [], []
    real_badges, real_mazumi = joe.tutorial_badges, joe.mazumi_quests

    async def spy_badges(cmd):
        badges.append(1)

    async def spy_mazumi(cmd):
        mazumi.append(1)

    joe.tutorial_badges = spy_badges
    joe.mazumi_quests = spy_mazumi
    try:
        asyncio.run(joe.beginner_items(fresh))
    finally:
        joe.farm_experience = real_exp
        joe.rank_up_class = real_rank
        joe.tutorial_badges = real_badges
        joe.mazumi_quests = real_mazumi

    assert levels == [10, 25], levels
    assert ranked_up == [("Rogue",)], ranked_up
    assert badges == [1], badges
    assert mazumi == [1], mazumi
    assert ("buy_item", 299, "battle oracle hood", 1, 0) in fresh.calls, \
        fresh.calls
    assert ("buy_item", 299, "battle oracle wings", 1, 0) in fresh.calls, \
        fresh.calls
    assert ("buy_item", 299, "battle oracle battlestaff", 1, 0) in fresh.calls, \
        fresh.calls
    assert ("equip_item", "Battle Oracle Battlestaff") in fresh.calls, \
        fresh.calls
    assert ("sell_item", "Default Sword") in fresh.calls, fresh.calls
    assert ("buy_item", 172, "rogue", 1, 0) in fresh.calls, fresh.calls
    # Mazumi's chain unlocks the Ninja shop, so the class is bought after it
    assert ("buy_item", 178, "ninja", 1, 0) in fresh.calls, \
        [c for c in fresh.calls if c[0] == "buy_item"]
    assert ("buy_item", 174, "mage", 1, 9845) in fresh.calls, fresh.calls
    for line in ('As the Acc is still "new", we\'re going todo the tutorial badges',
                 "Starting out acc:\n\tGoals: Ninja class & Mage Class",
                 "Getting rogue.. so we can get ninja (there's a 10k hp "
                 "\"boss\" to kill during the \"Hit Job\" quest.)",
                 "Getting starter Dodge class (Ninja)",
                 "Getting Starter Farm class (Mage)"):
        assert line in fresh.bot.logs, fresh.bot.logs
    print("beginner   : fresh account -> Oracle slots, Rogue, Rogue ranked, Mage")

    # --- ShirtAndHat: the merge for the armor, the hat from Yulgar -------
    shirt = Stub(shops=[_Shop(16, ["Scarecrow Hat"])])
    merged = []
    real_merge = joe.no_bots_armor

    async def spy_merge(cmd):
        merged.append(1)

    joe.no_bots_armor = spy_merge
    try:
        asyncio.run(joe.shirt_and_hat(shirt))
    finally:
        joe.no_bots_armor = real_merge
    assert merged == [1], merged
    assert ("buy_item", 16, "scarecrow hat", 1, 0) in shirt.calls, shirt.calls
    assert "Farming NO BOTS Armor (0/1)" in shirt.bot.logs, shirt.bot.logs
    print("shirt      : NO BOTS Armor from the merge, the hat from Yulgar")

    # --- bracket handlers: what runs, what is reported -------------------
    h70 = Stub(solo="King's Echo", classes_held=["King's Echo"],
               shops=[_Shop(308, ["Horc Evader"])])
    forged = []
    real_porters = {name: getattr(joe, name) for name in
                    ("smite", "vim", "pneuma", "examen", "anima", "get_ap")}

    async def spy_porter(cmd, *args, **kwargs):
        forged.append("ran")

    for name in real_porters:
        setattr(joe, name, spy_porter)
    try:
        asyncio.run(joe._handle_level_70(h70))
    finally:
        for name, fn in real_porters.items():
            setattr(joe, name, fn)
    assert ("buy_item", 308, "horc evader", 1, 0) in h70.calls, h70.calls
    assert forged == ["ran"] * 6, forged
    assert "unlocking the easy lvl 70 forge enhs" in h70.bot.logs, h70.bot.logs
    assert any(line.startswith("Geting Horc Evader")
               for line in h70.bot.logs), h70.bot.logs
    assert any(line.startswith("Level 70: Acquiring ArchPaladin")
               for line in h70.bot.logs), h70.bot.logs
    print("bracket70  : Horc Evader, Smite + four helm quests, then ArchPaladin")

    # --- bracket 50: the two ported pieces, Scarlet still reported --------
    h50 = Stub(solo="King's Echo", classes_held=["King's Echo"])
    level50 = []
    real50 = {name: getattr(joe, name) for name in
              ("get_ssorc", "get_ds_general", "get_burning_blade")}

    async def spy50(cmd, *args, **kwargs):
        level50.append("ran")

    for name in real50:
        setattr(joe, name, spy50)
    try:
        asyncio.run(joe._handle_level_50(h50))
    finally:
        for name, fn in real50.items():
            setattr(joe, name, fn)
    assert level50 == ["ran", "ran", "ran"], level50
    assert any(line.startswith("Level 50: Acquiring Dragonslayer General")
               for line in h50.bot.logs), h50.bot.logs
    assert any(line.startswith("Level 50: Acquiring Burning Blade")
               for line in h50.bot.logs), h50.bot.logs
    print("bracket50  : Scarlet, Dragonslayer General and Burning Blade all run")

    # --- bracket 55: Blaze Binder and Cryomancer both run ------------------
    h55 = Stub(solo="King's Echo", classes_held=["King's Echo"])
    level55 = []
    real55 = {name: getattr(joe, name) for name in
              ("get_blaze_binder", "get_cryomancer")}

    async def spy55(cmd, *args, **kwargs):
        level55.append("ran")

    for name in real55:
        setattr(joe, name, spy55)
    try:
        asyncio.run(joe._handle_level_55(h55))
    finally:
        for name, fn in real55.items():
            setattr(joe, name, fn)
    assert level55 == ["ran", "ran"], level55
    assert any(line.startswith("Level 55: Acquiring Blaze Binder")
               for line in h55.bot.logs), h55.bot.logs
    assert any(line.startswith("Level 55: Acquiring Cryomancer")
               for line in h55.bot.logs), h55.bot.logs
    print("bracket55  : Blaze Binder and Cryomancer both run")

    # --- bracket 60: DragonSoul Shinobi, then Lacerate ------------------
    h60 = Stub(solo="King's Echo", classes_held=["King's Echo"])
    level60 = []
    real60 = {name: getattr(joe, name) for name in ("get_dss", "lacerate")}

    async def spy60(cmd, *args, **kwargs):
        level60.append("ran")

    for name in real60:
        setattr(joe, name, spy60)
    try:
        asyncio.run(joe._handle_level_60(h60))
    finally:
        for name, fn in real60.items():
            setattr(joe, name, fn)
    assert level60 == ["ran", "ran"], level60
    assert any(line.startswith("Level 60: Acquiring DragonSoul Shinobi")
               for line in h60.bot.logs), h60.bot.logs
    print("bracket60  : DragonSoul Shinobi, then the Lacerate unlock")

    # --- bracket 65: Glacial Berserker ----------------------------------
    h65 = Stub(solo="King's Echo", classes_held=["King's Echo"])
    level65 = []
    real65 = joe.get_gb

    async def spy65(cmd, *args, **kwargs):
        level65.append("ran")

    joe.get_gb = spy65
    try:
        asyncio.run(joe._handle_level_65(h65))
    finally:
        joe.get_gb = real65
    assert level65 == ["ran"], level65
    assert any(line.startswith("Level 65: Acquiring Glacial Berserker")
               for line in h65.bot.logs), h65.bot.logs
    print("bracket65  : Glacial Berserker runs")

    h30 = Stub(solo="King's Echo", classes_held=["King's Echo"],
               inventory={"Venom Head": 1},
               shops=[_Shop(631, ["Awethur's Accoutrements"])])
    forges = []
    real_forge_helm = joe.forge_helm_enhancement
    real_boa = joe.blade_of_awe_rep
    real_ds = joe.get_dragonslayer

    async def spy_forge_helm(cmd):
        forges.append("helm")

    async def spy_boa(cmd, *args, **kwargs):
        forges.append("boa")

    async def spy_ds(cmd, *args, **kwargs):
        forges.append("ds")

    joe.forge_helm_enhancement = spy_forge_helm
    joe.blade_of_awe_rep = spy_boa
    joe.get_dragonslayer = spy_ds
    try:
        asyncio.run(joe._handle_level_30(h30))
    finally:
        joe.forge_helm_enhancement = real_forge_helm
        joe.blade_of_awe_rep = real_boa
        joe.get_dragonslayer = real_ds
    assert ("sell_item", "Venom Head") in h30.calls, h30.calls
    assert ("buy_item", 631, "awethur's accoutrements", 1, 0) in h30.calls, \
        h30.calls
    assert forges == ["ds", "boa", "helm"], forges
    assert any(line.startswith("Level 30: Farming Blade of Awe Rep")
               for line in h30.bot.logs), h30.bot.logs
    print("bracket30  : Dragonslayer, Blade of Awe rep, Awethur's, helm unlock")

    h80 = Stub(solo="King's Echo", classes_held=["King's Echo"],
               inventory={"Void Highlord": 1})
    asyncio.run(joe._handle_level_80(h80))
    assert any(line.startswith("Dragon of Time found but not rank 10")
               for line in h80.bot.logs), h80.bot.logs
    assert not any(c[0] == "ensure_accept_quest" for c in h80.calls), h80.calls
    print("bracket80  : VHL held -> the class line only, nothing farmed")

    # --- MasterRanger: the first kit bracket 30 needs --------------------
    from bot.other.classes.rep_based import master_ranger

    have_mr = Stub(inventory={"Master Ranger": 1})
    asyncio.run(master_ranger.get_mr(have_mr, rank_up_class=False))
    assert have_mr.calls == [], have_mr.calls
    print("masterrng  : held and no rank-up asked for -> no calls")

    missing_mr = Stub(shops=[_Shop(242, [_ShopItem("Master Ranger", 7260, 5682)])])
    asyncio.run(master_ranger.get_mr(missing_mr, rank_up_class=False))
    assert ("buy_item", 242, "master ranger", 1, 5682) in missing_mr.calls, \
        missing_mr.calls
    assert ("join_map", "sandsea") in missing_mr.calls, missing_mr.calls
    print("masterrng  : bought from sandsea 242 by item id and shop entry")

    ranked_mr = Stub(inventory={"Master Ranger": 1})
    ranked_calls = []
    real_advance = master_ranger.advance_class

    async def spy_advance(cmd, name, *args, **kwargs):
        ranked_calls.append(name)

    master_ranger.advance_class = spy_advance
    try:
        asyncio.run(master_ranger.get_mr(ranked_mr))
    finally:
        master_ranger.advance_class = real_advance
    assert ranked_calls == ["Master Ranger"], ranked_calls
    print("masterrng  : the rank-up runs through the ported RankUpClass")

    h30b = Stub(solo="King's Echo", classes_held=["King's Echo"],
                shops=[_Shop(242, [_ShopItem("Master Ranger", 7260, 5682)]),
                       _Shop(631, ["Awethur's Accoutrements"])])
    joe.forge_helm_enhancement = spy_forge_helm
    joe.blade_of_awe_rep = spy_boa
    joe.get_dragonslayer = spy_ds
    try:
        asyncio.run(joe._handle_level_30(h30b))
    finally:
        joe.forge_helm_enhancement = real_forge_helm
        joe.blade_of_awe_rep = real_boa
        joe.get_dragonslayer = real_ds
    assert ("buy_item", 242, "master ranger", 1, 5682) in h30b.calls, h30b.calls
    print("bracket30  : Master Ranger comes from the ported kit now")

    # --- the later step: the phases it reaches, then the frontier --------
    later = Stub()
    coa = []
    real_coa = joe.get_coa

    async def spy_coa(cmd):
        coa.append(1)

    joe.get_coa = spy_coa
    loc = []
    real_loc = joe.complete13loc

    async def spy_loc(cmd):
        loc.append(1)

    joe.complete13loc = spy_loc
    try:
        asyncio.run(joe.level_75_to_100(later))
    finally:
        joe.get_coa = real_coa
        joe.complete13loc = real_loc
    asyncio.run(joe.end_game(later))
    joined = "\n".join(later.bot.logs)
    assert "Phase 1: Class Preparation - Healer/Dragon of Time" in joined, \
        later.bot.logs
    assert "Phase 2: Chaos Shenanigans - CoA & 13 LoC" in joined, later.bot.logs
    assert coa == [1], coa
    assert loc == [1], loc
    assert ("equip_item", "Cape of Awe") in later.calls, later.calls
    assert "stops after Core13LoC.Complete13LOC" in joined, later.bot.logs
    assert "EndGame is not ported yet" in joined, later.bot.logs
    print("later      : level 75-100 runs CoA then names its frontier")

    # --- DoAll: the reference's order -----------------------------------
    calls = []
    real = {name: getattr(joe, name) for name in
            ("level_1_to_30", "level_30_to_75", "level_75_to_100", "end_game",
             "outfit", "pets")}

    async def recorder(name):
        async def inner(cmd, *args, **kwargs):
            calls.append((name,) + tuple(args))
        return inner

    async def run_do_all():
        joe._reported.clear()
        real_gear = joe.gear_store
        for name in real:
            setattr(joe, name, await recorder(name))

        async def spy_gear(cmd, restore=False, enh_after=False):
            calls.append(("gear_store", restore, enh_after))

        joe.gear_store = spy_gear
        try:
            await joe.do_all(Stub())
        finally:
            for name, fn in real.items():
                setattr(joe, name, fn)
            joe.gear_store = real_gear

    asyncio.run(run_do_all())
    assert [c[0] for c in calls] == [
        "gear_store", "level_1_to_30", "level_30_to_75", "level_75_to_100",
        "end_game", "outfit", "pets", "pets", "gear_store"], calls
    assert calls[0] == ("gear_store", False, False), calls[0]
    assert calls[-1] == ("gear_store", True, True), calls[-1]
    assert calls[-3] == ("pets", joe.PET_HOT_MAMA), calls[-3]
    assert calls[-2] == ("pets", joe.PET_AKRILOTH), calls[-2]
    print("doall      : snapshot, brackets, outfit, pets, then restore")

    joe.rank_up_class = real_rank_up
    print("\nfarmer joe tests OK")


if __name__ == "__main__":
    main()
