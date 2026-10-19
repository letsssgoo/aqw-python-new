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

    # --- the green/completed table, i.e. what a TurnIn probe answers ---
    # Both ``is_green_quest`` and ``is_completed_before`` are one turn-in
    # attempt: they send ``ccqr`` and read the refusal.  The two flags are not
    # opposites -- "green" means the quest is unlocked and turnable, which is
    # False both when the quest is locked and when it was already completed.
    cmd.quest_to_check = 7716

    def probe(quest_id, msg, success=0):
        cmd.is_green_quest_var = cmd.is_completed_before_var = None
        cmd._message_handler(_server("ccqr", QuestID=str(quest_id),
                                     bSuccess=success, msg=msg))
        return cmd.is_green_quest_var, cmd.is_completed_before_var

    assert probe(7716, "Missing Turn In Item") == (True, False)    # unlocked
    assert probe(7716, "Missing Quest Progress") == (False, False)  # not yet done
    assert probe(7716, "One Time Quest Only") == (False, True)      # done before
    assert probe(7716, "", success=1) == (True, True)               # just turned in
    assert probe(7717, "Missing Turn In Item") == (None, None)      # another quest
    print("probe     : green=unlocked | completed=done | mismatch ignored")

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

    # --- CoreSepulchure.ShadowfallRise: the step table, in source order ---
    from bot.story.sepulchure_saga import core_sepulchure as ss

    assert [s[0] for s in ss.SHADOWFALL_RISE_STEPS] == [
        6539, 6540, 6541, 6542, 6543, 6544, 6544, 6545, 6546, 6547, 6548, 6549,
        6550, 6560, 6561, 6562, 6563, 6564, 6565, 6566, 6567, 6581, 6581, 6582,
        6582, 6583, 6584, 6585, 6586, 6586, 6587, 6588, 6589, 6590, 6592], \
        [s[0] for s in ss.SHADOWFALL_RISE_STEPS]
    # 6544 / 6581 / 6582 / 6586 are the source's map-item-then-kill pairs
    paired = [q for q in {s[0] for s in ss.SHADOWFALL_RISE_STEPS}
              if sum(1 for s in ss.SHADOWFALL_RISE_STEPS if s[0] == q) == 2]
    assert sorted(paired) == [6544, 6581, 6582, 6586], paired
    assert ss.SHADOWFALL_RISE_LAST == 6592 and ss.CORRUPTED_LUMA_QUEST == 6591
    print("shadowfall : 35 steps of quests 6539-6592, 6591 by hand")

    # --- Core13LoC.Kitsune: the by-hand halves, and the last quest -------
    from bot.story.lordsofchaos import core13loc as loc

    assert loc.KITSUNE_LAST == 488
    assert [row[0] for row in loc.JUNKYARD_BY_ID] == [1, 4, 3, 6, 2], \
        loc.JUNKYARD_BY_ID
    assert loc.KAPPA_ITEMS == (("Dried Nori Leaf", 6),
                               ("Sumeshi Bundle", 3),
                               ("Fresh Cucumber", 1)), loc.KAPPA_ITEMS
    assert loc.KAPPA_MAP_ITEM == 92
    print("kitsune    : by-id order 1/4/3/6/2, three kappa drops, map item 92")

    # --- Core13LoC.Lionfang: the whole quest order, source-verified ------
    # The 65 quests in the order they are *executed* (the source guards 2797 and
    # 2798 together, so 2797 runs first even though the guard names 2798).
    import re as _re

    source = pathlib.Path(loc.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def lionfang("):]
    order = []
    for match in _re.finditer(r"(?:kill_quest|map_item_quest)\(\s*cmd,\s*(\d+)"
                              r"|ensure_accept_quest\((\d+)\)", body):
        qid = match.group(1) or match.group(2)
        if qid not in order:
            order.append(qid)
    assert order == [
        "2612", "2613", "2614", "2615", "2616", "2617", "2618", "2619", "2620",
        "2621", "2622", "2623", "2624", "2625", "2626", "2627", "2628", "2629",
        "2630", "2666", "2667", "2668", "2669", "2670", "2671", "2672", "2673",
        "2674", "2675", "2720", "2721", "2722", "2723", "2724", "2725", "2726",
        "2727", "2728", "2729", "2730", "2731", "2732", "2740", "2792", "2793",
        "2794", "2796", "2797", "2798", "2799", "2800", "2801", "2802", "2803",
        "2804", "2805", "2806", "2807", "2808", "2809", "2810", "2811", "2812",
        "2813", "2814"], order
    assert loc.LIONFANG_LAST == 2814
    assert loc.LIONFANG_2806 == ("Lightning Boots", "r1", "Left")
    assert len(loc.LIONFANG_2731) == 3
    print("lionfang   : 65 quests 2612-2814, execution order locked")

    # --- CoreSoW.RuinedCrown: quest order, 8784 before 8783 --------------
    from bot.story.shadows_of_war import core_sow

    body = pathlib.Path(core_sow.__file__).read_text(encoding="utf-8")
    body = body[body.index("async def ruined_crown("):body.index("TIMEKEEP_LAST")]
    # Yang literal di badan fungsi: map/kill quests, plus urutannya.
    literals = [m.group(1) for m in _re.finditer(
        r"(?:kill_quest|map_item_quest)\(\s*cmd,\s*(\d+)", body)]
    assert literals == ["8778", "8780", "8781", "8784", "8783", "8785"], literals
    assert body.index("8784") < body.index("8783"), "8784 harus sebelum 8783"
    # Yang lewat konstanta: blok tangan, gerbang, dan quest merge.
    assert [q for q, _ in core_sow.RUINED_CROWN_HANDS] == [8779, 8782, 8786]
    assert core_sow.RUINED_CROWN_LAST == 8787
    assert core_sow.RUINED_CROWN_MERGE_QUEST == 8788
    print("ruinedcrown: 8778-8788, 8784 before 8783, 8788 after the gate")

    # --- CoreSoW.Timekeep / TimestreamWar: the next two links ------------
    body = pathlib.Path(core_sow.__file__).read_text(encoding="utf-8")
    tk = body[body.index("async def timekeep("):body.index("TIMESTREAM_WAR_LAST")]
    tk_ids = [m.group(1) for m in _re.finditer(
        r"(?:kill_quest|map_item_quest)\(\s*cmd,\s*(\d+)", tk)]
    assert tk_ids == ["8803", "8804", "8805", "8806", "8807", "8808", "8809",
                      "8812"], tk_ids
    assert [q for q, _ in core_sow.TIMEKEEP_HANDS] == [8810, 8811, 8813]
    assert core_sow.TIMEKEEP_LAST == 8813

    tw = body[body.index("async def timestream_war("):body.index("DEADLINES_LAST")]
    tw_ids = [m.group(1) for m in _re.finditer(
        r"(?:kill_quest|map_item_quest)\(\s*cmd,\s*(\d+)", tw)]
    # 8819 ditulis lewat konstanta TIMESTREAM_WAR_LAST, bukan literal
    assert tw_ids == ["8816", "8817", "8818"], tw_ids
    assert core_sow.TIMESTREAM_MEDAL_QUEST == 8814
    assert core_sow.TIMESTREAM_WAR_LAST == 8819
    print("soW chain  : RuinedCrown -> Timekeep -> TimestreamWar, order locked")

    dl = body[body.index("async def dead_lines("):body.index("SHADOWFLAME_LAST")]
    dl_ids = [m.group(1) for m in _re.finditer(
        r"(?:kill_quest|map_item_quest)\(\s*cmd,\s*(\d+)", dl)]
    assert dl_ids == ["8859"], dl_ids        # 8868 lewat konstanta DEADLINES_LAST
    assert [q for q, _, _ in core_sow.DEADLINES_HANDS] == [8860, 8861, 8862, 8863,
                                                          8864, 8865, 8866, 8867]
    assert core_sow.DEADLINES_LAST == 8868
    print("deadlines  : 8859-8868, eight hand blocks with their map items")

    sf = body[body.index("async def shadow_flame("):body.index("MANACRADLE_LAST")]
    sf_ids = [m.group(1) for m in _re.finditer(
        r"(?:kill_quest|map_item_quest)\(\s*cmd,\s*(\d+)", sf)]
    assert sf_ids == ["8956", "8956", "8961", "8962"], sf_ids
    assert [q for q, _, _ in core_sow.SHADOWFLAME_HANDS] == [8957, 8958, 8959,
                                                            8960, 8963, 8964]
    assert core_sow.SHADOWFLAME_LAST == 8965

    mc = body[body.index("async def mana_cradle("):]
    mc_ids = [m.group(1) for m in _re.finditer(
        r"(?:kill_quest|map_item_quest)\(\s*cmd,\s*(\d+)", mc)]
    assert mc_ids == ["9116", "9117", "9118", "9118", "9120", "9121", "9122"], mc_ids
    assert [q for q, _, _ in core_sow.MANACRADLE_HANDS] == [9119, 9123]
    assert core_sow.MANACRADLE_BOSSES == ((9124, "Malgor"), (9125, "The Mainyu"))
    assert core_sow.MANACRADLE_LAST == 9126
    print("SoW done   : ShadowFlame -> ManaCradle, chain closed at 9126")

    # --- CoreAOR.TerminaTemple: the gate depends on the option flags -----
    from bot.story.age_of_ruin import core_aor

    assert core_aor.termina_temple_last(False, False) == 10438
    assert core_aor.termina_temple_last(True, False) == 9351
    assert core_aor.termina_temple_last(False, True) == 9851
    assert [q for q, _, _ in core_aor.TERMINA_TEMPLE_HANDS] == [9213, 9214]
    assert core_aor.TERMINA_TEMPLE_HANDS[0][1] == ((11625, 1), (11626, 1), (11627, 1))
    assert [q for q, _, _ in core_aor.TERMINA_TEMPLE_STEPS] == [9351, 9851]
    assert core_aor.SEAVOICE_GATE == 9348
    aor_body = pathlib.Path(core_aor.__file__).read_text(encoding="utf-8")
    assert "mana_cradle" in aor_body, "lead-in SoW.ManaCradle"
    assert "whitemap" in aor_body, "the source's own map reset for 9213"
    print("AOR        : TerminaTemple, gate 10438/9351/9851 by option")

    av = aor_body[aor_body.index("async def ashray_village("):]
    av_ids = [m.group(1) for m in _re.finditer(
        r"(?:kill_quest|map_item_quest)\(\s*cmd,\s*(\d+)", av)]
    assert av_ids == ["9225", "9227", "9230", "9233"], av_ids
    assert [q for q, _, _ in core_aor.ASHRAY_HANDS] == [9226, 9228, 9229, 9231, 9232]
    assert core_aor.ASHRAY_LAST == 9234
    print("AOR ashray : 9225-9234, five hand blocks with their map items")

    # Dua daftar drop itu variabel biasa di sumber: diport, bukan dilewati.
    assert core_sow.MAINYU_DROPS == ("Mainyu Rune", "Mainyu Tail", "Mainyu Wings")
    assert len(core_sow.MALGOR_DROPS) == 10
    assert core_sow.MALGOR_DROPS[0] == "Shadow DragonMaster"
    assert core_sow.MALGOR_DROPS[-1] == "Shadowflame Vanguard Spear"
    assert "inv_to_bank" in body[body.index("async def mana_cradle("):], \
        "the drops are banked like the source does"

    # --- the reward whitelist QuestProgression does ----------------------
    # `Story.QuestProgression` has three jobs: wait for the quest to be unlocked,
    # skip it when it is already completed, and add its *rewards* as drops so the
    # turn-in's item is picked up.  The last one was missing here.
    from bot.core_story import map_item_quest as _map_item_quest

    bot.loaded_quest_datas.append(Quest.from_payload({
        "QuestID": 4811, "sName": "Rewarded story",
        "oRewards": {"itemsC": {"0": {"ItemID": 4769, "sName": "Tainted Gem"}}},
    }))
    asyncio.run(_map_item_quest(cmd, 4811, "battleon", 1, 1))
    assert "Tainted Gem" in bot.items_drop_whitelist, bot.items_drop_whitelist
    print("rewards    : the story helper whitelists the quest's rewards")

    print("\nquest tests OK")


if __name__ == "__main__":
    main()
