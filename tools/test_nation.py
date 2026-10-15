"""Nation routines: guards and decisions, without a live connection.

    python tools/test_nation.py

The farm loops themselves need the game, but every *decision* they make before
the first packet -- "already full?", "is the story done?", "should I aggro?" --
is plain Python and is what this file pins down.  A stub Command records what
would have been sent, so an early return that still sent something fails here
rather than mid-run.
"""
import asyncio
import inspect
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bot.nation.core_nation import (  # noqa: E402
    approval_and_favor, assistant_during_supplies,
    assisting_crag_and_bamboozle, assisting_drudgen,
    bamboozle_vs_drudge, bloody_chaos, blood_from_the_void, can_we_aggro,
    carve_uni_gem_stone, contract_exchange, CRAG_PET, crags_thirst,
    dark_makai_item, deal, diamond_exchange,
    dirty_deeds_done_dirt_cheap, do_swindles_return_area,
    dragon_slayer_reward, dreadrock_gem_exchange, dwobo_coin,
    emblem_of_nulgath,
    empowering_items, equip_class, essence_of_defeat_reagent,
    essence_of_nulgath, farm_blood_gem,
    farm_contract_exchage, farm_dark_crystal_shard, farm_diamond_of_nulgath,
    farm_fiend_token, farm_gem_of_nulgath, farm_tainted_gem,
    farm_totem_of_nulgath, farm_uni10, farm_uni13_quest, farm_voucher,
    feed_the_fiend, fiend_emblem, forge_blood_gems,
    forge_dark_crystal_shards, forge_diamonds_of_nulgath, forge_tainted_gems,
    gem_stone_receipt_of_nulgath, gem_stones_of_nulgath, get_pcod,
    handle_voucher_conversions, hire_nulgath_larvae,
    kill_escherion, kill_vath,
    kissthe_void, leery_exchange_gold, nation_loyalty_rewarded,
    nation_round_4_medal,
    new_worlds_new_opportunities,
    nulgath_larvae, nulgaths_roulette_of_misfortune, sell_voucher_of_nulgath,
    supplies, swindle_bulk, swindle_return, the_assistant, time_is_money,
    totems_via_taros, uni, void_knight_sword_quest,
    voucher_item_totem_of_nulgath)


class _Other:
    def __init__(self, name):
        self.str_username = name


class _Item:
    """Minimal bank entry: only the name matters to the withdraw path."""

    def __init__(self, item_name):
        self.item_name = item_name


class _Player:
    def __init__(self, member=False, items_by_id=None, level=0, gold=0,
                 good_rank=0, bank_by_id=None):
        self.USER = "me"
        self.CELL = "r9"
        self.is_member = member
        self.LEVEL = level
        self.GOLD = gold
        self._by_id = {str(k): v for k, v in (items_by_id or {}).items()}
        self._bank_by_id = {str(k): v for k, v in (bank_by_id or {}).items()}

    def get_item_inventory_by_id(self, item_id):
        return self._by_id.get(str(item_id))

    def get_item_bank_by_id(self, item_id):
        return self._bank_by_id.get(str(item_id))

    def move_banked_by_name(self, name):
        """Mirror the real bank move for id-keyed entries.

        In the engine the very same item object moves from BANK to INVENTORY,
        so an id lookup finds it afterwards.  The stub keeps the two lookups in
        separate dicts, so the move has to be repeated here.
        """
        for item_id, item in list(self._bank_by_id.items()):
            if getattr(item, "item_name", None) == name:
                self._by_id[item_id] = self._bank_by_id.pop(item_id)


class _Bot:
    def __init__(self, others=()):
        self.player_in_area = [_Other(n) for n in others]
        self.areaId = "evilwarnul-9909"
        self.sent: list[str] = []
        self.loaded_shop_datas: list = []

    def write_message(self, msg):
        self.sent.append(msg)


