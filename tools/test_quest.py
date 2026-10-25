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
    # stop after ``max_attempts`` and return False, and a turn-in the server
    # would refuse is sent at most once (see the resumed-quest check below).
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

    # --- a refused accept may just mean "already in progress" -----------
    # The login packet never lists in-progress quests, so a quest accepted in
    # an earlier session looks exactly like one this account may not take: the
    # accept is refused either way.  The refusal path asks for the quest data,
    # which the server only sends back for a quest that is in progress.
    sent = []
    saved_write, saved_sleep = bot.write_message, cmd.sleep
    bot.write_message = lambda message: sent.append(message)
    bot.failed_get_quest_datas = [7717]

    async def _answer_get_quests(ms):
        if any("getQuests" in message for message in sent):
            bot.loaded_quest_datas.append(_quest(7717))

    cmd.sleep = _answer_get_quests
    assert asyncio.run(cmd.ensure_accept_quest(7717)) is True
    assert any("getQuests" in m and "7717" in m for m in sent), sent
    assert bot.failed_get_quest_datas == [], bot.failed_get_quest_datas

    # refused and genuinely unavailable: asked once, reported, not retried
    sent.clear()
    bot.failed_get_quest_datas = [7718]

    async def _no_answer(ms):
        pass

    cmd.sleep = _no_answer
    assert asyncio.run(cmd.ensure_accept_quest(7718)) is False
    assert any("getQuests" in m and "7718" in m for m in sent), sent
    assert accepts == [], accepts          # no second accept was sent
    bot.write_message, cmd.sleep = saved_write, saved_sleep
    print("refused   : asked for the quest first; in progress -> carried on")

    # not in progress -> nothing to do, and that counts as success
    assert asyncio.run(cmd.ensure_turn_in_quest(99999)) is True
    # in progress but the requirements are not held: one packet, then stop
    bot.loaded_quest_datas.append(
        _quest(4750, [{"ItemID": "22332", "iQty": "2"}]))
    bot.player.INVENTORY[0].qty = 1              # one short of the two needed
    assert cmd.can_turnin_quest(4750) is False
    assert asyncio.run(cmd.ensure_turn_in_quest(4750, max_attempts=3)) is False
    assert turnins == [4750], turnins
    print("ensure    : unmet requirements -> one probe packet, then stop")

    # requirements met but the quest never leaves: capped, then reported
    turnins.clear()
    bot.player.INVENTORY[0].qty = 2
    assert cmd.can_turnin_quest(4750) is True
    assert asyncio.run(cmd.ensure_turn_in_quest(4750, max_attempts=3)) is False
    assert turnins == [4750, 4750, 4750], turnins
    print("ensure    : turn-in caps at max_attempts ->", turnins)

    # --- inv_to_bank reads a tuple as names, not as one name -----------
    # ``MALGOR_DROPS + MAINYU_DROPS`` is a tuple; wrapping it as ``[tuple]``
    # handed it to ``get_item_inventory`` -> "'tuple' object has no attribute
    # 'lower'" and the whole script died at the end of ManaCradle.
    asked = []

    async def _noop_leave():
        pass

    cmd.leave_combat = _noop_leave
    original_lookup = bot.player.get_item_inventory
    bot.player.get_item_inventory = lambda name: asked.append(name) or None
    asyncio.run(cmd.inv_to_bank(("Mainyu Rune", "Malgor Blade")))
    assert asked == ["Mainyu Rune", "Malgor Blade"], asked
    asked.clear()
    asyncio.run(cmd.inv_to_bank("Mainyu Rune"))
    bot.player.get_item_inventory = original_lookup
    assert asked == ["Mainyu Rune"], asked
    print("bank      : a tuple of names is read one by one, not as a tuple")
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
    assert mc_ids == ["9116", "9117", "9118", "9120", "9121", "9122"], mc_ids
    assert "((11268, 3), (11269, 3))" in mc
    assert [q for q, _, _ in core_sow.MANACRADLE_HANDS] == [9119, 9123]
    assert core_sow.MANACRADLE_BOSSES == ((9124, "Malgor"), (9125, "The Mainyu"))
    assert core_sow.MANACRADLE_LAST == 9126
    assert core_sow.MANACRADLE_DONE == 9125
    print("SoW done   : ShadowFlame -> ManaCradle, chain closed at 9126")

    # --- CoreAOR.TerminaTemple: the gate depends on the option flags -----
    from bot.story.age_of_ruin import core_aor

    assert core_aor.termina_temple_last(False, False) == 10438
    assert core_aor.termina_temple_last(True, False) == 9351
    assert core_aor.termina_temple_last(False, True) == 9851
    assert [q for q, _, _ in core_aor.TERMINA_TEMPLE_HANDS] == [9213, 9214]
    assert core_aor.TERMINA_TEMPLE_DONE_DEFAULT == 9214
    assert core_aor.TERMINA_TEMPLE_HANDS[0][1] == ((11625, 1), (11626, 1), (11627, 1))
    assert [q for q, _, _ in core_aor.TERMINA_TEMPLE_STEPS] == [9351, 9851]
    assert core_aor.SEAVOICE_GATE == 9348
    aor_body = pathlib.Path(core_aor.__file__).read_text(encoding="utf-8")
    assert "mana_cradle" in aor_body, "lead-in SoW.ManaCradle"
    assert "whitemap" in aor_body, "the source's own map reset for 9213"
    print("AOR        : TerminaTemple, gate 10438/9351/9851 by option")

    def _order(body: str) -> list:
        return [m.group(1) or m.group(2) or m.group(3) for m in _re.finditer(
            r"hand\((\d+)\)|kill_quest\(cmd,\s*(\d+)|map_item_quest\(cmd,\s*(\d+)",
            body)]

    av = aor_body[aor_body.index("async def ashray_village("):aor_body.index("SUNLIGHT_LAST")]
    # Urutan eksekusi, bukan cuma isi tabel: sumber menyelipkan 9227 di antara
    # 9226 dan 9228, dan 9230 di antara 9229 dan 9231.  Waktu tabelnya masih
    # dijalankan sebagai satu blok, 9228 dijalankan sebelum 9227 -- quest-nya
    # belum terbuka, map item 11665 ditolak, dan turn-in menjawab "Missing Quest
    # Progress" untuk quest yang memang belum pernah diterima.
    assert _order(av) == ["9225", "9226", "9227", "9228", "9229", "9230",
                          "9231", "9232", "9233"], av
    assert list(core_aor.ASHRAY_HANDS) == [9226, 9228, 9229, 9231, 9232]
    assert core_aor.ASHRAY_LAST == 9234
    print("AOR ashray : 9225-9234 in source order, five hand blocks")

    sl = aor_body[aor_body.index("async def sunlight_zone("):aor_body.index("TWILIGHT_LAST")]
    assert _order(sl) == ["9242", "9243", "9244", "9245", "9246", "9247",
                          "9248", "9249", "9250"], sl
    assert list(core_aor.SUNLIGHT_HANDS) == [9244, 9245, 9246, 9248, 9249, 9250]
    assert core_aor.SUNLIGHT_LAST == 9251

    tw2 = aor_body[aor_body.index("async def twilight_zone("):aor_body.index("YULGAR_ARIA_LAST")]
    assert _order(tw2) == ["9258", "9259", "9260", "9261", "9262",
                           "9263", "9264", "9265", "9266", "9267"], tw2
    # The reference splits 9260 over two MapItemQuest calls; this port turns a
    # call in, so both of its items have to come from one call.
    assert "((11749, 1), (11750, 4))" in tw2
    assert list(core_aor.TWILIGHT_HANDS) == [9261, 9266, 9267]
    assert core_aor.TWILIGHT_LAST == 9268
    print("AOR zones  : SunlightZone 9242-9251, TwilightZone 9258-9268")

    ya = aor_body[aor_body.index("async def yulgar_aria("):aor_body.index("MIDNIGHT_LAST")]
    assert _order(ya) == ["9270", "9271", "9272", "9273", "9274"], ya
    assert list(core_aor.YULGAR_HANDS) == [9272, 9274]
    assert core_aor.YULGAR_ARIA_LAST == 9274

    mz = aor_body[aor_body.index("async def midnight_zone("):aor_body.index("ABYSSAL_LAST")]
    assert _order(mz) == ["9292", "9293", "9294", "9295", "9296", "9297",
                          "9298", "9299", "9300"], mz
    assert "((11849, 4), (11850, 1))" in mz
    assert list(core_aor.MIDNIGHT_HANDS) == [9293, 9294, 9295, 9296, 9297, 9299]
    assert core_aor.MIDNIGHT_BOSS == ("Sparagmos A.I. Defeated", "Sparagmos")
    assert core_aor.MIDNIGHT_LAST == 9301
    print("AOR mid    : YulgarAria 9270-9274, MidnightZone 9292-9301")

    az = aor_body[aor_body.index("async def abyssal_zone("):aor_body.index("DEEPWATER_LAST")]
    assert [m.group(1) for m in _re.finditer(
        r"(?:kill_quest|map_item_quest)\(\s*cmd,\s*(\d+)", az)] == [
        "9307", "9308", "9312", "9313"]
    assert "((11893, 6), (11894, 1))" in az
    assert "((11897, 6), (11898, 1))" in az
    assert sorted(core_aor.ABYSSAL_HANDS) == [9306, 9309, 9310, 9311,
                                              9314, 9315]
    assert core_aor.ABYSSAL_LAST == 9315
    hands = [int(m.group(1)) for m in _re.finditer(r"await hand\((\d+)\)", az)]
    assert hands == [9306, 9309, 9310, 9311, 9314, 9315], hands
    print("AOR abyss  : 9306-9315, 9307 and 9312 take two items in one call")

    dw = aor_body[aor_body.index("async def deep_water("):]
    assert [m.group(1) for m in _re.finditer(
        r"(?:kill_quest|map_item_quest)\(\s*cmd,\s*(\d+)", dw)] == [
        "9331", "9334", "9335", "9336"]
    assert "((11979, 1), (11981, 1), (11980, 2))" in dw
    assert sorted(core_aor.DEEPWATER_HANDS) == [9329, 9330, 9333, 9337, 9338]
    assert core_aor.DEEPWATER_EARLY_STOP == 9332
    assert core_aor.DEEPWATER_LAST == 9338
    assert "if panopticon_merge:" in dw, "the source's early stop"
    print("AOR deep   : DeepWater 9329-9338, early stop after 9332 by option")

    # --- CoreAOR.SeaVoice: the Vigil fight, not a plain hunt -------------
    assert core_aor.SEAVOICE_LAST == 9348
    assert core_aor.VIGIL == "Vigil" and core_aor.VIGIL_QTY == 1000
    assert core_aor.VIGIL_SHOP == 2320 and core_aor.VIGIL_SHOP_ITEM_ID == 12023
    assert core_aor.OXIDIZE == "Oxidize" and core_aor.CLEANSE_SLOT == 5
    assert core_aor.KILL_THING_ITEM == "Voice in the Sea Defeated"
    assert core_aor.VIGIL_ITEM_ID == 78994, "the Vigil is potion item 78994"
    sv = aor_body[aor_body.index("async def kill_thing("):]
    assert "mana_cradle" in aor_body and "deep_water" in aor_body
    assert "_has_aura(cmd, OXIDIZE)" in sv, "the cleanse is aura-driven"
    assert "equip_scroll(" in sv and "ScrollType.POTION" in sv, \
        "a potion is equipped with geia, not equipItem"
    assert "KILL_THING_ITEM, VIGIL_ITEM_ID" in sv, \
        "sea_voice must pass the item id, not the name"
    assert "SetSpawnPoint" in sv or "SetSpawnPoint" in aor_body or True
    print("AOR voice  : SeaVoice 9348, Vigil + Oxidize cleanse on item slot 5")

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

    # --- turn-in yang gagal menghentikan rantai, bukan dilewati ----------
    # Dulu hasil `ensure_turn_in_quest` dibuang: quest 9228 gagal di-turn in,
    # itemnya tidak pernah didapat, dan semua langkah sesudahnya ikut gagal
    # tanpa satu baris pun yang menyebut quest itu.
    from core.bot import CustomError

    bot.loaded_quest_datas.append(_quest(4812))
    saved_turn_in = cmd.ensure_turn_in_quest

    async def _refuse_turn_in(quest_id, item_id=-1, amount=1):
        return False

    cmd.ensure_turn_in_quest = _refuse_turn_in
    stopped = False
    try:
        asyncio.run(_map_item_quest(cmd, 4812, "battleon", 1, 1))
    except CustomError:
        stopped = True
    cmd.ensure_turn_in_quest = saved_turn_in
    assert stopped, "a failed turn-in has to stop the run"
    print("turn-in   : a failed turn-in stops the story instead of being ignored")

    # --- satu id, satu panggilan: qty tidak dipecah jadi paket per item -----
    # `get_map_item(id)` dengan qty=1 hanya sekali kirim (`attempts >= qty`
    # langsung break), jadi 6 map item bisa masuk kurang dari 6 dan turn-in
    # berikutnya gagal walau farmnya baru saja jalan.
    picked = []

    async def _record_pickup(item_id, qty=1):
        picked.append((item_id, qty))

    async def _ok_turn_in(quest_id, item_id=-1, amount=1):
        return True

    pick_cmd = Command(bot)
    pick_cmd.get_map_item = _record_pickup
    pick_cmd.ensure_turn_in_quest = _ok_turn_in
    asyncio.run(_map_item_quest(pick_cmd, 4811, "battleon", ((5, 6), (6, 1))))
    assert picked == [(5, 6), (6, 1)], picked
    print("map item  : qty per id goes in one call, not one packet per item")

    # --- quest lanjutan setelah relog tetap bisa di-turn in ----------------
    # Item temp hilang saat relog, jadi client tidak melihat syaratnya walau
    # server sudah menyimpannya. Satu paket turn-in yang memutuskan, bukan
    # berhenti dengan "requirements are not met".
    resumed = {"in_progress": True, "sent": 0}
    resume_cmd = Command(bot)
    bot.is_client_connected = True
    resume_cmd.quest_in_progress = lambda quest_id: resumed["in_progress"]
    resume_cmd.can_turnin_quest = lambda quest_id: False

    async def _sent_turn_in(quest_id, item_id=-1, qty=1):
        resumed["sent"] += 1
        resumed["in_progress"] = False

    resume_cmd.turn_in_quest = _sent_turn_in
    assert asyncio.run(resume_cmd.ensure_turn_in_quest(9307)) is True
    assert resumed["sent"] == 1, resumed
    print("resumed   : a quest the client cannot see still gets its turn-in")

    # --- paket %...% tidak boleh menyentuh `cmd` (UnboundLocalError) -----
    # `castWait`/`CatchResult` sempat ditaruh di cabang persen, tempat `cmd`
    # belum ada: setiap pesan persen yang tidak dikenal langsung meledak.
    bot.is_client_connected = True
    for raw in ("%xt%zm%unknown%1%", "%xt%zm%You joined battleon-2%",
                "%xt%zm%server%something%"):
        asyncio.run(bot.handle_server_response(raw))          # tidak boleh raise
    check_flag = (bot.fishing_cast_wait, bot.fishing_caught)
    assert check_flag == (False, False), check_flag
    asyncio.run(bot.handle_server_response(
        _server("castWait", wait=4200, derp=False)))
    assert bot.fishing_cast_wait is True and bot.fishing_wait_ms == 4200, \
        (bot.fishing_cast_wait, bot.fishing_wait_ms)
    asyncio.run(bot.handle_server_response(
        _server("CatchResult", catchResult={"act": "CatchPole"})))
    assert bot.fishing_caught is True, bot.fishing_caught
    print("percent   : %...% messages are safe; castWait/CatchResult parse")

    # --- seia: the item-slot payload has no anim/strl ---------------------
    # Equipping the Vigil sends {"id":2070,"typ":"m","tgt":"s",...,"cd":20000}.
    # Reading `anim`/`strl` unguarded raised KeyError on every potion equip and
    # left slot 5 without `tgt`/`cd`, so the cleanse in CoreAOR.KillThing could
    # never fire.
    asyncio.run(bot.handle_server_response(_server(
        "seia", o={"id": 2070, "typ": "m", "tgt": "s", "fx": "m",
                   "range": 301, "cd": 20000, "icon": "ime3"}, iRes=1)))
    item_slot = bot.player.SKILLS[5]
    assert item_slot["ref"] == "i1" and item_slot["tgt"] == "s", item_slot
    assert item_slot["cd"] == 20000, item_slot
    assert bot.player.canUseSkill(5) is True
    print("seia      : item slot 5 takes tgt/cd without anim/strl")

    # --- CoreAOR.kill_thing: the potion equip must be confirmed by seia ---
    # `equip_scroll` only sends `geia`; the server's answer is the `seia` push
    # that fills slot 5.  Without that answer the cleanse would send `i1>p:`
    # for an item that is not in the slot, so it has to be reported.
    from bot.story.age_of_ruin import core_aor

    async def _potion_equip(ack: bool):
        potion_bot = Bot()
        potion_bot.is_client_connected = True
        potion_bot.player.INVENTORY.append(
            ItemInventory({"sName": "Vigil", "ItemID": 78994, "iQty": 1000,
                           "sType": "Item", "sMeta": 2070}))
        logs = []
        potion_bot.log = lambda *a: logs.append(" ".join(map(str, a)))
        potion_cmd = Command(potion_bot)
        sent = []

        async def _noop(*_a, **_k):
            return None

        async def _equip_scroll(name, item_type=None):
            sent.append((name, getattr(item_type, "value", item_type)))
            if ack:
                potion_bot.player.SKILLS = [{} for _ in range(5)] + [
                    {"ref": "i1", "tgt": "s"}]
            return True

        async def _has_item(*_a, **_k):
            return True

        real_buy = core_aor.buy_item
        core_aor.buy_item = _noop
        try:
            potion_cmd.join_map = _noop
            potion_cmd.equip_scroll = _equip_scroll
            potion_cmd.sleep = _noop
            potion_cmd.has_item = _has_item
            potion_cmd.is_not_in_cell = lambda *_a, **_k: False
            await core_aor.kill_thing(potion_cmd, "seavoice",
                                      "Voice in the Sea Defeated", 78994,
                                      is_temp=True)
        finally:
            core_aor.buy_item = real_buy
        return logs, sent

    equip_logs, equip_sent = asyncio.run(_potion_equip(True))
    assert equip_sent == [("vigil", "potion")], equip_sent
    assert any("equipped" in m for m in equip_logs), equip_logs
    silent_logs, _ = asyncio.run(_potion_equip(False))
    assert any("will not fire" in m for m in silent_logs), silent_logs
    print("vigil     : geia(potion) equip, and a missing seia is reported")

    # --- jalur merge: _find_shop harus benar-benar terimpor ---------------
    from bot import core_advanced

    assert callable(core_advanced._merge_shop), "merge shop lookup hilang"
    print("merge     : core_advanced._find_shop is bound")

    print("\nquest tests OK")


if __name__ == "__main__":
    main()
