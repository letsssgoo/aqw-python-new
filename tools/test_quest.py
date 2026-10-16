"""Quest tracking: id normalisation and in-progress lookups.

    python tools/test_quest.py

Quest ids arrive as **strings** off the wire (``{"QuestID": "870"}``) and as
**ints** from scripts.  The old lookup fell back on
``str(quest_id) in str(loaded_quest_ids)`` to paper over the mismatch -- and
that substring test equated ``443`` with ``4432``, so a check for one quest
could pass because a *different* quest was in progress.  Every lookup must now
be an exact int match, which is what this file guards.
"""
import asyncio
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.bot import Bot  # noqa: E402
from core.command import Command  # noqa: E402
from model import Quest, normalize_quest_id  # noqa: E402
from model.inventory import ItemInventory  # noqa: E402


def _server(cmd: str, **fields) -> str:
    """Wrap a payload the way the server frames it: ``{"t":"xt","b":{"o":...}}``."""
    return json.dumps({"t": "xt", "b": {"r": -1, "o": dict(cmd=cmd, **fields)}})


def _quest(quest_id, turnin=None) -> Quest:
    return Quest.from_payload({
        "QuestID": str(quest_id), "iSlot": 12, "iValue": 3,
        "sName": f"Quest {quest_id}", "bOnce": "0", "sField": "",
        "turnin": turnin or [],
    })


