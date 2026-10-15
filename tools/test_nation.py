"""Nation routines: guards and decisions, without a live connection.

    python tools/test_nation.py

The farm loops themselves need the game, but every *decision* they make before
the first packet -- "already full?", "is the story done?", "should I aggro?" --
is plain Python and is what this file pins down.  A stub Command records what
would have been sent, so an early return that still sent something fails here
rather than mid-run.
"""
import asyncio
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bot.nation.core_nation import (  # noqa: E402
    approval_and_favor, blood_from_the_void, can_we_aggro, equip_class,
    fiend_emblem, has_any_item, has_any_item_id, has_item_id,
    new_worlds_new_opportunities, uni, void_knight_sword_quest)


class _Other:
    def __init__(self, name):
        self.str_username = name


class _Player:
    def __init__(self, member=False, items_by_id=None):
        self.USER = "me"
        self.CELL = "r9"
        self.is_member = member
        self._by_id = {str(k): v for k, v in (items_by_id or {}).items()}

    def get_item_inventory_by_id(self, item_id):
        return self._by_id.get(str(item_id))


class _Bot:
    def __init__(self, others=()):
        self.player_in_area = [_Other(n) for n in others]


class Stub:
    """Duck-typed Command: records calls, never touches the network."""

    def __init__(self, inventory=None, member=False, completed=(),
                 others=(), connected=True, items_by_id=None):
        self.inv = dict(inventory or {})
        self.calls = []
        self.player = _Player(member, items_by_id)
        self.bot = _Bot(others)
        self._completed = set(completed)
        self._connected = connected
        self.fill_inventory_on_skill = False

    # --- sync predicates ------------------------------------------------
    def is_in_inventory(self, name, qty=1, operator=">=", isTemp=False):
        return self.inv.get(name, 0) >= qty

    def is_still_connected(self):
        return self._connected

    def is_not_in_map(self, map_name):
        return False

    def is_not_in_cell(self, cell):
        return False

    def get_farm_class(self):
        return "Farm Class"

    def get_solo_class(self):
        return "Solo Class"

    def get_player(self):
        return self.player

    def get_player_cell(self):
        return self.player.CELL

    def add_drop(self, names):
        self.calls.append(("add_drop", names))

    def farming_logger(self, *args):
        self.calls.append(("farming_logger", args))

    def stop_aggro(self):
        self.calls.append(("stop_aggro",))

    def start_aggro_by_cell(self, cells):
        self.calls.append(("start_aggro_by_cell", tuple(cells)))

    def cancel_registered_quests(self):
        self.calls.append(("cancel_registered_quests",))

    # --- async ----------------------------------------------------------
    async def equip_item(self, name):
        self.calls.append(("equip_item", name))
        return True

    async def join_map(self, map_name, room=None, safe_leave=True):
        self.calls.append(("join_map", map_name))

    async def jump_cell(self, cell, pad):
        self.calls.append(("jump_cell", cell, pad))

    async def use_next_skill(self, *args, **kwargs):
        self.calls.append(("use_next_skill",))
        if self.fill_inventory_on_skill:
            self.inv["Nulgath's Approval"] = 10 ** 9
            self.inv["Archfiend's Favor"] = 10 ** 9
        self._connected = False          # end the loop deterministically
        return True

    async def is_completed_before(self, quest_id):
        self.calls.append(("is_completed_before", quest_id))
        return quest_id in self._completed

    async def register_quest(self, quest_id):
        self.calls.append(("register_quest", quest_id))

    async def ensure_accept_quest(self, quest_id):
        self.calls.append(("ensure_accept_quest", quest_id))

    async def ensure_turn_in_quest(self, quest_id, item_id=-1, amount=1):
        self.calls.append(("ensure_turn_in_quest", quest_id))

    def add_quest_rewards(self, quest_id):
        self.calls.append(("add_quest_rewards", quest_id))
        return []

    def get_loaded_quest(self, quest_id):
        self.calls.append(("get_loaded_quest", quest_id))
        return None

    def kinds(self):
        return [c[0] for c in self.calls]


