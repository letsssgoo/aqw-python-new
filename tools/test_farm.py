"""Gold, experience and reputation farms: guards, bands and wiring.

    python tools/test_farm.py

``bot/core_farms.py`` is the port of ``CoreFarms.cs`` and ``bot/core_bots.py``
the handful of ``CoreBots`` helpers it needs.  What matters mechanically is that
each routine refuses to run when the reference refuses, follows the same map /
cell / quest ladder when it does run, and reports rather than acting when the
engine cannot do what the reference does (boosts, class ranks).

Every routine is driven against a stub Command, so nothing touches the network.
"""
import asyncio
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bot.core_bots import (Alignment, can_we_aggro,  # noqa: E402
                          change_alignment, equip_class)
from bot.core_farms import (FACTION_FARMS, ICESTORM_LADDER,  # noqa: E402
                            battle_ground_e, dark_war_legion, farm_experience,
                            farm_faction, farm_gold, farm_until, good_rep,
                            honor_hall, icestorm_arena,
                            undead_giant_unlock, vampire_rep)


class _Player:
    def __init__(self, level=1, gold=0, member=False):
        self.USER = "me"
        self.CELL = "Enter"
        self.PAD = "Spawn"
        self.LEVEL = level
        self.GOLD = gold
        self.is_member = member


class _Bot:
    def __init__(self, others=()):
        self.player_in_area = [type("O", (), {"str_username": n})()
                               for n in others]
        self.areaId = "evilwarnul-9909"
        self.sent = []
        self.loaded_shop_datas = []

    def write_message(self, msg):
        self.sent.append(msg)


class _ShopItem:
    """Mirrors ``ItemInventory``: the model lower-cases ``sName`` on the way in."""

    def __init__(self, name):
        self.item_name = name.lower()


class _Shop:
    def __init__(self, shop_id, items):
        self.shop_id = shop_id
        self.items = [_ShopItem(n) for n in items]


class Stub:
    """Duck-typed Command: records calls, never touches the network."""

    def __init__(self, level=1, gold=0, member=False, others=(),
                 completed=(691,), good_rank=0, vampire_rank=0,
                 connect_after=1, accept=True, inventory=None):
        self.player = _Player(level, gold, member)
        self.bot = _Bot(others)
        self.calls = []
        self.inv = dict(inventory or {})
        self._connected = True
        self._completed = set(completed)
        self._accept = accept
        self._good_rank = good_rank
        self._vampire_rank = vampire_rank
        #: how many skill casts it takes to end the run (0 = never disconnects)
        self._casts_left = connect_after

    # --- sync -----------------------------------------------------------
    def kinds(self):
        return [c[0] for c in self.calls]

    def is_still_connected(self):
        return self._connected

    def is_not_in_map(self, map_name):
        return map_name.lower() != self._map_name()

    def is_not_in_cell(self, cell):
        return cell.lower() != self.player.CELL.lower()

    def get_player(self):
        return self.player

    def get_farm_class(self):
        return "Farm Class"

    def get_solo_class(self):
        return "Solo Class"

    def get_faction_rank(self, name):
        return {"Good": self._good_rank, "Vampire": self._vampire_rank}.get(
            name, 0)

    def get_quant_item(self, name):
        return self.inv.get(name, 0)

    def is_in_bank(self, name, qty=1, operator=">="):
        return False

    def is_in_inventory(self, name, qty=1, operator=">=", isTemp=False):
        return self.inv.get(name, 0) >= qty

    def get_equipped_class(self):
        return None

    def add_drop(self, names):
        self.calls.append(("add_drop", tuple(names) if isinstance(
            names, (list, tuple)) else names))

    def remove_drop(self, names):
        self.calls.append(("remove_drop", names))

    def cancel_registered_quests(self):
        self.calls.append(("cancel_registered_quests",))

    def stop_aggro(self):
        self.calls.append(("stop_aggro",))

    def start_aggro_by_cell(self, cells):
        self.calls.append(("start_aggro_by_cell", tuple(cells)))

    # --- async ----------------------------------------------------------
    async def equip_item(self, name):
        self.calls.append(("equip_item", name))
        return True

    async def join_map(self, map_name, room=None, safe_leave=True):
        self.calls.append(("join_map", map_name))
        self._map = map_name

    async def jump_cell(self, cell, pad):
        self.calls.append(("jump_cell", cell, pad))
        self.player.CELL = cell
        self.player.PAD = pad

    async def jump_to_monster(self, *args, **kwargs):
        self.calls.append(("jump_to_monster",))

    async def sleep(self, ms):
        pass

    async def register_quest(self, quest_id):
        self.calls.append(("register_quest", quest_id))

    async def ensure_accept_quest(self, quest_id, max_attempts=60):
        self.calls.append(("ensure_accept_quest", quest_id))
        return self._accept

    async def ensure_turn_in_quest(self, quest_id, item_id=-1, amount=1):
        self.calls.append(("ensure_turn_in_quest", quest_id))
        return True

    async def is_completed_before(self, quest_id):
        self.calls.append(("is_completed_before", quest_id))
        return quest_id in self._completed

    async def sell_item(self, item_name, qty=1):
        self.calls.append(("sell_item", item_name, qty))
        self.inv[item_name] = max(0, self.inv.get(item_name, 0) - qty)

    async def bank_to_inv(self, names):
        self.calls.append(("bank_to_inv", names))

    async def buy_item(self, shop_id, item_name, qty=1):
        self.calls.append(("buy_item", shop_id, item_name, qty))

    async def wait_use_skill(self, slot, target_monsters="*"):
        self.calls.append(("wait_use_skill", slot))

    async def leave_combat(self, safe_leave=True):
        self.calls.append(("leave_combat",))

    async def rest(self):
        self.calls.append(("rest",))

    async def use_next_skill(self, *args, **kwargs):
        self.calls.append(("use_next_skill",))
        if self._casts_left > 0:
            self._casts_left -= 1
            if self._casts_left == 0:
                self._connected = False

    # --- helpers --------------------------------------------------------
    def _map_name(self):
        return getattr(self, "_map", "battleon")

    def gained(self):
        """Gold/level gains a skill cast would produce -- used by the gold/exp
        happy paths, where the routine must stop because the target is met."""
        return