def main() -> None:
    # --- normalize_quest_id ------------------------------------------
    assert normalize_quest_id("870") == 870          # wire string
    assert normalize_quest_id(870) == 870            # script int
    assert normalize_quest_id(" 870 ") == 870        # padded
    assert normalize_quest_id(None) == 0
    assert normalize_quest_id("") == 0
    assert normalize_quest_id("abc") == 0
    print("normalize : '870' ->", normalize_quest_id("870"),
          "| None ->", normalize_quest_id(None))

    bot = Bot()
    cmd = Command(bot)

    # --- exact-match lookup, string and int agree --------------------
    bot.loaded_quest_datas.append(_quest(4432, [{"ItemID": "22332", "iQty": "2"}]))
    assert bot.get_loaded_quest("4432") is bot.get_loaded_quest(4432)
    assert bot.get_loaded_quest(4432) is not None
    assert bot.loaded_quest_ids() == [4432]
    print("lookup    : 4432 via '4432' and 4432 -> same object")

    # --- the regression: 443 must NOT match 4432 ---------------------
    assert bot.quest_not_in_progress(443), "443 matched 4432 (substring bug)"
    assert not bot.quest_not_in_progress(4432)
    assert cmd.quest_in_progress(4432) and not cmd.quest_in_progress(443)
    print("regression: 443 does not match 4432")

    # --- junk ids match nothing -------------------------------------
    for junk in (0, None, "", "abc"):
        assert bot.get_loaded_quest(junk) is None, junk
        assert bot.quest_not_in_progress(junk), junk
    print("junk ids  : 0/None/''/'abc' -> not in progress")

    # --- can_turn_in_quest reads the model ---------------------------
    assert not bot.can_turn_in_quest(4432)           # nothing in inventory
    bot.player.INVENTORY.append(
        ItemInventory({"sName": "Blood Gem of the Archfiend",
                       "ItemID": 22332, "iQty": 2}))
    assert bot.can_turn_in_quest("4432")             # string id again
    bot.player.INVENTORY[0].qty = 1                  # one short of the 2 needed
    assert not bot.can_turn_in_quest(4432)
    print("turn-in   : 2 needed, 2 held -> True; 1 held -> False")

    # --- ccqr handler: exact removal, and near-miss must not remove ---
    asyncio.run(bot.handle_server_response(
        _server("ccqr", QuestID="443", bSuccess=1, sName="near miss")))
    assert bot.get_loaded_quest(4432) is not None, "ccqr 443 removed 4432"
    asyncio.run(bot.handle_server_response(
        _server("ccqr", QuestID="4432", bSuccess=1, sName="exact")))
    assert bot.get_loaded_quest(4432) is None, "ccqr 4432 did not remove it"
    print("ccqr      : '443' kept it, '4432' removed it")

    # --- acceptQuest handler: a wire string lands as an int -----------
    asyncio.run(bot.handle_server_response(
        _server("acceptQuest", QuestID="9999", bSuccess=0)))
    assert bot.failed_get_quest_datas == [9999], bot.failed_get_quest_datas
    asyncio.run(bot.handle_server_response(
        _server("acceptQuest", QuestID="9999", bSuccess=0)))
    assert bot.failed_get_quest_datas == [9999], "duplicate recorded"
    assert 9999 in cmd.bot.failed_get_quest_datas  # int lookup now matches
    print("failed    : wire '9999' stored as int, no duplicate")

    # --- quest rewards come from the payload, not from a cache -------
    bot.loaded_quest_datas.append(Quest.from_payload({
        "QuestID": 871, "sName": "Rewarded", "oRewards": {"itemsC": {
            "0": {"ItemID": 4769, "sName": "Tainted Gem"},
            "1": {"ItemID": 4770, "sName": "Dark Crystal Shard"}}},
    }))
    assert cmd.get_quest_rewards(871) == ["Tainted Gem", "Dark Crystal Shard"]
    assert cmd.get_quest_rewards(99999) == []
    added = cmd.add_quest_rewards(871)
    assert added == ["Tainted Gem", "Dark Crystal Shard"]
    assert set(added) <= set(bot.items_drop_whitelist)
    print("rewards   : read oRewards, whitelisted the names")

    # --- registration list round-trips through str/int ---------------
    # ``register_quest`` is @check_alive, so it no-ops while disconnected;
    # connect first, and keep 870 already in progress so ensure_accept_quest
    # has nothing to loop on.
    bot.loaded_quest_datas.append(_quest(870))
    bot.is_client_connected = True
    asyncio.run(cmd.register_quest("870"))
    assert bot.registered_auto_quest_ids == [870]
    cmd.unregister_quest("870")                      # str removes the int
    assert bot.registered_auto_quest_ids == []
    bot.is_client_connected = False
    print("register  : '870' registered then unregistered as int")

    # --- ensure_* give up instead of hanging ------------------------
    # Both loops used to be unbounded: a quest the server never accepts (or
    # never lets you turn in) hung the bot with no message at all.  They now
    # stop after ``max_attempts`` and return False, and they must not send a
    # turn-in the server would only refuse again.
    bot.is_client_connected = True
    bot.player.ISDEAD = False
    accepts, turnins = [], []

    async def _noop_accept(quest_id):
        accepts.append(quest_id)

    async def _noop_turn_in(quest_id, item_id=-1, amount=1):
        turnins.append(quest_id)

    async def _noop_sleep(ms):
        pass                        # keep the 1 s pacing sleep out of the test

    cmd.accept_quest = _noop_accept
    cmd.turn_in_quest = _noop_turn_in
    cmd.sleep = _noop_sleep

    # accepted already (870 is in progress from above): nothing sent
    assert asyncio.run(cmd.ensure_accept_quest(870)) is True
    assert accepts == [], accepts
    # never accepted: exactly max_attempts tries, then a reported False
    assert asyncio.run(cmd.ensure_accept_quest(5150, max_attempts=3)) is False
    assert accepts == [5150, 5150, 5150], accepts
    # the server already refused it: stop at once, without retrying
    accepts.clear()
    assert asyncio.run(cmd.ensure_accept_quest(9999)) is False
    assert accepts == [], accepts
    print("ensure    : accept caps at max_attempts, refused id stops at once")

    # not in progress -> nothing to do, and that counts as success
    assert asyncio.run(cmd.ensure_turn_in_quest(99999)) is True
    # in progress but the requirements are not held: refuse to send anything
    bot.loaded_quest_datas.append(
        _quest(4750, [{"ItemID": "22332", "iQty": "2"}]))
    bot.player.INVENTORY[0].qty = 1              # one short of the two needed
    assert cmd.can_turnin_quest(4750) is False
    assert asyncio.run(cmd.ensure_turn_in_quest(4750, max_attempts=3)) is False
    assert turnins == [], turnins
    print("ensure    : turn-in with unmet requirements sends nothing")

    # requirements met but the quest never leaves: capped, then reported
    bot.player.INVENTORY[0].qty = 2
    assert cmd.can_turnin_quest(4750) is True
    assert asyncio.run(cmd.ensure_turn_in_quest(4750, max_attempts=3)) is False
    assert turnins == [4750, 4750, 4750], turnins
    print("ensure    : turn-in caps at max_attempts ->", turnins)
    bot.is_client_connected = False

    # --- quest requirements: names from oItems, temp from the temp bag ---
    # the join CoreStory's kill quest drives its per-monster kills from
    from bot.core_story import pending_requirements

    bot.loaded_quest_datas.append(Quest.from_payload({
        "QuestID": 9526, "sName": "Where the Heart is",
        "turnin": [{"ItemID": "11", "iQty": "2"}, {"ItemID": "22", "iQty": "1"}],
        "oItems": [{"ItemID": "11", "sName": "Lightguard Paladin"},
                   {"ItemID": "22", "sName": "Paladin Ascendant"}],
    }))
    heart = cmd.get_loaded_quest(9526)
    assert pending_requirements(cmd, heart) == [
        ("Lightguard Paladin", 2, False),
        ("Paladin Ascendant", 1, False)], pending_requirements(cmd, heart)
    bot.player.INVENTORY.append(
        ItemInventory({"sName": "Lightguard Paladin", "ItemID": 11, "iQty": 2}))
    assert pending_requirements(cmd, heart) == [("Paladin Ascendant", 1, False)]
    bot.player.TEMPINVENTORY.append(
        ItemInventory({"sName": "Paladin Ascendant", "ItemID": 22, "iQty": 1,
                       "bTemp": 1}))
    assert pending_requirements(cmd, heart) == []
    print("requirements: ids joined to names, held ones dropped, temp detected")

    # --- Core13LoC.Escherion: the step table, in the source's order -----
    from bot.story.lordsofchaos import core13loc

    assert len(core13loc.ESCHERION_STEPS) == 24, len(core13loc.ESCHERION_STEPS)
    assert core13loc.ESCHERION_STEPS[0][:2] == (245, "mobius")
    assert core13loc.ESCHERION_STEPS[-1][:2] == (271, "hydra")
    assert [s[0] for s in core13loc.ESCHERION_STEPS] == [
        245, 246, 247, 260, 248, 249, 250, 251, 252, 255, 256, 257, 261, 258,
        262, 259, 263, 266, 267, 264, 268, 269, 270, 271], \
        [s[0] for s in core13loc.ESCHERION_STEPS]
    assert core13loc.ESCHERION_LAST == 272
    print("escherion  : 24 steps of quests 245-271, then 272 by hand")

    print("\nquest tests OK")


if __name__ == "__main__":
    main()