def main() -> None:
    # --- uni ----------------------------------------------------------
    assert uni(10) == "Unidentified 10"
    assert uni(13) == "Unidentified 13"
    print("uni        :", uni(13))

    # --- can_we_aggro -------------------------------------------------
    alone = Stub()
    assert can_we_aggro(alone) is False
    assert alone.kinds() == ["stop_aggro"], alone.kinds()

    shared = Stub(others=("someone-else",))
    assert can_we_aggro(shared) is True
    assert shared.kinds() == ["start_aggro_by_cell"], shared.kinds()
    assert shared.calls[0][1] == ("r9",), shared.calls[0]
    print("aggro      : alone -> stop, shared -> aggro r9")

    # a stub whose own name is in the cell must not count itself as "someone"
    self_only = Stub(others=("me",))
    assert can_we_aggro(self_only) is False, "self counted as another player"
    print("aggro      : self in the cell does not count as 'shared'")

    # --- equip_class --------------------------------------------------
    assert asyncio.run(equip_class(Stub())) is True
    assert asyncio.run(equip_class(Stub(), solo=True)) is True
    none_cfg = Stub()
    none_cfg.get_farm_class = lambda: None
    assert asyncio.run(equip_class(none_cfg)) is False
    assert none_cfg.calls == []
    print("equip      : configured -> equipped, unset -> no-op")

    # --- approval_and_favor -------------------------------------------
    full = Stub({"Nulgath's Approval": 5000, "Archfiend's Favor": 5000})
    asyncio.run(approval_and_favor(full))
    assert full.calls == [], full.calls
    print("approval   : both full -> returns without a single call")

    half = Stub({"Nulgath's Approval": 5000, "Archfiend's Favor": 0})
    asyncio.run(approval_and_favor(half))
    assert half.kinds()[0] == "add_drop", half.kinds()
    assert "equip_item" in half.kinds(), half.kinds()
    assert "join_map" not in half.kinds(), "already in map, must not rejoin"
    assert "use_next_skill" in half.kinds(), half.kinds()
    assert "farming_logger" in half.kinds()
    print("approval   : partial -> drops+class+skill, no rejoin")

    # --- blood_from_the_void ------------------------------------------
    have = Stub({"Blood From the Void": 300})
    asyncio.run(blood_from_the_void(have))
    assert have.calls == [], have.calls
    print("bfv        : already full -> returns before any lookup")

    no_story = Stub({"Blood From the Void": 0})
    asyncio.run(blood_from_the_void(no_story))
    assert "is_completed_before" in no_story.kinds()
    assert "register_quest" not in no_story.kinds(), "must not farm the story"
    assert "add_drop" not in no_story.kinds()
    print("bfv        : story missing -> stops before registering the quest")

    # --- fiend_emblem -------------------------------------------------
    emblem = Stub({"Fiend Emblem": 300})
    asyncio.run(fiend_emblem(emblem))
    assert emblem.calls == [], emblem.calls
    print("emblem     : already full -> returns without a single call")

    # --- has_any_item / id helpers ------------------------------------
    assert has_any_item(Stub({"a": 1}), ("b", "a")) is True
    assert has_any_item(Stub(), ("b", "a")) is False
    assert has_item_id(Stub(items_by_id={38275: object()}), 38275) is True
    assert has_item_id(Stub(items_by_id={38254: object()}), 38275) is False
    assert has_any_item_id(Stub(items_by_id={38254: object()}), (38275, 38254)) is True
    assert has_any_item_id(Stub(), (38275, 38254)) is False
    print("item ids   : id and any-id checks read the inventory")

    # --- new_worlds_new_opportunities ---------------------------------
    no_pet = Stub()
    asyncio.run(new_worlds_new_opportunities(no_pet))
    assert no_pet.calls == [], no_pet.calls
    print("nwno       : no pet -> returns without a single call")

    done = Stub({"Unidentified 10": 1000}, items_by_id={})
    asyncio.run(new_worlds_new_opportunities(done, "Unidentified 10", 1000))
    assert done.calls == [], done.calls
    print("nwno       : item already full -> returns without a single call")

    # --- void_knight_sword_quest --------------------------------------
    no_sword = Stub()
    asyncio.run(void_knight_sword_quest(no_sword))
    assert no_sword.calls == [], no_sword.calls
    print("vkwsq      : no sword owned -> returns without a single call")

    have = Stub({"Unidentified 10": 1000}, items_by_id={38275: object()})
    asyncio.run(void_knight_sword_quest(have, "Unidentified 10", 1000))
    assert have.calls == [], have.calls
    print("vkwsq      : item already full -> returns without a single call")

    print("\nnation tests OK")


if __name__ == "__main__":
    main()
