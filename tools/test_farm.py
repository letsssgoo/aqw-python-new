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
import json
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
        self.ISDEAD = False


class _Bot:
    def __init__(self, others=()):
        self.player_in_area = [type("O", (), {"str_username": n})()
                               for n in others]
        self.areaId = "evilwarnul-9909"
        self.sent = []
        self.loaded_shop_datas = []
        self.monsters = []
        self.logs = []

    def write_message(self, msg):
        self.sent.append(msg)

    def log(self, *args):
        """The engine's script log (``Bot.log``): what the port writes to."""
        self.logs.append(" ".join(map(str, args)))

    def debug(self, *args):
        self.logs.append(" ".join(map(str, args)))


class _ShopItem:
    """Mirrors ``ItemInventory``: the model lower-cases ``sName`` on the way in."""

    def __init__(self, name, item_id=0, shop_item_id=None):
        self.item_name = name.lower()
        self.item_id = item_id
        self.shop_item_id = item_id if shop_item_id is None else shop_item_id


class _Shop:
    def __init__(self, shop_id, items):
        self.shop_id = shop_id
        self.items = [i if isinstance(i, _ShopItem) else _ShopItem(i)
                      for i in items]


class _ShopBot:
    """A client whose shop cache is filled by the read loop, not by the call.

    ``answers`` makes it behave like a live server: the next ``loadShop`` request
    is what puts the shop in the cache.
    """

    def __init__(self, answers=False):
        self.player = _Player()
        self.loaded_shop_datas = []
        self.answers = answers
        self.sent = []
        self.areaId = "alchemyacademy-1"
        self.is_client_connected = True
        self.accept_quest = None            # only touched by is_still_connected
        self.is_aggro_handler_task_running = False
        self.aggro_mons_id = []

    def write_message(self, msg):
        self.sent.append(msg)
        if self.answers and "loadShop" in msg:
            shop_id = msg.split("%")[-2]
            self.loaded_shop_datas.append(_Shop(shop_id, ["Gold Voucher 100k"]))

    async def ensure_leave_from_combat(self, always=False):
        return None

    def jump_cell(self, cell, pad):
        return None


class Stub:
    """Duck-typed Command: records calls, never touches the network."""

    def __init__(self, level=1, gold=0, member=False, others=(),
                 completed=(691,), good_rank=0, vampire_rank=0, ranks=None,
                 connect_after=1, accept=True, inventory=None):
        self.player = _Player(level, gold, member)
        self.bot = _Bot(others)
        self.calls = []
        self.inv = dict(inventory or {})
        self._connected = True
        self._completed = set(completed)
        self._accept = accept
        self._good_rank = good_rank
        self._ranks = {"Good": good_rank, "Vampire": vampire_rank,
                       **(ranks or {})}
        self._vampire_rank = vampire_rank
        #: how many skill casts it takes to end the run (0 = never disconnects)
        self._casts_left = connect_after
        #: False makes ensure_load_shop report a shop that never arrives
        self.shop_loads = True
        #: set True to make is_monster_alive report an empty cell
        self._monsters_dead = False
        #: set True to make is_in_cell answer yes whatever the cell
        self.cell_ok = False
        #: item ids ``has_item_id`` should report as held
        self.owned_ids = set()

    # --- sync -----------------------------------------------------------
    def kinds(self):
        return [c[0] for c in self.calls]

    def is_still_connected(self):
        return self._connected

    def is_not_in_map(self, map_name):
        return map_name.lower() != self._map_name()

    def is_in_map(self, map_name):
        return map_name.lower() == self._map_name()

    def is_not_in_cell(self, cell):
        if self.cell_ok:
            return False
        return cell.lower() != self.player.CELL.lower()

    def is_in_cell(self, cell):
        if self.cell_ok:
            return True
        return cell.lower() == self.player.CELL.lower()

    def is_monster_alive(self, monster="*"):
        return not self._monsters_dead

    def is_player_alive(self):
        return not self.player.ISDEAD

    def farming_logger(self, *args):
        self.calls.append(("farming_logger", args))

    def get_player(self):
        return self.player

    def get_farm_class(self):
        return "Farm Class"

    def get_solo_class(self):
        return "Solo Class"

    def get_faction_rank(self, name):
        return self._ranks.get(name, 0)

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

    async def walk_to(self, x, y, speed=8):
        self.calls.append(("walk_to", x, y))

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

    async def buy_item(self, shop_id, item_name, qty=1, shop_item_id=0):
        self.calls.append(("buy_item", shop_id, item_name, qty, shop_item_id))

    async def ensure_load_shop(self, shop_id):
        self.calls.append(("ensure_load_shop", shop_id))
        return self.shop_loads

    async def has_item_id(self, item_id):
        self.calls.append(("has_item_id", item_id))
        return str(item_id) in self.owned_ids

    async def has_item(self, name, qty=1, operator=">=", isTemp=False):
        if not isTemp and self.is_in_bank(name):
            await self.bank_to_inv(name)
        return self.inv.get(name, 0) >= qty

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