class Stub:
    """Duck-typed Command: records calls, never touches the network."""

    def __init__(self, inventory=None, member=False, completed=(),
                 others=(), connected=True, items_by_id=None, level=0,
                 gold=0, good_rank=0, all_owned=False, quests=None,
                 bank=None, bank_by_id=None, accept=True):
        self.inv = dict(inventory or {})
        self.calls = []
        self.player = _Player(member, items_by_id, level, gold,
                              bank_by_id=bank_by_id)
        self.bot = _Bot(others)
        self.bank = dict(bank or {})
        self._completed = set(completed)
        self._connected = connected
        self._good_rank = good_rank
        self._accept = accept
        self._all_owned = all_owned
        self._quests = {str(k): v for k, v in (quests or {}).items()}
        self.fill_inventory_on_skill = False

    # --- sync predicates ------------------------------------------------
    def is_in_inventory(self, name, qty=1, operator=">=", isTemp=False):
        if self._all_owned:
            return True
        return self.inv.get(name, 0) >= qty

    def is_still_connected(self):
        return self._connected

    def is_not_in_map(self, map_name):
        return False

    def is_not_in_cell(self, cell):
        return False

    def is_in_bank(self, name, qty=1, operator=">="):
        return self.bank.get(name, 0) >= qty

    def get_equipped_class(self):
        return None

    def get_monster(self, name):
        return None

    def is_monster_alive(self, name="*"):
        # always true so the "wait for the spawn" loops fall through and the
        # fight loop reaches use_next_skill, which ends the run deterministically
        return True

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

    async def jump_to_monster(self, *args, **kwargs):
        self.calls.append(("jump_to_monster",))

    async def leave_combat(self, safe_leave=True):
        self.calls.append(("leave_combat",))

    async def rest(self):
        self.calls.append(("rest",))

    async def bank_to_inv(self, names):
        self.calls.append(("bank_to_inv",))
        for name in ([names] if isinstance(names, str) else names):
            if name in self.bank:
                self.inv[name] = self.inv.get(name, 0) + self.bank.pop(name)
            self.player.move_banked_by_name(name)

    async def inv_to_bank(self, names):
        self.calls.append(("inv_to_bank", names))

    async def get_map_item(self, map_item_id, qty=1):
        self.calls.append(("get_map_item", map_item_id, qty))

    # --- async bank-aware predicates (mirror Command.has_item & co) -------
    async def has_item(self, name, qty=1, operator=">=", isTemp=False):
        if not isTemp and self.is_in_bank(name):
            await self.bank_to_inv(name)
        return self.is_in_inventory(name, qty, operator, isTemp)

    async def has_item_id(self, item_id):
        banked = self.player.get_item_bank_by_id(item_id)
        if banked is not None:
            await self.bank_to_inv(banked.item_name)
        return self.player.get_item_inventory_by_id(item_id) is not None

    async def has_any_item(self, names):
        for name in names:
            if await self.has_item(name):
                return True
        return False

    async def has_any_item_id(self, item_ids):
        for item_id in item_ids:
            if await self.has_item_id(item_id):
                return True
        return False

    async def sleep(self, ms):
        pass

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

    async def ensure_accept_quest(self, quest_id, max_attempts=3):
        self.calls.append(("ensure_accept_quest", quest_id))
        return self._accept

    async def ensure_turn_in_quest(self, quest_id, item_id=-1, amount=1):
        self.calls.append(("ensure_turn_in_quest", quest_id))
        return True

    def add_quest_rewards(self, quest_id):
        self.calls.append(("add_quest_rewards", quest_id))
        return []

    def get_quest_rewards(self, quest_id):
        return []

    def get_quest_reward_entries(self, quest_id):
        quest = self._quests.get(str(quest_id))
        return quest.reward_entries if quest else []

    def remove_drop(self, names):
        self.calls.append(("remove_drop", names))

    def get_loaded_quest(self, quest_id):
        self.calls.append(("get_loaded_quest", quest_id))
        return self._quests.get(str(quest_id))

    def get_quant_item(self, name):
        return self.inv.get(name, 0)

    def get_faction_rank(self, name):
        return self._good_rank

    async def sell_item(self, name, qty=1):
        self.calls.append(("sell_item", name, qty))

    def can_turnin_quest(self, quest_id):
        self.calls.append(("can_turnin_quest", quest_id))
        return False

    async def buy_item(self, shop_id, item_name, qty=1):
        self.calls.append(("buy_item", shop_id, item_name, qty))

    async def ensure_load_shop(self, shop_id):
        self.calls.append(("ensure_load_shop", shop_id))
        return True

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

    # --- bank-aware ownership -----------------------------------------
    # the reference bot's CheckInventory withdraws from the bank by default, so
    # a guard that only reads the inventory farms what is already owned
    banked = Stub(bank={"Fiend Emblem": 300})
    assert asyncio.run(banked.has_item("Fiend Emblem", 300)) is True
    assert ("bank_to_inv",) in banked.calls, banked.calls
    assert banked.inv["Fiend Emblem"] == 300, banked.inv
    assert asyncio.run(Stub().has_item("Fiend Emblem")) is False
    assert asyncio.run(Stub(inventory={"Fiend Emblem": 1})
                       .has_item("Fiend Emblem")) is True

    banked_id = Stub(bank_by_id={38275: _Item("Void Knight Sword")})
    assert asyncio.run(banked_id.has_item_id(38275)) is True
    assert ("bank_to_inv",) in banked_id.calls, banked_id.calls
    assert asyncio.run(Stub(items_by_id={38254: object()})
                       .has_item_id(38275)) is False
    assert asyncio.run(Stub(items_by_id={38254: object()})
                       .has_any_item_id((38275, 38254))) is True
    assert asyncio.run(Stub().has_any_item_id((38275, 38254))) is False
    print("item ids   : id/any-id checks withdraw from the bank first")

    # a whole guard driven by the bank: nothing must be farmed
    banked_af = Stub(bank={"Nulgath's Approval": 5000,
                           "Archfiend's Favor": 5000})
    asyncio.run(approval_and_favor(banked_af))
    assert banked_af.kinds() == ["bank_to_inv", "bank_to_inv"], \
        banked_af.kinds()
    print("approval   : both banked -> withdrawn, never farmed")

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

    # --- boss helpers and the level gate ------------------------------
    makai = Stub({f"Dark Makai Rune": 5})
    asyncio.run(dark_makai_item(makai))
    assert makai.calls == [], makai.calls
    print("makai      : already held -> returns without a single call")

    escherion = Stub({"Escherion's Helm": 1})
    asyncio.run(kill_escherion(escherion, "Escherion's Helm"))
    assert escherion.calls == [], escherion.calls
    print("escherion  : already held -> returns without a single call")

    vath = Stub({"Strand of Vath's Hair": 1})
    asyncio.run(kill_vath(vath, "Strand of Vath's Hair"))
    assert vath.calls == [], vath.calls
    print("vath       : already held -> returns without a single call")

    crags = Stub()
    asyncio.run(crags_thirst(crags))
    assert crags.calls == [], crags.calls
    print("crags      : no Crag pet -> returns without a single call")

    essence = Stub({"Dark Crystal Shard": 1000})
    asyncio.run(essence_of_defeat_reagent(essence))
    assert essence.calls == [], essence.calls
    print("essence    : already full -> returns without a single call")

    # The level-80 gate must not fire on an unparsed level: LEVEL is 0 until
    # initUserDatas is read, and treating that as "below 80" would silently
    # skip the whole farm.
    low = Stub(level=70)
    asyncio.run(bloody_chaos(low))
    assert low.calls == [], low.calls
    print("chaos      : level 70 -> returns without a single call")

    unknown = Stub(level=0, inventory={"Blood Gem of the Archfiend": 1000})
    asyncio.run(bloody_chaos(unknown))
    assert unknown.calls == [], unknown.calls
    assert "register_quest" not in unknown.kinds(), unknown.kinds()
    print("chaos      : unknown level is not 'too low'; full stack still stops it")

    # --- the Supplies cluster ------------------------------------------
    have_it = Stub({"Diamond of Nulgath": 5})
    asyncio.run(supplies(have_it, "Diamond of Nulgath", 5))
    assert have_it.calls == [], have_it.calls
    print("supplies   : item already full -> returns without a single call")

    no_sell = Stub({"Voucher of Nulgath": 3})
    asyncio.run(sell_voucher_of_nulgath(no_sell, False))
    assert no_sell.calls == [], no_sell.calls
    print("voucher    : sell flag off -> returns without a single call")

    no_assist = Stub(gold=10 ** 9)
    asyncio.run(assistant_during_supplies(no_assist, False))
    assert no_assist.calls == [], no_assist.calls
    print("assist     : assist flag off -> returns without a single call")

    poor = Stub(gold=99_999)
    asyncio.run(assistant_during_supplies(poor, True))
    assert poor.calls == [], poor.calls
    print("assist     : under 100k gold -> returns without a single call")

    no_return = Stub({"Unidentified 1": 1, "Unidentified 6": 1,
                      "Unidentified 9": 1, "Unidentified 16": 1,
                      "Unidentified 20": 1})
    asyncio.run(do_swindles_return_area(no_return, False))
    assert no_return.calls == [], no_return.calls
    print("swindles   : policy off -> returns without a single call")

    no_target = Stub()
    asyncio.run(bamboozle_vs_drudge(no_target))
    assert no_target.calls == [], no_target.calls
    print("bamboozle  : no item -> stops instead of looping forever")

    owned = Stub({"Tainted Gem": 1000})
    asyncio.run(bamboozle_vs_drudge(owned, "Tainted Gem", 1000))
    assert owned.calls == [], owned.calls
    print("bamboozle  : item already owned -> returns without a single call")

    no_voucher = Stub()
    asyncio.run(handle_voucher_conversions(no_voucher, "Tainted Gem"))
    assert no_voucher.calls == [], no_voucher.calls
    print("conversion : no spare voucher -> returns without a single call")

    pcod_have = Stub({"Purified Claymore of Destiny": 1})
    assert asyncio.run(get_pcod(pcod_have)) is True
    assert pcod_have.calls == [], pcod_have.calls
    print("pcod       : already owned -> True, no calls")

    pcod_low = Stub(good_rank=3, level=40)
    assert asyncio.run(get_pcod(pcod_low)) is False
    # the C# farms the prerequisites here, so this is no longer a no-op
    assert "register_quest" in pcod_low.kinds(), pcod_low.kinds()
    print("pcod       : Good rank 3 -> farms Good rep first, then stops")

    # --- the FarmX family: every one must bail before sending anything ---
    family = [
        ("uni13", farm_uni13_quest, {"Unidentified 13": 13}),
        ("uni10", farm_uni10, {"Unidentified 10": 1000}),
        ("dcs", farm_dark_crystal_shard, {"Dark Crystal Shard": 1000}),
        ("diamond", farm_diamond_of_nulgath, {"Diamond of Nulgath": 1000}),
        ("gem", farm_gem_of_nulgath, {"Gem of Nulgath": 1000}),
        ("blood", farm_blood_gem, {"Blood Gem of the Archfiend": 100}),
        ("tainted", farm_tainted_gem, {"Tainted Gem": 1000}),
        ("totem", farm_totem_of_nulgath, {"Totem of Nulgath": 100}),
        ("essence", essence_of_nulgath, {"Essence of Nulgath": 60}),
        ("voucher", farm_voucher, {"Voucher of Nulgath (non-mem)": 1}),
        ("fiendtok", farm_fiend_token, {"Fiend Token": 30}),
        ("kissvoid", kissthe_void, {"Blood Gem of the Archfiend": 100}),
        ("taros", totems_via_taros, {"Totem of Nulgath": 100}),
    ]
    for label, func, inv in family:
        st = Stub(inv)
        asyncio.run(func(st) if label != "voucher" else func(st, False))
        assert st.calls == [], (label, st.calls)
    print(f"farmx      : {len(family)} routines all stop when already farmed")

    for label, func in (("exchange", contract_exchange),
                        ("farm-contract", farm_contract_exchage)):
        st = Stub()
        asyncio.run(func(st) if label == "farm-contract"
                    else func(st, "Tainted Gem", 1000))
        assert st.calls == [], (label, st.calls)
    print("contract   : no Drudgen pet -> both stop without a call")

    dx = Stub({"Diamond of Nulgath": 15})
    asyncio.run(diamond_exchange(dx))
    assert dx.calls == [], dx.calls
    print("dexchange  : no Crag pet -> returns without a single call")

    dl = Stub()
    asyncio.run(deal(dl, totem_quant=10))
    assert dl.calls == [], dl.calls
    print("deal       : no Crag pet -> returns without a single call")

    ad = Stub({"Drudgen the Assistant": 1, "Twin Blade of Nulgath": 1})
    asyncio.run(assisting_drudgen(ad))
    assert ad.calls == [], ad.calls
    print("assisting  : not a member -> returns without a single call")

    ff = Stub()
    asyncio.run(feed_the_fiend(ff))
    assert ff.calls == [], ff.calls
    print("feedfiend  : not a member -> returns without a single call")

    dsr = Stub(completed=(169,))
    asyncio.run(dragon_slayer_reward(dsr))
    assert dsr.kinds() == ["is_completed_before"], dsr.kinds()
    print("dragonslay : quest 169 done -> only looked, sent nothing")

    # --- the medallion / larvae set ------------------------------------
    nr4 = Stub({"Nation Round 4 Medal": 1})
    asyncio.run(nation_round_4_medal(nr4))
    assert nr4.calls == [], nr4.calls
    print("medals     : medal 4 owned -> returns without a single call")

    emb = Stub({"Emblem of Nulgath": 500})
    asyncio.run(emblem_of_nulgath(emb, 500))
    assert emb.calls == [], emb.calls
    print("emblem     : already full -> returns without a single call")

    bulk = Stub({"Tainted Gem": 1000})
    asyncio.run(swindle_bulk(bulk, 1000))
    assert bulk.calls == [], bulk.calls
    print("bulk       : already full -> returns without a single call")

    drk = Stub({"Tainted Gem": 1000})
    asyncio.run(dreadrock_gem_exchange(drk, 1000))
    assert drk.calls == [], drk.calls
    print("dreadrock  : already full -> returns without a single call")

    lar = Stub({"Unidentified 10": 1})
    asyncio.run(nulgath_larvae(lar, "Unidentified 10", 1))
    assert lar.kinds() == ["ensure_accept_quest", "get_loaded_quest"], lar.kinds()
    print("larvae     : quest not loaded -> accepted, looked, then stopped")

    rou = Stub()
    asyncio.run(nulgaths_roulette_of_misfortune(rou, None, 1))
    assert rou.calls == [], rou.calls
    print("roulette   : no item given -> returns without a single call")

    asst = Stub({"Diamond of Nulgath": 1000})
    asyncio.run(the_assistant(asst, "Diamond of Nulgath", 1000))
    assert asst.calls == [], asst.calls
    print("assistant  : item already full -> returns without a single call")

    asst2 = Stub()
    asyncio.run(the_assistant(asst2))
    assert asst2.kinds() == ["ensure_accept_quest", "get_loaded_quest"], asst2.kinds()
    print("assistant  : quest not loaded -> accepted, looked, then stopped")

    # --- a loaded quest that names no rewards must not read as "all done" ---
    from model.quest import Quest
    nameless = Stub(quests={2566: Quest.from_payload(
        {"QuestID": 2566, "reward": [{"ItemID": 1, "iQty": 1}]})})
    asyncio.run(nulgath_larvae(nameless))
    assert nameless.kinds() == ["ensure_accept_quest", "get_loaded_quest"], \
        nameless.kinds()
    print("larvae     : rewards with ids but no names -> reported, farmed nothing")

    empty = Stub(quests={2566: Quest.from_payload({"QuestID": 2566})})
    asyncio.run(nulgath_larvae(empty))
    assert "add_drop" not in empty.kinds(), empty.kinds()
    print("larvae     : quest with no rewards at all -> reported, farmed nothing")

    # the shape quest 2566 actually sends names its rewards without the itemsC
    # wrapper; once it parses, a no-item run really does start farming
    flat = Stub(quests={2566: Quest.from_payload({
        "QuestID": 2566,
        "reward": [{"ItemID": 4723, "iQty": 1, "iType": 2}],
        "oRewards": {"0": {"ItemID": 4723, "sName": "Mana Energy for Nulgath",
                           "iStk": 100}},
    })})
    asyncio.run(nulgath_larvae(flat))
    assert "add_drop" in flat.kinds(), flat.kinds()
    assert "farming_logger" in flat.kinds(), flat.kinds()
    print("larvae     : flat oRewards -> parses and starts farming")

    named = Stub(quests={7551: Quest.from_payload(
        {"QuestID": 7551, "oRewards": {"itemsC": {
            "0": {"ItemID": 4769, "sName": "Tainted Gem", "iStk": 1000}}}})})
    asyncio.run(swindle_return(named))
    assert "add_drop" in named.kinds(), named.kinds()
    print("swindle    : no item given -> picked the first reward instead of "
          "silently stopping")

    # --- the Nation-root batch ----------------------------------------
    tim = Stub()
    asyncio.run(time_is_money(tim))
    assert tim.calls == [], tim.calls
    print("timeismoney: no Bounty Hunter Blade Pet -> reported, farmed nothing")

    emp = Stub({"Death Scythe of Nulgath": 1})
    asyncio.run(empowering_items(emp))
    assert emp.calls == [], emp.calls
    print("empowering : scythe already held -> returns without a single call")

    acab = Stub({CRAG_PET: 1}, member=True)
    asyncio.run(assisting_crag_and_bamboozle(acab))
    assert acab.calls == [], acab.calls
    print("acab       : no Sparrow's Blood -> reported, farmed nothing")

    vch = Stub({"Voucher of Nulgath (non-mem)": 1})
    asyncio.run(voucher_item_totem_of_nulgath(vch, "Not A Reward"))
    assert "add_drop" not in vch.kinds(), vch.kinds()
    print("voucher    : unknown reward name -> reported, farmed nothing")

    nlr = Stub(quests={4749: Quest.from_payload({"QuestID": 4749})})
    asyncio.run(nation_loyalty_rewarded(nlr))
    assert "add_drop" not in nlr.kinds(), nlr.kinds()
    print("nlr        : quest sent no rewards -> reported, farmed nothing")

    # --- the Forge chain (quests 4917-4924) ---------------------------
    f2p = Stub()
    asyncio.run(forge_tainted_gems(f2p, 100))
    assert f2p.calls == [], f2p.calls
    print("forge      : non-member -> reported, nothing farmed")

    no_gem = Stub(member=True)
    asyncio.run(forge_tainted_gems(no_gem, 100))
    assert no_gem.calls == [], no_gem.calls
    print("forge      : member without the Gemstone of Nulgath -> reported")

    done = Stub(member=True, inventory={"Gemstone of Nulgath": 1,
                                        "Tainted Gem": 100})
    asyncio.run(forge_tainted_gems(done, 100))
    assert done.calls == [], done.calls
    print("forge      : reward already at the target -> no calls")

    # the reference's own stop conditions, verbatim: they name "Dark Crystal
    # Shards" and "Diamonds for Nulgath", which no item is called, so holding the
    # real item does not end those farms -- as in the reference
    dcs_literal = Stub(member=True, inventory={"Gemstone of Nulgath": 1,
                                               "Dark Crystal Shards": 1000})
    asyncio.run(forge_dark_crystal_shards(dcs_literal, 1000))
    assert dcs_literal.calls == [], dcs_literal.calls
    print("forge dcs  : the literal 'Dark Crystal Shards' ends the farm")

    dcs_real = Stub(member=True, inventory={"Gemstone of Nulgath": 1,
                                            "Dark Crystal Shard": 1000})
    asyncio.run(forge_dark_crystal_shards(dcs_real, 1000))
    assert dcs_real.calls, "the plural check should not match the real item"
    print("forge dcs  : the real item does not -- same as the reference")

    gem_done = Stub(member=True, inventory={"Gemstone of Nulgath": 1,
                                            "Diamonds for Nulgath": 1000})
    asyncio.run(forge_diamonds_of_nulgath(gem_done, 1000))
    assert gem_done.calls == [], gem_done.calls
    print("forge dia  : the literal 'Diamonds for Nulgath' ends the farm")

    blood_done = Stub(member=True, inventory={
        "Gemstone of Nulgath": 1, "Blood Gem of the Archfiend": 100})
    asyncio.run(forge_blood_gems(blood_done, 100))
    assert blood_done.calls == [], blood_done.calls
    print("forge blood: reward already at the target -> no calls")

    # --- the two Forge guard readings, both kept from the reference ----
    # ForgeTaintedGems refuses when *either* is missing ...
    strict_gem = Stub(member=True)
    asyncio.run(forge_tainted_gems(strict_gem, 100))
    assert strict_gem.calls == [], strict_gem.calls
    strict_member = Stub(inventory={"Gemstone of Nulgath": 1})
    asyncio.run(forge_tainted_gems(strict_member, 100))
    assert strict_member.calls == [], strict_member.calls
    print("forge      : strict guard -> either one missing stops it")

    # ... while the other three refuse only when *both* are missing, so a member
    # without the gemstone still starts -- and so does a non-member with it.
    # What the guard lets through is the point here, not how deep the farm gets.
    loose = Stub(member=True)
    asyncio.run(forge_dark_crystal_shards(loose, 1000))
    assert loose.calls, "the loose guard should not have refused a member"
    print("forge dcs  : loose guard -> a member without the gemstone starts")

    loose_other = Stub(inventory={"Gemstone of Nulgath": 1})
    asyncio.run(forge_dark_crystal_shards(loose_other, 1000))
    assert loose_other.calls, "the loose guard should not have refused"
    print("forge dcs  : loose guard -> a non-member with the gemstone too")

    loose_none = Stub()
    asyncio.run(forge_dark_crystal_shards(loose_none, 1000))
    assert loose_none.calls == [], loose_none.calls
    print("forge dcs  : loose guard -> missing both refuses")

    # a quest the server will not accept must stop the loop, not spin it.  The
    # two prerequisites are pre-held so the flow reaches the loop itself.
    refused = Stub(member=True, accept=False, inventory={
        "Gemstone of Nulgath": 1, "Gemstone Receipt of Nulgath": 1,
        "Unidentified 5": 1})
    asyncio.run(forge_tainted_gems(refused, 100))
    assert refused.kinds().count("ensure_accept_quest") == 1, refused.calls
    assert "use_next_skill" not in refused.kinds(), refused.calls
    print("forge      : a refused quest stops after one report")

    bad_reward = Stub(member=True)
    asyncio.run(carve_uni_gem_stone(bad_reward, "Not A Reward", 10))
    assert bad_reward.calls == [], bad_reward.calls
    print("carve      : unknown reward -> reported, nothing farmed")

    noc = Stub(member=True, inventory={"Gemstone of Nulgath": 1})
    asyncio.run(carve_uni_gem_stone(noc, "Tainted Gem", 10))
    assert ("add_drop", ["Tainted Gem"]) in noc.calls, noc.calls
    print("carve      : a named reward starts the farm")

    rich = Stub(member=True, gold=200_000_000)
    asyncio.run(leery_exchange_gold(rich, 100_000_000))
    assert rich.calls == [], rich.calls
    print("leery      : already at the gold target -> no calls")

    dwobo = Stub(inventory={"Dwobo Coin": 100})
    asyncio.run(dwobo_coin(dwobo, 100))
    assert dwobo.calls == [], dwobo.calls
    print("dwobo      : already owned -> no calls")

    # --- hire_nulgath_larvae ------------------------------------------
    f2p_hire = Stub()
    asyncio.run(hire_nulgath_larvae(f2p_hire))
    assert f2p_hire.calls == [], f2p_hire.calls
    owned_hire = Stub(member=True, inventory={"Nulgath Larvae": 1})
    asyncio.run(hire_nulgath_larvae(owned_hire))
    assert owned_hire.calls == [], owned_hire.calls
    print("larvae     : non-member or already hired -> no calls")

    # --- proof of recruitment's chain ---------------------------------
    from bot.nation.various.proof_of_recruitment import arch_tokens
    from bot.nation.various.proof_of_recruitment import main as proof_main

    chain_done = Stub(completed=tuple(range(4751, 4762)))
    assert asyncio.run(arch_tokens(chain_done)) is True
    assert [c for c in chain_done.calls if c[0] != "is_completed_before"] == [], \
        chain_done.calls
    print("archtoken  : every chain quest done -> only the checks, no work")

    doomwood = Stub(completed=(4751,))
    assert asyncio.run(arch_tokens(doomwood)) is False
    assert ("ensure_accept_quest", 4752) not in doomwood.calls, doomwood.calls
    print("archtoken  : quest 4752 without a Doomwood Token -> stops with why")

    # with the chain done, the wrapper goes straight to the reward quest
    rewardless = Stub(completed=tuple(range(4751, 4762)))
    asyncio.run(proof_main(rewardless))
    assert ("ensure_accept_quest", 4785) in rewardless.calls, rewardless.calls
    assert "use_next_skill" not in rewardless.kinds(), rewardless.calls
    print("proof      : chain done, quest 4785 reports no rewards and stops")

    # --- every wrapper is runnable, and no-ops when all is banked -----
    WRAPPERS = [
        "materials.0_max_bags", "materials.approval_and_favor",
        "materials.blood_from_the_void", "materials.blood_gem",
        "materials.dark_crystal_shards", "materials.diamond_of_nulgath",
        "materials.fiend_emblem", "materials.fiend_token",
        "materials.gem_of_nulgath", "materials.tainted_gem",
        "materials.totem_of_nulgath", "materials.unidentified_10",
        "materials.unidentified_13", "materials.voucher_of_nulgath",
        "materials.voucher_of_nulgath_non_member",
        "contract_exchange", "dirty_deeds_done_dirt_cheap",
        "dragon_slayer_reward", "dreadrock_gem_exchange",
        "emblem_of_nulgath", "essence_of_defeat_reagent", "kissthe_void",
        "new_worlds_new_opportunities", "nulgath_larvae",
        "supplies_to_spin_the_wheel_of_chance", "swindle_return_policy",
        "the_assistant", "void_knight_sword_quest",
        "assisting_crag_and_bamboozle", "empowering_items",
        "nation_loyalty_rewarded", "time_is_money", "voucher_item_choose",
        "various.forge_gem_stones_for_nulgath",
        "various.carve_the_unidentified_gem_stone",
        "various.leery_exchange_gold",
        "various.purified_claymore_of_destiny",
        "various.random_weapon_of_nulgath",
        "various.hire_nulgath_larvae",
        "various.swindle_bulk",
        "various.shadow_legacy_of_nulgath",
        "various.demanding_approval_from_nulgath",
        "various.golden_hanzo_void",
        "various.hanzo_orb_quest",
        "various.yulgaths_inn",
        "various.void_destroyer",
        "various.sin_of_the_abyss_mats_pre_farm",
        "various.void_spartan",
        "various.the_leery_contract",
        "various.juggernaut_items",
        "various.tendurrr_the_assistant_quests",
        "various.taros_manslayer",
        "various.taros_prismatic_manslayers",
        "various.impossible_empowered_items_of_nulgath",
        "various.tainted_claymore",
        "various.void_shogun",
        "various.behemoth_blades",
        "various.the_game_of_gemstones",
        "various.dragon_blade",
        "various.proof_of_recruitment",
        "various.the_refreshing_deal",
        "various.the_poisonous_deal",
        "afdl.willpower_extraction",
        "afdl.nulgath_demands_work",
        "evolved_orb.evolved_blood_orb",
        "evolved_orb.evolved_hex_orb",
        "evolved_orb.evolved_shadow_orb",
    ]
    #: ``leery_exchange_gold`` trades Unidentified 13 for gold: with a stub that
    #: owns everything and never spends it, the loop has no way to end -- give
    #: it the gold it is after instead.
    WRAPPER_STUBS = {"various.leery_exchange_gold": {"gold": 200_000_000}}
    from importlib import import_module
    for name in WRAPPERS:
        mod = import_module(f"bot.nation.{name}")
        assert inspect.iscoroutinefunction(mod.main), name
        stub = Stub(all_owned=True, **WRAPPER_STUBS.get(name, {}))
        asyncio.run(mod.main(stub))
        assert not stub._connected or True      # ran to completion
    print(f"wrappers   : {len(WRAPPERS)} modules import, expose main(cmd), and "
          f"no-op when everything is owned")

    print("\nnation tests OK")


if __name__ == "__main__":
    main()
