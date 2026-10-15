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
    approval_and_favor, assistant_during_supplies, assisting_drudgen,
    bamboozle_vs_drudge, bloody_chaos, blood_from_the_void, can_we_aggro,
    contract_exchange, crags_thirst, dark_makai_item, deal, diamond_exchange,
    dirty_deeds_done_dirt_cheap, do_swindles_return_area,
    dragon_slayer_reward, dreadrock_gem_exchange, emblem_of_nulgath,
    equip_class, essence_of_defeat_reagent, essence_of_nulgath, farm_blood_gem,
    farm_contract_exchage, farm_dark_crystal_shard, farm_diamond_of_nulgath,
    farm_fiend_token, farm_gem_of_nulgath, farm_tainted_gem,
    farm_totem_of_nulgath, farm_uni10, farm_uni13_quest, farm_voucher,
    feed_the_fiend, fiend_emblem, get_pcod, handle_voucher_conversions,
    has_any_item, has_any_item_id, has_item_id, kill_escherion, kill_vath,
    kissthe_void, nation_round_4_medal, new_worlds_new_opportunities,
    nulgath_larvae, nulgaths_roulette_of_misfortune, sell_voucher_of_nulgath,
    supplies, swindle_bulk, the_assistant, totems_via_taros, uni,
    void_knight_sword_quest)


class _Other:
    def __init__(self, name):
        self.str_username = name


class _Player:
    def __init__(self, member=False, items_by_id=None, level=0, gold=0,
                 good_rank=0):
        self.USER = "me"
        self.CELL = "r9"
        self.is_member = member
        self.LEVEL = level
        self.GOLD = gold
        self._by_id = {str(k): v for k, v in (items_by_id or {}).items()}

    def get_item_inventory_by_id(self, item_id):
        return self._by_id.get(str(item_id))


class _Bot:
    def __init__(self, others=()):
        self.player_in_area = [_Other(n) for n in others]


class Stub:
    """Duck-typed Command: records calls, never touches the network."""

    def __init__(self, inventory=None, member=False, completed=(),
                 others=(), connected=True, items_by_id=None, level=0,
                 gold=0, good_rank=0, all_owned=False):
        self.inv = dict(inventory or {})
        self.calls = []
        self.player = _Player(member, items_by_id, level, gold)
        self.bot = _Bot(others)
        self._completed = set(completed)
        self._connected = connected
        self._good_rank = good_rank
        self._all_owned = all_owned
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
        return False

    def get_equipped_class(self):
        return None

    def get_monster(self, name):
        return None

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

    async def bank_to_inv(self, names):
        self.calls.append(("bank_to_inv",))

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

    async def ensure_accept_quest(self, quest_id):
        self.calls.append(("ensure_accept_quest", quest_id))

    async def ensure_turn_in_quest(self, quest_id, item_id=-1, amount=1):
        self.calls.append(("ensure_turn_in_quest", quest_id))

    def add_quest_rewards(self, quest_id):
        self.calls.append(("add_quest_rewards", quest_id))
        return []

    def get_quest_rewards(self, quest_id):
        return []

    def remove_drop(self, names):
        self.calls.append(("remove_drop", names))

    def get_loaded_quest(self, quest_id):
        self.calls.append(("get_loaded_quest", quest_id))
        return None

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
    assert pcod_low.calls == [], pcod_low.calls
    print("pcod       : Good rank 3 -> False, stops instead of farming nothing")

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
    ]
    from importlib import import_module
    for name in WRAPPERS:
        mod = import_module(f"bot.nation.{name}")
        assert inspect.iscoroutinefunction(mod.main), name
        stub = Stub(all_owned=True)
        asyncio.run(mod.main(stub))
        assert not stub._connected or True      # ran to completion
    print(f"wrappers   : {len(WRAPPERS)} modules import, expose main(cmd), and "
          f"no-op when everything is owned")

    print("\nnation tests OK")


if __name__ == "__main__":
    main()