def _rank_gain(stub, faction, amount):
    """A skill cast raises a faction rank -- the rewards the quest task would
    hand over, without simulating the task itself."""
    original = stub.use_next_skill

    async def cast(*args, **kwargs):
        await original(*args, **kwargs)
        stub._ranks[faction] = stub._ranks.get(faction, 0) + amount

    stub.use_next_skill = cast


def _drop_gain(stub, item_name, amount):
    """A skill cast adds an item and clears the cell -- the drop a brawl pass
    credits, and the fact that the NPC it came off is now down."""
    original = stub.use_next_skill

    async def cast(*args, **kwargs):
        await original(*args, **kwargs)
        stub.inv[item_name] = stub.inv.get(item_name, 0) + amount
        stub._monsters_dead = True

    stub.use_next_skill = cast


def _rank_on_turn_in(stub, faction, amount):
    original = stub.ensure_turn_in_quest

    async def turn_in(quest_id, item_id=-1, quantity=1):
        result = await original(quest_id, item_id, quantity)
        stub._ranks[faction] = stub._ranks.get(faction, 0) + amount
        return result

    stub.ensure_turn_in_quest = turn_in


class _HuntStub(Stub):
    """Credits each hunt on the first cast, so a farm loop ends on its own.

    ``hunt_item`` whitelists the item it is about to farm with ``add_drop``, so
    that call names whatever the next cast should produce -- no per-item setup.
    ``turn_in_rewards`` does the same for a quest's reward, so a ``Wait.ForPickup``
    poll (``wait_for_item``) finds it.
    """

    def __init__(self, *args, turn_in_rewards=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._wanted = None
        self.turn_in_rewards = {int(k): v
                                for k, v in (turn_in_rewards or {}).items()}

    def add_drop(self, names):
        super().add_drop(names)
        self._wanted = names if isinstance(names, str) else names[0]

    async def use_next_skill(self, *args, **kwargs):
        if self._wanted:
            self.inv[self._wanted] = self.inv.get(self._wanted, 0) + 1
        await super().use_next_skill(*args, **kwargs)

    async def ensure_turn_in_quest(self, quest_id, item_id=-1, amount=1):
        result = await super().ensure_turn_in_quest(quest_id, item_id, amount)
        reward = self.turn_in_rewards.get(int(quest_id))
        if reward:
            self.inv[reward] = self.inv.get(reward, 0) + 1
        return result


class _QtyPlayer:
    """The three name lookups ``dynamic_quant`` reads, and nothing else."""

    def __init__(self, inventory=None, bank=None, temp=None):
        self._inventory = dict(inventory or {})
        self._bank = dict(bank or {})
        self._temp = dict(temp or {})

    @staticmethod
    def _found(source, name):
        qty = source.get(name)
        return None if qty is None else type("I", (), {"qty": qty})()

    def get_item_inventory(self, name):
        return self._found(self._inventory, name)

    def get_item_bank(self, name):
        return self._found(self._bank, name)

    def get_item_temp_inventory(self, name):
        return self._found(self._temp, name)


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
    assert asyncio.run(farm_faction(unknown, "Arcangrove", 10)) is False
    assert unknown.calls == [], unknown.calls          # reported, never farmed
    assert set(FACTION_FARMS) == {"Good", "Vampire", "Yokai", "Evil",
                                  "ChronoSpan", "CraggleRock"}, \
        sorted(FACTION_FARMS)
    known = Stub(vampire_rank=10)
    assert asyncio.run(farm_faction(known, "Vampire", 10)) is True
    print("dispatch   : ported factions run, the rest are named and refused")

    # --- buy_item: wait for the shop, and check it carries the item -----
    # Command.buy_item only *asks* for an unseen shop, so buying on that first
    # call looks like a purchase that never happened
    from bot.core_bots import buy_item

    never = Stub()
    never.shop_loads = False
    assert asyncio.run(buy_item(never, 1212, "Receipt of Nulgath")) is False
    assert ("ensure_load_shop", 1212) in never.calls, never.calls
    assert "buy_item" not in never.kinds(), never.calls
    print("buy_item   : shop never loads -> reported, nothing bought")

    lacking = Stub()
    lacking.bot.loaded_shop_datas.append(_Shop(1212, ["Something Else"]))
    assert asyncio.run(buy_item(lacking, 1212, "Receipt of Nulgath")) is False
    assert "buy_item" not in lacking.kinds(), lacking.calls
    print("buy_item   : shop lacks the item -> reported, nothing bought")

    stocked = Stub()
    stocked.bot.loaded_shop_datas.append(_Shop(68, ["Blade of Affliction"]))
    assert asyncio.run(buy_item(stocked, 68, "Blade of Affliction")) is True
    assert ("buy_item", 68, "blade of affliction", 1, 0) in stocked.calls, \
        stocked.calls
    print("buy_item   : shop loaded and stocked -> bought once")

    # a shop only loads in its own map, so the map comes first
    mapped = Stub()
    mapped.bot.loaded_shop_datas.append(_Shop(89, ["Shadow Lich"]))
    assert asyncio.run(buy_item(mapped, 89, "Shadow Lich",
                                map_name="shadowfall")) is True
    kinds = mapped.kinds()
    assert "join_map" in kinds and "ensure_load_shop" in kinds, mapped.calls
    assert kinds.index("join_map") < kinds.index("ensure_load_shop"), kinds
    print("buy_item   : joins the shop's map before loading the shop")

    unreachable = Stub()
    unreachable._connected = False
    assert asyncio.run(buy_item(unreachable, 89, "Shadow Lich",
                                map_name="shadowfall")) is False
    assert "buy_item" not in unreachable.kinds(), unreachable.calls
    print("buy_item   : a dropped connection stops before the shop")

    # --- ensure_load_shop is bounded ------------------------------------
    # it used to be `while True`, so a shop the server never sends hung the bot
    # with no message at all
    from core.command import Command

    real_sleep = asyncio.sleep
    try:
        async def instant(_seconds):
            return None

        asyncio.sleep = instant

        silent = _ShopBot()
        cmd = Command(silent)
        cmd.SHOP_LOAD_MAX_ATTEMPTS = 3
        assert asyncio.run(cmd.ensure_load_shop(2114)) is False
        assert len(silent.sent) == 3, silent.sent    # one ask per attempt
        print("shop       : never arrives -> gives up after the bound")

        answering = _ShopBot(answers=True)
        cmd = Command(answering)
        assert asyncio.run(cmd.ensure_load_shop(2114)) is True
        assert len(answering.sent) == 1, answering.sent
        assert [s.shop_id for s in answering.loaded_shop_datas] == ["2114"]
        print("shop       : one request, then the reply is in the cache")
    finally:
        asyncio.sleep = real_sleep

    # --- the four newer reputation methods -----------------------------
    from bot.core_farms import (chronospan_rep, craggle_rock_rep, evil_rep,
                                monster_by_definition_id, yokai_rep)

    for name, farm in (("Yokai", yokai_rep), ("Evil", evil_rep),
                       ("ChronoSpan", chronospan_rep),
                       ("CraggleRock", craggle_rock_rep)):
        done = Stub(ranks={name: 10})
        asyncio.run(farm(done, 10))
        assert done.calls == [], (name, done.calls)
    print("rep        : all four stop when the rank is already there")

    yokai = Stub()
    asyncio.run(yokai_rep(yokai, 10))
    assert ("join_map", "dragonkoiz") in yokai.calls, yokai.calls
    assert ("register_quest", 383) in yokai.calls, yokai.calls
    assert ("add_drop", ("Piece of Pockey",)) in yokai.calls, yokai.calls
    print("yokai      : quest 383 in /dragonkoiz")

    evil_f2p = Stub(connect_after=0)
    _rank_gain(evil_f2p, "Evil", 4)
    asyncio.run(evil_rep(evil_f2p, 10))
    assert evil_f2p.bot.sent[0].endswith("%41%2%"), evil_f2p.bot.sent
    assert ("join_map", "swordhavenbridge") in evil_f2p.calls, evil_f2p.calls
    assert ("register_quest", 367) in evil_f2p.calls, evil_f2p.calls
    assert ("join_map", "castleundead") in evil_f2p.calls, evil_f2p.calls
    assert ("ensure_accept_quest", 366) not in evil_f2p.calls, evil_f2p.calls
    print("evil       : Evil alignment, 364 then 367 in /castleundead")

    evil_mem = Stub(member=True, ranks={"Evil": 4},
                    inventory={"Chair": 4, "Table": 2, "Bookcase": 1})
    _rank_on_turn_in(evil_mem, "Evil", 6)
    asyncio.run(evil_rep(evil_mem, 10))
    assert ("ensure_accept_quest", 366) in evil_mem.calls, evil_mem.calls
    assert ("ensure_turn_in_quest", 366) in evil_mem.calls, evil_mem.calls
    assert ("join_map", "castleundead") not in evil_mem.calls, evil_mem.calls
    assert evil_mem._ranks["Evil"] == 10, evil_mem._ranks
    print("evil       : members run quest 366, not /castleundead")

    chrono = Stub()
    asyncio.run(chronospan_rep(chrono, 10))
    assert ("register_quest", 2204) in chrono.calls, chrono.calls
    assert ("jump_cell", "r6", "Left") in chrono.calls, chrono.calls
    assert ("jump_cell", "r4", "Left") in chrono.calls, chrono.calls
    print("chronospan : quest 2204 across thespan r6 and r4")

    no_monster = Stub()
    asyncio.run(craggle_rock_rep(no_monster, 10))
    assert ("register_quest", 7277) in no_monster.calls, no_monster.calls
    assert ("cancel_registered_quests",) in no_monster.calls, no_monster.calls
    assert "use_next_skill" not in no_monster.kinds(), no_monster.calls
    print("craggle    : no monster 560 -> reported, nothing attacked")

    class _Mon:
        def __init__(self, mon_id, frame, map_id):
            self.mon_id = monster_id = mon_id
            self.frame = frame
            self.mon_map_id = map_id

    hunted = Stub()
    hunted.bot.monsters.append(_Mon(560, "r2", "7"))
    asyncio.run(craggle_rock_rep(hunted, 10))
    assert ("jump_cell", "r2", "Left") in hunted.calls, hunted.calls
    assert ("use_next_skill",) in hunted.calls, hunted.calls
    assert monster_by_definition_id(hunted, 560) is hunted.bot.monsters[0]
    # either id the model carries is accepted, because which one Skua's
    # Monster.ID is cannot be told from the scripts
    assert monster_by_definition_id(hunted, "7") is hunted.bot.monsters[0]
    assert monster_by_definition_id(hunted, 561) is None
    print("craggle    : monster id 560 -> jumps to its cell and hits it")

    # --- the Bludrut Brawl boss ----------------------------------------
    from bot.core_farms import bludrut_brawl_boss

    held = Stub(inventory={"Combat Trophy": 10})
    assert asyncio.run(bludrut_brawl_boss(held, "Combat Trophy", 10)) is True
    assert held.calls == [], held.calls
    print("brawl      : already at the target -> no calls")

    brawl = Stub(connect_after=0, inventory={"Mithril PvP Amulet +15000": 1})
    brawl.cell_ok = True
    _drop_gain(brawl, "Combat Trophy", 1)
    assert asyncio.run(bludrut_brawl_boss(brawl, "Combat Trophy", 1)) is True
    assert ("join_map", "bludrutbrawl") in brawl.calls, brawl.calls
    assert ("jump_cell", "Enter0", "Spawn") in brawl.calls, brawl.calls
    assert ("equip_item", "Mithril PvP Amulet +15000") in brawl.calls
    assert [c for c in brawl.calls if c[0] == "walk_to"], brawl.calls
    assert any(m.startswith("%xt%zm%mtcid%") for m in brawl.bot.sent), brawl.bot.sent
    assert ("join_map", "battleon") in brawl.calls, brawl.calls
    print("brawl      : one pass walks the route, credits the trophy, leaves")

    ads = Stub(connect_after=0)
    ads.cell_ok = True
    _drop_gain(ads, "Combat Trophy", 1)
    assert asyncio.run(bludrut_brawl_boss(ads, "Combat Trophy", 1,
                                          kill_ads=True)) is True
    assert any(f"%xt%zm%mtcid%{ads.bot.areaId}%18%" == m for m in ads.bot.sent), \
        ads.bot.sent
    print("brawl      : kill_ads walks the extra cells")

    died = Stub(connect_after=0)
    died.cell_ok = True
    died._monsters_dead = True
    died.player.ISDEAD = True
    assert asyncio.run(bludrut_brawl_boss(died, "Combat Trophy", 1)) is False
    assert ("join_map", "battleon") in died.calls, died.calls
    print("brawl      : a death leaves for /battleon and reports the stop")

    # --- BattleUnderB and TheSecret4 ------------------------------------
    from bot.core_farms import (battle_under_b, bone_some_dust, the_secret4)

    have_dust = Stub(inventory={"Bone Dust": 10000})
    asyncio.run(battle_under_b(have_dust, "Bone Dust", 10000))
    # the reference logs the line and returns, so only the log is expected
    assert [c for c in have_dust.calls if c[0] != "farming_logger"] == [], \
        have_dust.calls
    print("battleund  : already at the target -> only the logger line")

    dust = Stub(connect_after=0)
    dust.player.CELL = "r1"
    dust.player.PAD = "Left"
    _drop_gain(dust, "Bone Dust", 10000)
    asyncio.run(battle_under_b(dust, "Bone Dust", 10000))
    assert ("join_map", "battleunderb") in dust.calls, dust.calls
    assert ("jump_cell", "Enter", "Spawn") in dust.calls, dust.calls
    assert ("add_drop", "Bone Dust") in dust.calls, dust.calls
    print("battleund  : kills in battleunderb Enter/Spawn for the item")

    orb = Stub(connect_after=0)
    _drop_gain(orb, "Spirit Orb", 65000)
    asyncio.run(bone_some_dust(orb, 65000))
    assert ("register_quest", 2082) in orb.calls, orb.calls
    assert ("register_quest", 2083) in orb.calls, orb.calls
    assert ("cancel_registered_quests",) in orb.calls, orb.calls
    print("bonesome   : quests 2082/2083 until the Spirit Orbs are full")

    secret = Stub(connect_after=0)
    secret.cell_ok = True
    _drop_gain(secret, "The Secret 4", 1)
    asyncio.run(the_secret4(secret))
    assert ("jump_cell", "Enter0", "Spawn") in secret.calls, secret.calls
    assert ("walk_to", 528, 255) in secret.calls, secret.calls
    assert any(f"%xt%zm%mtcid%{secret.bot.areaId}%20%" == m
               for m in secret.bot.sent), secret.bot.sent
    assert ("join_map", "battleon") in secret.calls, secret.calls
    print("secret4    : the brawl route, one walk, both restorers, then out")

    # --- the Kitsune listener's rule, as a pure function ----------------
    from bot.core_bots import kitsune_shifted, parse_message

    def _ct(aura, action):
        return json.dumps({"t": "xt", "b": {"o": {"cmd": "ct", "a": [
            {"cmd": action, "aura": {"nam": aura}}]}}})

    assert kitsune_shifted(_ct("Shapeshifted", "aura+")) is True
    assert kitsune_shifted(_ct("Shapeshifted", "aura-")) is False
    # anything else must leave the caller's state alone, not clear it
    assert kitsune_shifted(_ct("Something Else", "aura+")) is None
    assert kitsune_shifted(json.dumps({"t": "xt",
                                       "b": {"o": {"cmd": "ccqr"}}})) is None
    assert kitsune_shifted("%xt%zm%anything%") is None
    assert parse_message(json.dumps({"t": "xt", "b": {"o": {"cmd": "ct"}}})) \
        == {"cmd": "ct"}
    assert parse_message("not json") is None
    print("kitsune    : the Shapeshifted rule reads on/off, nothing else")

    # --- buy_item: the id form, and the shop entry id -------------------
    from bot.core_bots import dynamic_quant, wait_for_item

    by_id = Stub()
    by_id.bot.loaded_shop_datas.append(
        _Shop(44, [_ShopItem("Some Item", 38316, 22367)]))
    assert asyncio.run(buy_item(by_id, 44, 38316, map_name="citadel",
                                shop_item_id=22367)) is True
    assert ("buy_item", 44, "some item", 1, 22367) in by_id.calls, by_id.calls
    print("buy_item   : item id + shop entry id buys that entry")

    owned = Stub()
    owned.owned_ids = {"38316"}
    assert asyncio.run(buy_item(owned, 44, 38316)) is True
    assert owned.calls == [("has_item_id", 38316)], owned.calls
    print("buy_item   : the id form stops when that id is already held")

    twice = Stub()
    twice.bot.loaded_shop_datas.append(_Shop(900, ["Twin", "Twin"]))
    assert asyncio.run(buy_item(twice, 900, "Twin")) is False
    assert "buy_item" not in twice.kinds(), twice.calls
    print("buy_item   : a name the shop carries twice is refused, not guessed")

    # --- dynamic_quant / wait_for_item ----------------------------------
    qty = Stub()
    qty.bot.player = _QtyPlayer(inventory={"Unidentified 13": 3},
                                bank={"Unidentified 13": 2})
    assert dynamic_quant(qty, "Unidentified 13") == 5
    assert dynamic_quant(qty, "Unidentified 13", is_temp=True) == 0
    assert dynamic_quant(qty, "Something Else") == 0
    print("quant      : bank counts with the inventory, temp only on ask")

    assert asyncio.run(wait_for_item(Stub(inventory={"Elders' Blood": 1}),
                                     "Elders' Blood")) is True
    assert asyncio.run(wait_for_item(Stub(), "Elders' Blood",
                                     timeout_ms=1000)) is False
    print("pickup     : held is immediate; a drop that never lands times out")

    # --- Black Knight Orb (quest 318) -----------------------------------
    from bot.core_farms import BLACK_KNIGHT_ORB_PIECES, black_knight_orb

    have_orb = Stub(inventory={"Black Knight Orb": 1})
    asyncio.run(black_knight_orb(have_orb))
    assert have_orb.calls == [], have_orb.calls
    print("blackknight: already held -> no calls")

    refused_orb = Stub(accept=False)
    asyncio.run(black_knight_orb(refused_orb))
    assert ("ensure_accept_quest", 318) in refused_orb.calls, refused_orb.calls
    assert "use_next_skill" not in refused_orb.kinds(), refused_orb.calls
    print("blackknight: quest 318 refused -> reported, nothing killed")

    orb = _HuntStub(connect_after=0)
    asyncio.run(black_knight_orb(orb))
    assert [c[1] for c in orb.calls if c[0] == "join_map"] == \
        [piece[0] for piece in BLACK_KNIGHT_ORB_PIECES], orb.calls
    assert ("ensure_turn_in_quest", 318) in orb.calls, orb.calls
    print("blackknight: the four pieces in the four maps, then the turn-in")

    # --- Elders' Blood (quest 802, one a day) ---------------------------
    from bot.core_dailies import elders_blood

    done_today = Stub(accept=False)
    asyncio.run(elders_blood(done_today))
    assert ("ensure_accept_quest", 802) in done_today.calls, done_today.calls
    assert "use_next_skill" not in done_today.kinds(), done_today.calls
    print("elders     : a refused accept is today's being done -- nothing killed")

    full = Stub(inventory={"Elders' Blood": 20})
    asyncio.run(elders_blood(full))
    assert full.calls == [], full.calls
    print("elders     : at the item's cap -> no calls")

    blood = _HuntStub(connect_after=0, turn_in_rewards={802: "Elders' Blood"})
    asyncio.run(elders_blood(blood))
    assert ("join_map", "arcangrove") in blood.calls, blood.calls
    assert ("jump_cell", "LeftBack", "Left") in blood.calls, blood.calls
    assert ("add_drop", "Slain Gorillaphant") in blood.calls, blood.calls
    assert ("ensure_accept_quest", 802) in blood.calls, blood.calls
    assert ("ensure_turn_in_quest", 802) in blood.calls, blood.calls
    assert blood.inv.get("Elders' Blood") == 1, blood.inv
    # the source's own log line, verbatim: the port's log has to read like it
    assert "Daily: Elders' Blood" in blood.bot.logs, blood.bot.logs
    print("elders     : quest 802 in /arcangrove LeftBack for the one Blood")

    print("\nfarm tests OK")


if __name__ == "__main__":
    main()
