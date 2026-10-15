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
    """A class in the inventory: slot, name and quantity are what get read."""

    def __init__(self, name, qty=1):
        self.s_name = name
        self.item_name = name.lower()
        self.s_es = ItemType.CLASS.value
        self.qty = qty


class _Player:
    def __init__(self, level=30):
        self.USER = "me"
        self.LEVEL = level
        self.INVENTORY = []

    def get_item_inventory(self, name):
        for item in self.INVENTORY:
            if item.item_name == name.lower():
                return item
        return None


class _Bot:
    def __init__(self):
        self.farmClass = None
        self.soloClass = None
        self.player = _Player()
        self.logs = []
        self.sent = []

    def write_message(self, msg):
        self.sent.append(msg)

    def log(self, *args):
        self.logs.append(" ".join(map(str, args)))

    def debug(self, *args):
        self.logs.append(" ".join(map(str, args)))


class Stub:
    """Duck-typed Command: records calls, never touches the network."""

    def __init__(self, inventory=None, level=30, solo=None, farm=None,
                 classes_held=()):
        self.bot = _Bot()
        self.bot.player.LEVEL = level
        self.bot.farmClass = farm
        self.bot.soloClass = solo
        self.inv = dict(inventory or {})
        held = (dict(classes_held) if isinstance(classes_held, dict)
                else {name: 1 for name in classes_held})
        self.bot.player.INVENTORY = [_Item(name, qty)
                                     for name, qty in held.items()]
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
        return self.inv.get(name, 0) >= qty

    def is_in_bank(self, name, qty=1, operator=">="):
        return False

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

    async def inv_to_bank(self, names):
        self.calls.append(("inv_to_bank", tuple(names)))

    async def has_item(self, name, qty=1, operator=">=", isTemp=False):
        return self.inv.get(name, 0) >= qty

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
    print("setclass   : resolves both pools and equips the solo one")

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

    # --- Pets -----------------------------------------------------------
    none = Stub()
    asyncio.run(joe.pets(none))
    assert none.calls == [], none.calls
    print("pets       : no choice -> nothing fetched")

    mama = Stub(solo="King's Echo", classes_held=["King's Echo"])
    asyncio.run(joe.pets(mama, joe.PET_HOT_MAMA))
    assert ("join_map", "battleundere") in mama.calls, mama.calls
    assert ("equip_item", joe.HOT_MAMA) in mama.calls, mama.calls
    akriloth = Stub(solo="King's Echo", classes_held=["King's Echo"])
    asyncio.run(joe.pets(akriloth, joe.PET_AKRILOTH))
    assert ("join_map", "gravestrike") in akriloth.calls, akriloth.calls
    assert ("equip_item", joe.AKRILOTH_PET) in akriloth.calls, akriloth.calls
    print("pets       : the parameter is honoured, both pets in their own map")

    # --- the level ladder -----------------------------------------------
    # the two things that would touch the network are replaced, so what is left
    # to check is the ladder itself: order, the daily, and the handlers
    ladder = Stub(level=30, solo="King's Echo",
                  classes_held=["King's Echo", "Ninja"])
    levels, dailies = [], []
    real_exp, real_daily = joe.farm_experience, joe.elders_blood

    async def fake_exp(cmd, level=100, rank_up_class=False):
        levels.append(level)

    async def fake_daily(cmd):
        dailies.append("elders")

    joe.farm_experience, joe.elders_blood = fake_exp, fake_daily
    try:
        asyncio.run(joe.level_30_to_75(ladder))
    finally:
        joe.farm_experience, joe.elders_blood = real_exp, real_daily

    assert levels == list(joe.LEVEL_BRACKETS), levels
    assert dailies == ["elders"], dailies
    assert [c[1] for c in ladder.calls if c[0] == "inv_to_bank"], ladder.calls
    for level in joe.LEVEL_BRACKETS:
        assert f"Level Handler: {level} bracket" in ladder.bot.logs, ladder.bot.logs
    # the reference's own bracket line, word for word
    assert any(line.startswith("Joe will handle each level bracket (0-30")
               for line in ladder.bot.logs), ladder.bot.logs
    print("ladder     : brackets 30..80, the daily first, every handler called")

    # --- the two later steps are loud, not silent ------------------------
    later = Stub()
    asyncio.run(joe.level_75_to_100(later))
    asyncio.run(joe.end_game(later))
    joined = "\n".join(later.bot.logs)
    assert "Level75to100 is not ported yet" in joined, later.bot.logs
    assert "EndGame is not ported yet" in joined, later.bot.logs
    print("later      : level 75-100 and endgame name what they still need")

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
        for name in real:
            setattr(joe, name, await recorder(name))
        try:
            await joe.do_all(Stub())
        finally:
            for name, fn in real.items():
                setattr(joe, name, fn)

    asyncio.run(run_do_all())
    assert [c[0] for c in calls] == [
        "level_1_to_30", "level_30_to_75", "level_75_to_100", "end_game",
        "outfit", "pets", "pets"], calls
    assert calls[-2] == ("pets", joe.PET_HOT_MAMA), calls[-2]
    assert calls[-1] == ("pets", joe.PET_AKRILOTH), calls[-1]
    print("doall      : brackets, endgame, outfit, then both pets")

    print("\nfarmer joe tests OK")


if __name__ == "__main__":
    main()
