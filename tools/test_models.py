"""Smoke-test the model layer against a realistic payload.

    python tools/test_models.py
"""
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from model.inventory import ItemInventory, ItemType, ScrollType  # noqa: E402
from model import enhancement  # noqa: E402
from model.quest import Quest  # noqa: E402

ITEM = {
    "ItemID": 1965, "sName": "Yara's Sword", "sDesc": "desc", "iRng": 10,
    "iDPS": 110, "iLvl": 65, "iRty": 7, "iCost": 0, "bTemp": 0, "iStk": 1,
    "bPTR": 0, "bUpg": 0, "bCoins": 0, "bStaff": 0, "sFile": "yara",
    "sLink": "", "sES": "Weapon", "sType": "Sword", "EnhPatternID": 10,
    "iQty": 1, "bEquip": 1, "bWear": 1, "CharItemID": 5, "ShopItemID": "",
    "iQtyNow": 1, "EnhID": 70750, "iEnh": 70750, "EnhLvl": 100,
    "EnhRty": 7, "EnhDPS": 100, "EnhRng": 10,
}


class _Item:
    def __init__(self, qty):
        self.qty = qty


class _Player:
    """Minimal stand-in for core.player.Player: id lookups only."""

    def __init__(self, inv=None, temp=None):
        self._inv = inv or {}
        self._temp = temp or {}

    def get_item_inventory_by_id(self, item_id):
        return self._inv.get(str(item_id))

    def get_item_temp_inventory_by_id(self, item_id):
        return self._temp.get(str(item_id))


QUEST = {
    "QuestID": 870, "iSlot": 12, "iValue": 3, "sName": "Contract Exchange",
    "sDesc": "d", "sEndText": "e", "bOnce": "0", "sField": "", "iIndex": 1,
    "bUpg": "0", "iLvl": 0, "iClass": 0, "iReqCP": 0, "FactionID": 0,
    "iReqRep": 0, "iGold": 100, "iExp": 50, "oReqd": {}, "oItems": {},
    "turnin": [{"ItemID": "22332", "iQty": "1"}],
}


def check_quest() -> None:
    """Quest: typed accessors, dict compatibility, no-raise parsing."""
    q = Quest.from_payload(QUEST)
    assert q.quest_id == 870, q.quest_id
    assert q.name == "Contract Exchange", q.name
    assert (q.slot, q.value, q.index) == (12, 3, 1)
    assert not q.is_once and not q.needs_single_turn_in
    assert (q.gold, q.exp) == (100, 50)
    assert q.turn_in_items == [(22332, 1)], q.turn_in_items
    assert q.requirements_met(_Player({"22332": _Item(1)}))
    assert not q.requirements_met(_Player({"22332": _Item(0)}))
    assert not q.requirements_met(_Player())
    assert q.requirements_met(_Player(temp={"22332": _Item(1)}))  # temp counts
    print("quest     :", q.describe())

    # the raw mapping stays intact, so every [..] call site keeps working
    assert q["QuestID"] == 870 and q["turnin"][0]["ItemID"] == "22332"
    assert q.get("turnin") == QUEST["turnin"]

    # once / field both force a single turn-in (the reference bot EnsureCompleteMulti rule)
    assert Quest.from_payload({"QuestID": 1, "bOnce": "1"}).needs_single_turn_in
    assert Quest.from_payload({"QuestID": 2, "sField": "x"}).needs_single_turn_in
    assert not Quest.from_payload({"QuestID": 3, "bOnce": "0"}).needs_single_turn_in

    # sparse / malformed payloads must not raise
    for payload in ({}, None, {"turnin": None},
                    {"turnin": [None, "junk", {}]},
                    {"QuestID": "", "bOnce": "", "iSlot": None}):
        empty = Quest.from_payload(payload)
        assert empty.quest_id == 0
        assert empty.turn_in_items == [], (payload, empty.turn_in_items)
        assert empty.requirements_met(_Player())

    # an entry missing iQty defaults to 1 instead of dropping the requirement
    assert Quest.from_payload({"turnin": [{"ItemID": 5}]}).turn_in_items == [(5, 1)]
    print("quest bad : ok, empty turn_in_items, no raise")