def _gold_gain(stub, amount):
    """Make one skill cast add ``amount`` gold, so the target is reached."""
    original = stub.use_next_skill

    async def cast(*args, **kwargs):
        await original(*args, **kwargs)
        stub.player.GOLD += amount

    stub.use_next_skill = cast


def _level_gain(stub, amount):
    original = stub.use_next_skill

    async def cast(*args, **kwargs):
        await original(*args, **kwargs)
        stub.player.LEVEL += amount

    stub.use_next_skill = cast


def main() -> None:
    # --- Alignment / change_alignment ---------------------------------
    assert (Alignment.GOOD.value, Alignment.EVIL.value, Alignment.CHAOS.value) \
        == (1, 2, 3)
    stub = Stub()
    asyncio.run(change_alignment(stub, Alignment.GOOD))
    assert stub.bot.sent == ["%xt%zm%updateQuest%evilwarnul-9909%41%1%"], \
        stub.bot.sent
    print("align      : Good -> updateQuest 41 with value 1")

    # --- equip_class ---------------------------------------------------
    stub = Stub()
    assert asyncio.run(equip_class(stub)) is True
    assert asyncio.run(equip_class(stub, solo=True)) is True
    assert [c for c in stub.calls if c[0] == "equip_item"] == \
        [("equip_item", "Farm Class"), ("equip_item", "Solo Class")]

    class NoClass(Stub):
        def get_farm_class(self):
            return None

    assert asyncio.run(equip_class(NoClass())) is False
    print("equip      : farm and solo name their own class; unset -> False")

    # --- can_we_aggro --------------------------------------------------
    alone = Stub()
    assert can_we_aggro(alone) is False
    assert ("stop_aggro",) in alone.calls, alone.calls
    shared = Stub(others=["someone"])
    assert can_we_aggro(shared) is True
    assert ("start_aggro_by_cell", ("Enter",)) in shared.calls, shared.calls
    print("aggro      : alone -> stop, shared -> aggro the cell")

    # --- farm_until: the quest gate ------------------------------------
    refused = Stub(accept=False)
    assert asyncio.run(farm_until(refused, lambda: False, "somewhere",
                                  cell="r1", quests=(8584, 8585))) is False
    assert ("register_quest", 8584) not in refused.calls, refused.calls
    assert "use_next_skill" not in refused.kinds(), refused.calls
    print("farm_until : an unacceptable quest stops before any farming")

    # --- farm_until: a done() that holds does nothing ------------------
    done = Stub()
    assert asyncio.run(farm_until(done, lambda: True, "somewhere")) is True
    assert done.calls == [], done.calls
    print("farm_until : done() already true -> no calls at all")

    # --- gold: already rich, and the fallback chain --------------------
    rich = Stub(gold=200_000_000)
    assert asyncio.run(farm_gold(rich, 100_000_000)) is True
    assert rich.calls == [], rich.calls
    print("gold       : already at the target -> True, no calls")

    poor = Stub(level=1, gold=0)
    assert asyncio.run(farm_gold(poor, 100_000_000)) is False
    assert ("register_quest", 236) in poor.calls, poor.calls   # BerserkerBunny
    assert ("join_map", "greenguardwest") in poor.calls, poor.calls
    assert ("add_drop", ("Berserker Bunny",)) in poor.calls, poor.calls
    print("gold       : low level -> only the BerserkerBunny route runs")

    member = Stub(level=61, gold=0, member=True, connect_after=0)
    _gold_gain(member, 100_000_000)
    assert asyncio.run(farm_gold(member, 100_000_000)) is True
    assert ("register_quest", 3992) in member.calls, member.calls
    assert ("join_map", "honorhall") in member.calls, member.calls
    assert ("jump_cell", "r1", "Center") in member.calls, member.calls
    assert ("join_map", "battlegrounde") not in member.calls, member.calls
    print("gold       : member 61+ -> HonorHall takes it, BGE never runs")

    # --- the individual gold methods -----------------------------------
    without_member = Stub(level=61, gold=0)
    asyncio.run(honor_hall(without_member, 1000))
    assert without_member.calls == [], without_member.calls
    print("honorhall  : non-member -> returns without a single call")

    bge = Stub(level=61, gold=0, connect_after=0)
    _gold_gain(bge, 100_000_000)
    asyncio.run(battle_ground_e(bge, 100_000_000))
    assert ("register_quest", 3991) in bge.calls, bge.calls
    assert ("jump_cell", "r2", "center") in bge.calls, bge.calls
    print("bge        : 61+ -> quests 3991/3992 in /battlegrounde r2")

    dwl = Stub(level=61, gold=0, connect_after=0)
    _gold_gain(dwl, 100_000_000)
    asyncio.run(dark_war_legion(dwl, 100_000_000))
    assert ("register_quest", 8584) in dwl.calls, dwl.calls
    assert ("add_drop", ("Nation Badge",)) in dwl.calls, dwl.calls
    print("darkwar    : quests 8584/8585 with the Nation Badge drop filter")

    # --- experience: the level ladder ----------------------------------
    high = Stub(level=50)
    asyncio.run(farm_experience(high, 15))
    assert high.calls == [], high.calls
    print("exp        : above the target level -> no calls")

    low = Stub(level=5, connect_after=0)
    _level_gain(low, 2)
    asyncio.run(farm_experience(low, 7))
    assert ("join_map", "oaklore") in low.calls, low.calls
    assert ("register_quest", 4007) in low.calls, low.calls
    assert low.player.LEVEL == 7, low.player.LEVEL     # min(10, level), not 10
    assert ("join_map", "icestormarena") not in low.calls, low.calls
    assert ("join_map", "swordhavenundead") not in low.calls, low.calls
    print("exp        : level 5 -> the oaklore block only, stop at 7 not 10")

    # --- undead giant unlock (the prerequisite for quest 178) ----------
    done = Stub(completed=(177,))
    asyncio.run(undead_giant_unlock(done))
    assert done.calls == [("is_completed_before", 177)], done.calls
    print("unlock     : quest 177 done -> only the check, nothing farmed")

    unlock = Stub(level=15)
    asyncio.run(undead_giant_unlock(unlock))
    assert [c for c in unlock.calls if c[0] == "ensure_accept_quest"] == \
        [("ensure_accept_quest", 183), ("ensure_accept_quest", 176),
         ("ensure_accept_quest", 177)], unlock.calls
    assert [c for c in unlock.calls if c[0] == "ensure_turn_in_quest"] == \
        [("ensure_turn_in_quest", 183), ("ensure_turn_in_quest", 176),
         ("ensure_turn_in_quest", 177)], unlock.calls
    assert ("join_map", "portalundead") in unlock.calls, unlock.calls
    print("unlock     : quests 183 -> 176 -> 177, accepted then turned in")

    # 20-25 is the first band the ladder uses quest 6628 in
    ladder = Stub(level=25)
    asyncio.run(icestorm_arena(ladder, 30))
    assert ("join_map", "icestormarena") in ladder.calls, ladder.calls
    assert ("jump_cell", "r10", "Left") in ladder.calls, ladder.calls
    assert ("register_quest", 6628) not in ladder.calls, ladder.calls
    for cell in ("r4", "r5", "r6", "r7"):
        assert ("jump_cell", cell, "Bottom" if cell == "r4" else "Left") \
            not in ladder.calls, ladder.calls
    print("icestorm   : level 25 -> r10, the bands below it are skipped")

    banded = Stub(level=21)
    asyncio.run(icestorm_arena(banded, 26))
    assert ("jump_cell", "r7", "Left") in banded.calls, banded.calls
    assert ("register_quest", 6628) in banded.calls, banded.calls
    print("icestorm   : level 21 -> r7 with quest 6628")

    # every band in the table is reachable and ordered
    assert [b[0] for b in ICESTORM_LADDER] == sorted(b[0] for b in ICESTORM_LADDER)
    assert ICESTORM_LADDER[0][0] == 0 and ICESTORM_LADDER[-1][1] == 61
    print("icestorm   : the ladder starts at 0 and its bands are ordered")

    # --- reputation: Good ----------------------------------------------
    ranked = Stub(good_rank=10)
    asyncio.run(good_rep(ranked, 10))
    assert ranked.calls == [], ranked.calls
    print("good       : already rank 10 -> no calls")

    fallback = Stub(good_rank=1)
    asyncio.run(good_rep(fallback, 10))
    assert fallback.bot.sent and fallback.bot.sent[0].endswith("%41%1%"), \
        fallback.bot.sent
    assert ("join_map", "swordhavenbridge") in fallback.calls, fallback.calls
    assert ("register_quest", 369) in fallback.calls, fallback.calls
    assert ("join_map", "poisonforest") not in fallback.calls, fallback.calls
    print("good       : story unfinished -> quest 369 route first")

    poison = Stub(good_rank=1, completed=(1955,))
    asyncio.run(good_rep(poison, 10))
    assert ("join_map", "poisonforest") in poison.calls, poison.calls
    assert ("register_quest", 1952) in poison.calls, poison.calls
    assert ("join_map", "swordhavenbridge") not in poison.calls, poison.calls
    print("good       : story complete -> quest 1952 in /poisonforest")

    member_path = Stub(good_rank=5, member=True)
    asyncio.run(good_rep(member_path, 10))
    assert ("join_map", "sewer") in member_path.calls, member_path.calls
    assert ("join_map", "castleundead") not in member_path.calls
    print("good       : fallback for members -> /sewer, not /castleundead")

    f2p_path = Stub(good_rank=5)
    asyncio.run(good_rep(f2p_path, 10))
    assert ("join_map", "castleundead") in f2p_path.calls, f2p_path.calls
    print("good       : fallback for the rest -> /castleundead")

    # --- reputation: Vampire -------------------------------------------
    have_it = Stub(vampire_rank=10)
    asyncio.run(vampire_rep(have_it, 10))
    assert have_it.calls == [], have_it.calls
    print("vampire    : already rank 10 -> no calls")

    no_story = Stub(accept=False)
    asyncio.run(vampire_rep(no_story, 10))
    assert ("register_quest", 522) not in no_story.calls, no_story.calls
    assert "use_next_skill" not in no_story.kinds(), no_story.calls
    print("vampire    : quest 522 refused -> reported, nothing farmed")

    story = Stub()
    asyncio.run(vampire_rep(story, 10))
    assert ("join_map", "safiria") in story.calls, story.calls
    assert ("add_drop", ("Twisted Paw's Head",)) in story.calls, story.calls
    assert ("remove_drop", "Old Moon") in story.calls, story.calls
    assert ("equip_item", "Solo Class") in story.calls, story.calls
    print("vampire    : quest 522 route with the solo class and drop filter")

    # --- the dispatcher -------------------------------------------------
    unknown = Stub()
    assert asyncio.run(farm_faction(unknown, "Yokai", 10)) is False
    assert unknown.calls == [], unknown.calls          # reported, never farmed
    assert set(FACTION_FARMS) == {"Good", "Vampire"}, sorted(FACTION_FARMS)
    known = Stub(vampire_rank=10)
    assert asyncio.run(farm_faction(known, "Vampire", 10)) is True
    print("dispatch   : ported factions run, the rest are named and refused")

    # --- buy_item waits for the shop, then buys -------------------------
    # Command.buy_item only *asks* for an unseen shop; buying on that first
    # call would look like a purchase that never happened
    from bot.core_bots import buy_item

    never = Stub()
    assert asyncio.run(buy_item(never, 1212, "Receipt of Nulgath")) is False
    assert never.calls == [("buy_item", 1212, "Receipt of Nulgath", 1)] * 3, \
        never.calls
    print("buy_item   : shop never loads -> reported, asked 3 times")

    lacking = Stub()
    lacking.bot.loaded_shop_datas.append(_Shop(1212, ["Something Else"]))
    assert asyncio.run(buy_item(lacking, 1212, "Receipt of Nulgath")) is False
    assert lacking.calls == [], lacking.calls
    print("buy_item   : shop lacks the item -> reported, nothing bought")

    stocked = Stub()
    stocked.bot.loaded_shop_datas.append(_Shop(68, ["Blade of Affliction"]))
    assert asyncio.run(buy_item(stocked, 68, "Blade of Affliction")) is True
    assert stocked.calls == [("buy_item", 68, "Blade of Affliction", 1)], \
        stocked.calls
    print("buy_item   : shop loaded -> bought once")

    print("\nfarm tests OK")


if __name__ == "__main__":
    main()