#: Quest 870 as the server actually sends it (trimmed), captured from a live
#: ``getQuests`` reply.  Note ``reqd`` (not ``oReqd``), and that the rewards DO
#: arrive -- under ``reward`` plus ``oRewards.itemsC``.
QUEST_870 = {
    "QuestID": 870, "sName": "Contract Exchange", "sDesc": "d", "sEndText": "e",
    "iLvl": 0, "iExp": 0, "iGold": 0, "iClass": 0, "iReqCP": 0,
    "FactionID": 1, "sFaction": "None", "iReqRep": 0, "iRep": 0,
    "iSlot": -1, "iValue": 0, "bUpg": False, "bOnce": False,
    "turnin": [{"ItemID": 4762, "iQty": 1}, {"ItemID": 15396, "iQty": 1}],
    "reward": [{"ItemID": 4769, "iQty": 8, "iType": 2, "iRate": 100},
               {"ItemID": 4770, "iQty": 4, "iType": 2, "iRate": 100},
               {"ItemID": 4771, "iQty": 15, "iType": 2, "iRate": 100}],
    "reqd": [{"ItemID": 4763, "iQty": 1}],
    "oRewards": {"itemsC": {
        "0": {"ItemID": 4769, "sName": "Tainted Gem", "iQty": 8},
        "1": {"ItemID": 4770, "sName": "Dark Crystal Shard", "iQty": 4},
        "2": {"ItemID": 4771, "sName": "Diamond of Nulgath", "iQty": 15},
    }},
    "oItems": {"4762": {"ItemID": 4762, "sName": "Unidentified 13"},
               "15396": {"ItemID": 15396, "sName": "Blade Master Rune"}},
}


def check_quest_rewards() -> None:
    """Rewards, accept-requirements and the choice flag, from a live payload."""
    q = Quest.from_payload(QUEST_870)
    assert q.turn_in_items == [(4762, 1), (15396, 1)], q.turn_in_items
    assert q.reward_names == ["Tainted Gem", "Dark Crystal Shard",
                              "Diamond of Nulgath"], q.reward_names
    assert q.is_choice_reward, "iType==2 rows must read as a choice quest"
    assert q.accept_requirements == [{"ItemID": 4763, "iQty": 1}]
    assert q.faction_name == "None"
    assert not q.is_once and not q.is_upgrade      # bOnce/bUpg are real bools
    print("quest 870 :", q.describe())

    # ~ the accept-requirement key differs between the live payload (reqd) and
    #   the reference bot's reconstructed shape (oReqd); both must work
    assert Quest.from_payload(
        {"oReqd": [{"ItemID": 1, "iQty": 2}]}).accept_requirements == [
            {"ItemID": 1, "iQty": 2}]

    # no rewards / no container / alternate shape must not raise
    for payload in ({}, {"reward": None}, {"oRewards": None},
                    {"oRewards": {}}, {"oRewards": {"itemsC": None}}):
        empty = Quest.from_payload(payload)
        assert empty.reward_names == [], payload
        assert empty.reward_items == [], payload
        assert not empty.is_choice_reward, payload
    assert Quest.from_payload(
        {"oRewards": [{"sName": "loose"}]}).reward_names == ["loose"]
    print("quest rwd : empty/odd payloads ok")


def main() -> None:
    check_quest()
    check_quest_rewards()
    it = ItemInventory(ITEM)
    print("desc      :", it.describe())
    print("enh obj   :", it.enhancement)
    print("enh name  :", it.enhancement_name, "| slot:", it.enhancement_slot)
    print("has enh   :", it.has_enhancement,
          "| weapon:", it.is_weapon, "| equipped:", it.is_equipped)
    print("lvl/dps   :", it.level, it.dps, "| rty", it.rarity, "| rng", it.range)
    print("turn_in   :", it.turn_in, type(it.turn_in).__name__)
    print("slot      :", it.slot)

    # malformed / sparse payload must not raise
    bad = ItemInventory({"sName": "x", "iLvl": "", "iCost": None,
                         "bEquip": "", "EnhID": "abc"})
    print("bad ok    : lvl", bad.level, "cost", bad.cost,
          "equipped", bad.is_equipped, "enh_id", bad.enh_id,
          "pattern", bad.enh_pattern_id)
    print("no enh    :", ItemInventory({"sName": "y"}).enhancement,
          "| name:", ItemInventory({"sName": "y"}).enhancement_name)

    # registry lookups (forge_enhancement.jsonl is the source of truth)
    enhancement.load()
    print("find(Valiance)   :", [r.describe() for r in enhancement.find("Valiance")])
    print("get(70752)       :", enhancement.get(70752))
    print("get(71542)       :", enhancement.get(71542))
    print("resolve_ids(70752):", enhancement.resolve_ids(70752))
    print("resolve_ids(29)  :", enhancement.resolve_ids(29), "(pattern id)")
    print("resolve_ids('Valiance'):", enhancement.resolve_ids("Valiance"))
    print("resolve_ids('Nope')    :", enhancement.resolve_ids("Nope"))
    print("is_pattern_unique(10)  :", enhancement.is_pattern_unique(10))
    print("is_pattern_unique(29)  :", enhancement.is_pattern_unique(29))
    print("slots_of('Forge')      :", enhancement.slots_of("Forge"))
    print("names('ba')            :", enhancement.names("ba"))

    print("enums      :", ItemType.WEAPON.value, ScrollType.POTION.value)


if __name__ == "__main__":
    main()
