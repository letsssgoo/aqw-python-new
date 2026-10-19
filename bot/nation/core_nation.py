"""Shared Nation routines -- the port of ``Nation/CoreNation.cs``.

Every file under ``Nation/`` is a thin wrapper around a method in that class,
so this module is where the actual work lives.  The reference bot's ``FarmX()`` methods are
"try whichever method you have the pet for" chains, which makes them one large
mutually-recursive cluster (``Deal`` -> ``Supplies`` -> ``FarmSingleSupply`` ->
``BambloozevsDrudgen`` -> ``Deal``), so this file is filled in dependency order
rather than all at once.

**Ported so far** (each stands alone, or needs only the helpers above it):

========================  ====================================================
``uni``                   ``Unidentified {n}``
``equip_class``           farm / solo class, from ``Bot(...)``
``can_we_aggro``          aggro while someone else shares the cell
``join_swf``              enter a map whose retired SWF is client-loaded
``all_owned`` / ``first_missing``  bank-aware inventory checks
``kill_escherion``        the Escherion fight, staff-aware
``kill_vath``             the Stalagbite / Vath fight
``dark_makai_item``       Dark Makai drops, one of two maps at random
``approval_and_favor``    Nulgath's Approval + Archfiend's Favor
``blood_from_the_void``   Blood From the Void (needs /tercesinvasion story)
``fiend_emblem``          Fiend Emblem, quest 7890
``new_worlds_new_opportunities``  rewards of quest 6183 / 6697, from the pet
``void_knight_sword_quest``       rewards of quest 5662 / 5659
``crags_thirst``          Diamonds via quest 600
``bloody_chaos``          Blood Gems via quest 7816 (+2857 with the relic)
``essence_of_defeat_reagent``     Dark Crystal Shards via quest 570
``dirty_deeds_done_dirt_cheap``   Unidentified 10 via quest 7818
``supplies`` and its helpers    the whole quest-2857 route
``bamboozle_vs_drudge``         the pet route: Tainted Elementals in /evilmarsh
``farm_contract_exchage`` / ``contract_exchange`` / ``diamond_exchange``
``dragon_slayer_reward`` / ``deal`` / ``get_pcod``
``farm_uni10`` / ``farm_uni13_quest`` / ``farm_dark_crystal_shard``
``farm_diamond_of_nulgath`` / ``farm_gem_of_nulgath`` / ``farm_blood_gem``
``farm_tainted_gem`` / ``farm_totem_of_nulgath`` / ``farm_voucher``
``farm_fiend_token`` / ``assisting_drudgen`` / ``feed_the_fiend``
``essence_of_nulgath`` / ``totems_via_taros`` / ``kissthe_void``
``nation_round_4_medal`` / ``emblem_of_nulgath``
``swindle_return`` / ``swindle_bulk`` / ``dreadrock_gem_exchange``
``nulgath_larvae`` / ``nulgaths_roulette_of_misfortune``
``the_assistant``       quest 2859, fed with War-Torn Memorabilia
========================  ====================================================

**Not ported yet:**

* The remaining Nation-root script methods, which have not been read yet.
* The Forge chain's callers: ``HireNulgathLarvae``, and the merge-shop and
  "Various" wrappers that are not written yet.
* The rest of CoreFarms: ``Experience``/``IcestormArena`` and the four gold
  methods are in ``bot.core_farms``, along with the faction methods a Nation
  script calls (Good, Vampire).  The other ~60 faction methods -- and the
  boost-item support ``ToggleBoost`` needs -- are not ported;
  ``farm_faction`` names what it cannot do.

The member Forge chain (quests 4917-4924) is ported: ``dwobo_coin``,
``gem_stone_receipt_of_nulgath``, ``gem_stones_of_nulgath``, the four
``forge_*`` routines, ``carve_uni_gem_stone`` and ``leery_exchange_gold``.

Its guards and stop conditions are the reference's own, verbatim: the four loose
``&&`` guards, and the two reward names that name no item (``"Dark Crystal
Shards"``, ``"Diamonds for Nulgath"``), so those two loops run until the bot is
stopped -- exactly as the reference does.  The one thing not copied is a loop
that spins on a quest the server refuses: that reports once and stops.

Folder layout mirrors the reference tree: the ``Nation/`` root wrappers and
this file sit in ``bot/nation/``, and each subfolder that exists so far --
``materials/`` -- matches its sibling.  Later batches land in ``various/``,
``merge_shops/``, ``vhl/``, ``afdl/``, ``evolved_orb/`` and
``oblivion_blade/`` as those are ported, rather than being flattened here.

Porting notes that apply throughout:

* The reference bot's ``Bot.Sleep`` / ``Bot.Wait.ForPickup`` / ``ForMapLoad`` become the
  ``hunt_item`` loop guards and ``cmd.sleep`` -- this engine polls state.
* ``Core.EquipClass(ClassType.Farm|Solo)`` maps to the class passed to
  ``Bot(farmClass=..., soloClass=...)``.
* Quest requirement tracking is temp-item based, so quest farms pass
  ``is_temp=True`` where the reference bot left ``isTemp`` at its default.
* Reward names come from ``Command.get_quest_rewards`` / ``add_quest_rewards``,
  which read the live ``getQuests`` payload.  Unlike the reference bot's client-side quest
  cache that payload only exists **after the quest is accepted**, so the order
  here is register/accept first, then read the rewards.
"""
from __future__ import annotations

import random
from typing import List, Optional, Sequence, Tuple

from bot import core_bots as _core_bots
from bot.core_bots import buy_item
from bot.core_farms import (farm_experience, farm_faction, farm_gold)
from core.command import Command
from model.quest import Quest
from templates.hunt import DEFAULT_SKILL_LIST, hunt_item, kill_quest

#: The principal Nulgath drops, straight from the reference bot's ``CoreNation.bagDrops``.
#: Fed to ``cmd.add_drop`` so the auto-pickup picks them up while farming.
BAG_DROPS: Tuple[str, ...] = (
    "Blood Gem of the Archfiend",
    "Dark Crystal Shard",
    "Diamond of Nulgath",
    "Gem of Nulgath",
    "Totem of Nulgath",
    "Tainted Gem",
    "Unidentified 10",
    "Unidentified 13",
    "Voucher of Nulgath",
    "Voucher of Nulgath (non-mem)",
    # extras
    "Unidentified 24",
    "Essence of Nulgath",
    "Unidentified 25",
    "Fiend Token",
    "Emblem of Nulgath",
    "Receipt of Swindle",
    "Bone Dust",
    "Nulgath's Approval",
    "Archfiend's Favor",
    "Unidentified 34",
)

#: The two pets that make ``new_worlds_new_opportunities`` possible.
NWNO_PETS: Tuple[str, ...] = ("Nulgath's Birthday Gift",
                              "Bounty Hunter's Drone Pet")

#: The two Sword of the Void Knight variants the quest 5662/5659 choice hangs on.
VOID_KNIGHT_SWORDS: Tuple[int, ...] = (38275, 38254)

#: The Crag & Bamboozle pet, which gates several of the cheapest farm methods.
#: The reference's literal carries an HTML escape (``"Crag &amp; Bamboozle"``),
#: which no item is named; that has since been fixed to the plain name, so the
#: Crag checks compare against the real item and the pet routes run.
CRAG_PET = "Crag & Bamboozle"
CRAG_PET = "Crag & Bamboozle"

#: Extra drops handed out while Bloody Chaos is running with the relic branch.
BLOODY_CHAOS_SUPPLIES: Tuple[str, ...] = (
    "Tainted Gem",
    "Dark Crystal Shard",
    "Diamond of Nulgath",
    "Voucher of Nulgath",
    "Voucher of Nulgath (non-mem)",
    "Unidentified 10",
    "Unidentified 13",
    "Gem of Nulgath",
    "Relic of Chaos",
)

#: Drops from the bosses that used to gate access to Tercessuinotlim.
TERCESS_BAGS: Tuple[str, ...] = ("Bone Dust",)

#: Monster map ids used by the two per-map boss helpers below.  AQW mints a
#: fresh ``MonMapID`` per zone spawn, but these two fights are single-spawn
#: cells, so the ids are stable there.
ESCHERION_STAFF = "id.2"
ESCHERION_BOSS = "id.3"
VATH_BOSS = "id.7"
STALAGBITE = "id.8"

#: The ten drops the Supplies route cares about -- ``bagDrops`` minus the
#: eleven extras that follow them in the C# array.
BAG_DROPS_PRINCIPAL: Tuple[str, ...] = BAG_DROPS[:10]

#: Rewards handed out by the Supplies quest.
SUPPLIES_REWARDS: Tuple[str, ...] = (
    "Tainted Gem",
    "Dark Crystal Shard",
    "Diamond of Nulgath",
    "Voucher of Nulgath",
    "Voucher of Nulgath (non-mem)",
    "Gem of Nulgath",
    "Unidentified 10",
    "Essence of Nulgath",
    "Receipt of Swindle",
)

#: The two pets that stand in for the OBoN (member-only).
OBO_PETS: Tuple[int, ...] = (4809, 5373)

#: Quest 7551 offers one reward that must never be picked here.
SWINDLES_EXCLUDED_REWARD = 57446

#: Voucher quest whose two rewards (totem / diamond) are swapped once maxed.
VOUCHER_CONVERSION_QUEST = 4778
TOTEM_OF_NULGATH = 5357
GEM_OF_NULGATH = 6136

#: The four rewards quest 870 (Contract Exchange) can hand out, by name.  The
#: C# switches on an enum to pick between them; a name is enough here, which
#: collapses that switch to one call.
CONTRACT_REWARDS: Tuple[str, ...] = (
    "Tainted Gem",
    "Dark Crystal Shard",
    "Gem of Nulgath",
    "Blood Gem of the Archfiend",
)

#: Quest ids and monsters for the Dragon Slayer chain (quests 165-169).
DRAGON_SLAYER_QUESTS: Tuple[Tuple[int, str, bool], ...] = (
    (165, "Water Draconian", False),
    (166, "Bronze Draconian", False),
    (167, "Golden Draconian", False),
    (168, "Red Dragon", True),
    (169, "Water Draconian", False),
)

#: The four Shadow Blast Arena medals: ``(medal, quest, ((monster, item, qty), ...))``.
NATION_MEDALS: Tuple[Tuple[str, int, Tuple[Tuple[str, str, int], ...]], ...] = (
    ("Nation Round 1 Medal", 4744,
     (("Legion AirStrike", "Legion Rookie Defeated", 5),
      ("Shadowrise Guard", "Shadowscythe Rookie Defeated", 5))),
    ("Nation Round 2 Medal", 4745,
     (("Legion Fenrir", "Legion Veteran Defeated", 7),
      ("Doombringer", "Shadowscythe Veteran Defeated", 7))),
    ("Nation Round 3 Medal", 4746,
     (("Legion Cannon", "Legion Elite Defeated", 10),
      ("Draconic Doomknight", "Shadowscythe Elite Defeated", 10))),
    ("Nation Round 4 Medal", 4747,
     (("Grimlord Boss", "Grimlord Vanquished", 1),)),
)

#: What quest 7551 eats, plus the extras it pays out.
RECEIPT_DROPS: Tuple[str, ...] = (
    "Unidentified 1", "Unidentified 6", "Unidentified 9",
    "Unidentified 16", "Unidentified 20", "Receipt of Swindle",
    "Dark Crystal Shard", "Diamond of Nulgath", "Gem of Nulgath",
    "Blood Gem of the Archfiend",
)

#: The Larvae / Roulette quest and the two energy items it runs on.
LARVAE_QUEST = 2566
MANA_ENERGY = "Mana Energy for Nulgath"
CHARGED_MANA_ENERGY = "Charged Mana Energy for Nulgath"

#: The two rewards quest 4778 can hand out, by lower-cased name.
VOUCHER_ITEM_REWARDS = {
    "totem of nulgath": TOTEM_OF_NULGATH,
    "gem of nulgath": GEM_OF_NULGATH,
}

#: What Assisting Crag & Bamboozle pays out, and therefore what to pick up.
ACAB_DROPS: Tuple[str, ...] = (
    "Nulgath Larvae", "Sparrow's Blood", "Sword of Nulgath", "Gem of Nulgath",
    "Tainted Gem", "Dark Crystal Shard", "Diamond of Nulgath",
    "Totem of Nulgath", "Blood Gem of the Archfiend", "Unidentified 19",
    "Elders' Blood", "Voucher of Nulgath", "Voucher of Nulgath (non-mem)",
)

#: The eight Betrayal Blades, by name, for ``kissthe_void``'s blade argument.
BETRAYAL_BLADES: Tuple[str, ...] = tuple(
    f"{nth} Betrayal Blade of Nulgath"
    for nth in ("1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th")
)

#: The eleven Assisting Crag & Bamboozle rewards, as ``(name, item_id)``.
#: Item ids because that is how the quest picks between them.
ACAB_REWARDS: Tuple[Tuple[str, int], ...] = (
    ("Sword of Nulgath", 4670),
    ("Tainted Gem", 4769),
    ("Dark Crystal Shard", 4770),
    ("Diamond of Nulgath", 4771),
    ("Unidentified 19", 4752),
    ("Totem of Nulgath", 5357),
    ("Elders' Blood", 5586),
    ("Gem of Nulgath", 6136),
    ("Blood Gem of the Archfiend", 22332),
    ("Voucher of Nulgath", 4861),
    ("Voucher of Nulgath (non-mem)", 4862),
)

#: Which quest-7551 rewards can be asked for by name.
SWINDLES_RETURN_REWARDS: Tuple[str, ...] = (
    "Tainted Gem",
    "Dark Crystal Shard",
    "Diamond of Nulgath",
    "Gem of Nulgath",
    "Blood Gem of the Archfiend",
)

#: The member Forge chain.  ``GEMSTONE_OF_NULGATH`` gates every one of them --
#: 4918 hands it out, and the four Forge quests spend it.
GEMSTONE_OF_NULGATH = "Gemstone of Nulgath"
DEMANDING_APPROVAL_QUEST = 4917
GEMSTONES_FOR_NULGATH_QUEST = 4918
FORGE_TAINTED_GEMS_QUEST = 4919
FORGE_DARK_CRYSTAL_SHARDS_QUEST = 4920
FORGE_DIAMONDS_QUEST = 4921
FORGE_BLOOD_GEMS_QUEST = 4922
CARVE_UNI_GEMSTONE_QUEST = 4923
RECEIPT_OF_NULGATH_QUEST = 4924
RECEIPT_OF_NULGATH_ID = 33451
RECEIPT_OF_NULGATH = "Receipt of Nulgath"
GEMSTONE_RECEIPT_OF_NULGATH = "Gemstone Receipt of Nulgath"

#: Quest 4923 lets the caller name its reward; these are the ids the server
#: wants, straight from the reference's own lookup.
CARVE_REWARD_IDS = {
    "Tainted Gem": 4769,
    "Dark Crystal Shard": 4770,
    "Diamond of Nulgath": 4771,
    "Gem of Nulgath": 6136,
    "Blood Gem of the Archfiend": 22332,
}

#: The three ``GemstonesOfnulgath`` counters, by name.
GEMSTONE_COUNTERS: Tuple[str, ...] = (
    "Bloodstone of Nulgath",
    "Quartz of Nulgath",
    "Tanzanite of Nulgath",
)
UNI_GEMSTONE_OF_NULGATH = "Unidentified Gemstone of Nulgath"


def uni(nr: int) -> str:
    """``Unidentified {nr}`` -- the reference bot's ``CoreNation.Uni``.

    A one-liner, but the name is built in dozens of places, so it lives here
    rather than being re-spelled at every call site.
    """
    return f"Unidentified {nr}"


async def equip_class(cmd: Command, solo: bool = False) -> bool:
    """Equip the configured farm or solo class (``CoreBots.EquipClass``).

    Kept as a module-level name because every Nation routine and its tests call
    it through here; the body lives with the other CoreBots helpers, which
    ``bot.core_farms`` uses too.
    """
    return await _core_bots.equip_class(cmd, solo=solo)


def can_we_aggro(cmd: Command) -> bool:
    """Aggro while another player shares the cell (``CoreBots.CanWeAggro``)."""
    return _core_bots.can_we_aggro(cmd)


async def approval_and_favor(cmd: Command, quant_approval: int = 5000,
                             quant_favor: int = 5000) -> None:
    """Farm Nulgath's Approval and Archfiend's Favor in ``/evilwarnul`` r9.

    Port of ``CoreNation.ApprovalAndFavor``.  Both counters are read
    separately, so the loop runs until *both* are full.

    Note:
        The reference bot's own loop condition is
        ``!ShouldExit && approval < q || favor < q``, and ``&&`` binds tighter
        than ``||`` -- so it can keep looping after ``ShouldExit`` whenever
        favor is short.  That precedence bug is not reproduced; the loop here
        stops on disconnect, as intended.
    """
    if (await cmd.has_item("Nulgath's Approval", quant_approval)
            and await cmd.has_item("Archfiend's Favor", quant_favor)):
        return

    cmd.add_drop(["Nulgath's Approval", "Archfiend's Favor"])
    cmd.farming_logger("Nulgath's Approval", quant_approval)
    cmd.farming_logger("Archfiend's Favor", quant_favor)
    await equip_class(cmd)

    while cmd.is_still_connected():
        if (await cmd.has_item("Nulgath's Approval", quant_approval)
                and await cmd.has_item("Archfiend's Favor", quant_favor)):
            break
        if cmd.is_not_in_map("evilwarnul"):
            await cmd.join_map("evilwarnul")
            continue
        if cmd.is_not_in_cell("r9"):
            await cmd.jump_cell("r9", "Left")
            continue
        can_we_aggro(cmd)
        await cmd.use_next_skill(DEFAULT_SKILL_LIST, "*")


async def blood_from_the_void(cmd: Command, quant: int = 300) -> None:
    """Farm Blood From the Void in ``/tercesinvasion``.

    Port of ``CoreNation.BloodFromTheVoid``.  Quest 10583 for members, 10582
    otherwise; both are registered, so the auto-quest task turns them in as the
    three Archfiend drops arrive.
    """
    if await cmd.has_item("Blood From the Void", quant):
        return

    if cmd.is_still_connected() and not await cmd.is_completed_before(10581):
        cmd.bot.log("Blood From the Void needs the /tercesinvasion story completed "
              "(quest 10581). Run the TercesInvasion story script first.")
        return

    cmd.add_drop("Blood From the Void")
    await equip_class(cmd, solo=True)
    await cmd.register_quest(10583 if cmd.get_player().is_member else 10582)
    cmd.farming_logger("Blood From the Void", quant)

    while (cmd.is_still_connected()
           and not await cmd.has_item("Blood From the Void", quant)):
        await hunt_item(cmd, "Rodeleros' Blade Shard", 1, "tercesinvasion",
                        monster_name="Archfiend Rodeleros", is_temp=True)
        await hunt_item(cmd, "Vigneron's Chalice", 1, "tercesinvasion",
                        monster_name="Archfiend Vigneron", is_temp=True)
        await hunt_item(cmd, "Casimir's Pinky", 1, "tercesinvasion",
                        monster_name="Archfiend Casimir", is_temp=True)

    cmd.cancel_registered_quests()


async def fiend_emblem(cmd: Command, quant: int = 300) -> None:
    """Farm Fiend Emblem in ``/originul`` with quest 7890.

    Port of the standalone body in ``Nation/Materials/FiendEmblem.cs`` (that
    script holds its own logic rather than calling ``CoreNation``).  The class
    swaps between farm and solo per step, exactly as the reference bot does.
    """
    if await cmd.has_item("Fiend Emblem", quant):
        cmd.bot.log(f"You already have {quant} (max stack) Fiend Emblem")
        return

    cmd.add_drop("Fiend Emblem")

    while cmd.is_still_connected() and not await cmd.has_item("Fiend Emblem", quant):
        await cmd.ensure_accept_quest(7890)

        await equip_class(cmd)
        await hunt_item(cmd, "Essence of The Citadel", 30, "originul",
                        cell="r5", pad="Right", monster_name="*", is_temp=True)

        await equip_class(cmd, solo=True)
        await hunt_item(cmd, "Champion's Essence", 1, "originul",
                        cell="r5", pad="Right",
                        monster_name="Fiend Champion", is_temp=True)

        await cmd.ensure_turn_in_quest(7890)


async def join_swf(cmd: Command, map_name: str, cell: str = "Enter",
                   pad: str = "Spawn") -> None:
    """Enter a map whose retired SWF is client-loaded (``JoinSWF``).

    the reference bot joins the map and then calls ``world.loadMap(swfPath)`` to have the
    *client* load the retired map asset.  This engine renders nothing, so the
    only parts that carry meaning are the server join and the cell/pad -- which
    is exactly what this does.  The ``swfPath`` the reference bot passes (always
    ``ChiralValley/town-Mobius-21Feb14.swf`` in Nation) has no counterpart and
    is deliberately not a parameter here.

    Args:
        cmd (Command): Facade to act through.
        map_name (str): Map to join, e.g. ``"mobius"``.
        cell (str): Cell to stand in afterwards.
        pad (str): Pad within that cell.
    """
    while cmd.is_still_connected() and cmd.is_not_in_map(map_name):
        await cmd.join_map(map_name)
        await cmd.sleep(500)
    if cell and cmd.is_not_in_cell(cell):
        await cmd.jump_cell(cell, pad)


async def all_owned(cmd: Command, items: Sequence[Tuple[str, int]]) -> bool:
    """True when every ``(name, qty)`` pair is held somewhere in the account.

    The ``all(...)`` shape a generator cannot express once each check has to
    await.  Every pair withdraws banked stock before it is counted, so the answer
    is "do I own this", not "is it lying in my inventory".
    """
    for name, qty in items:
        if not await cmd.has_item(name, qty):
            return False
    return True


async def first_missing(cmd: Command,
                        candidates: Sequence[Tuple[int, str, int]]):
    """First ``(id, name, qty)`` entry the account does not already hold.

    An explicit loop rather than ``next(e for e in ...)``: once the ownership
    test has to await, a generator expression becomes an *async* generator and
    ``next()`` on it raises ``TypeError``.
    """
    for candidate in candidates:
        if not await cmd.has_item(candidate[1], candidate[2]):
            return candidate
    return None


async def _mobius_horns(cmd: Command, full: bool) -> None:
    """Farm the Slugfit / Cyclops horns the quest needs, in the old /mobius map."""
    horn, cyclops = (10, 6) if full else (5, 3)
    if (await cmd.has_item("Slugfit Horn", horn, isTemp=True)
            and await cmd.has_item("Cyclops Horn", cyclops, isTemp=True)):
        return
    await join_swf(cmd, "mobius", "Slugfit", "Bottom")
    await hunt_item(cmd, "Slugfit Horn", horn, "mobius",
                    cell="Slugfit", pad="Bottom",
                    monster_name="Slugfit", is_temp=True)
    await hunt_item(cmd, "Cyclops Horn", cyclops, "mobius",
                    cell="Slugfit", pad="Bottom",
                    monster_name="Cyclops Warlord", is_temp=True)


async def new_worlds_new_opportunities(cmd: Command,
                                       item: Optional[str] = None,
                                       quant: int = 1) -> None:
    """Farm quest 6183 / 6697 rewards with the Birthday Gift / Drone pet.

    Port of ``CoreNation.NewWorldsNewOpportunities``.  Which quest it is
    depends on the pet you own: ``Bounty Hunter's Drone Pet`` selects 6183,
    otherwise 6697.  With ``item`` given it farms that one up to ``quant``;
    without it, it walks every reward the quest offers and maxes each.

    Note:
        the reference bot reads the reward list from its client-side quest cache, so it can
        enumerate rewards *before* accepting.  The live ``getQuests`` payload
        only exists once the quest is accepted, so this registers the quest
        first and reads the rewards after -- same outcome, different order.
    """
    if item and await cmd.has_item(item, quant):
        return
    if not await cmd.has_any_item(NWNO_PETS):
        return

    quest_id = 6183 if await cmd.has_item("Bounty Hunter's Drone Pet") else 6697
    await equip_class(cmd)
    await cmd.register_quest(quest_id)          # accepts, so rewards load
    cmd.add_quest_rewards(quest_id)

    if item is None:
        quest = cmd.get_loaded_quest(quest_id)
        if _quest_rewards_or_warn(cmd, quest_id, quest) is None:
            cmd.cancel_registered_quests()
            return
        for _, name, max_stack in quest.reward_entries:
            if await cmd.has_item(name, max_stack):
                continue
            cmd.farming_logger(name, max_stack)
            while (cmd.is_still_connected()
                   and not await cmd.has_item(name, max_stack)):
                await _mobius_horns(cmd, full=True)
                await hunt_item(cmd, "Makai Fang", 10, "tercessuinotlim",
                                cell="m2", pad="Top",
                                monster_name="Dark Makai", is_temp=True)
                await hunt_item(cmd, "Imp Flame", 6, "hydra",
                                cell="Rune2", pad="Left",
                                monster_name="Fire Imp", is_temp=True)
                await hunt_item(cmd, "Wereboar Tusk", 4, "greenguardwest",
                                cell="West12", pad="Up",
                                monster_name="Big Bad Boar", is_temp=True)
        cmd.bot.log("[nation] all items maxed")
    else:
        cmd.farming_logger(item, quant)
        while cmd.is_still_connected() and not await cmd.has_item(item, quant):
            await _mobius_horns(cmd, full=False)
            await hunt_item(cmd, "Makai Fang", 5, "tercessuinotlim",
                            cell="m2", pad="Top",
                            monster_name="Dark Makai", is_temp=True)
            await hunt_item(cmd, "Imp Flame", 3, "hydra",
                            cell="Rune2", pad="Left",
                            monster_name="Fire Imp", is_temp=True)
            await hunt_item(cmd, "Wereboar Tusk", 2, "greenguardwest",
                            cell="West12", pad="Up",
                            monster_name="Big Bad Boar", is_temp=True)

    cmd.cancel_registered_quests()


async def _void_knight_step(cmd: Command, quest_id: int) -> None:
    """One turn-in cycle of the Void Knight Sword quest (5662 / 5659)."""
    await cmd.ensure_accept_quest(quest_id)
    await equip_class(cmd, solo=True)
    await join_swf(cmd, "mobius", "Slugfit", "Bottom")
    await hunt_item(cmd, "Slugfit Horn", 5, "mobius",
                    cell="Slugfit", pad="Bottom",
                    monster_name="Slugfit", is_temp=True)
    await hunt_item(cmd, "Aracara Silk", 1, "faerie",
                    monster_name="Aracara", is_temp=True)

    await equip_class(cmd)
    await hunt_item(cmd, "Makai Fang", 5, "tercessuinotlim",
                    cell="m2", pad="Left", monster_name="*", is_temp=True)
    await hunt_item(cmd, "Imp Flame", 3, "hydra",
                    monster_name="Fire Imp", is_temp=True)
    await hunt_item(cmd, "Aquamarine of Nulgath", 3, "battleunderc",
                    monster_name="Crystalized Jellyfish", is_temp=True)

    await cmd.ensure_turn_in_quest(quest_id)


async def void_knight_sword_quest(cmd: Command, item: Optional[str] = None,
                                  quant: int = 1) -> None:
    """Farm the Void Knight Sword quest rewards (5662 or 5659).

    Port of ``CoreNation.VoidKnightSwordQuest``.  Owning ``38275`` selects quest
    5662, owning only ``38254`` selects 5659; without either, there is nothing
    to do and the method returns.

    Arguments and reward handling match
    :func:`new_worlds_new_opportunities`.
    """
    if item and await cmd.has_item(item, quant):
        return
    if not await cmd.has_any_item_id(VOID_KNIGHT_SWORDS):
        return

    cmd.add_drop(BAG_DROPS)
    if item:
        cmd.add_drop(item)

    quest_id = 5662 if await cmd.has_item_id(38275) else 5659
    await cmd.ensure_accept_quest(quest_id)      # accepts, so rewards load
    cmd.add_quest_rewards(quest_id)

    if item is None:
        quest = cmd.get_loaded_quest(quest_id)
        if _quest_rewards_or_warn(cmd, quest_id, quest) is None:
            return
        for _, name, max_stack in quest.reward_entries:
            if await cmd.has_item(name, max_stack):
                continue
            cmd.farming_logger(name, max_stack)
            while (cmd.is_still_connected()
                   and not await cmd.has_item(name, max_stack)):
                await _void_knight_step(cmd, quest_id)
        cmd.bot.log("[nation] all items maxed")
    else:
        cmd.farming_logger(item, quant)
        while cmd.is_still_connected() and not await cmd.has_item(item, quant):
            await _void_knight_step(cmd, quest_id)


async def _travel(cmd: Command, map_name: str, cell: str,
                  pad: str = "Left") -> bool:
    """Move to ``map_name`` / ``cell``; False while still on the way.

    The C# spells this as ``Join`` + ``Wait.ForMapLoad`` + ``Jump`` +
    ``Wait.ForCellChange``.  This engine polls instead, so the caller loops
    until it gets True back.
    """
    if cmd.is_not_in_map(map_name):
        await cmd.join_map(map_name)
        await cmd.sleep(500)
        return False
    if cell and cmd.is_not_in_cell(cell):
        await cmd.jump_cell(cell, pad)
        await cmd.sleep(500)
        return False
    return True


async def kill_escherion(cmd: Command, item: Optional[str] = None,
                         quant: int = 1, is_temp: bool = False,
                         log: bool = True) -> None:
    """Kill Escherion in ``/escherion``, optionally for ``item``.

    A generic quest helper the Nation farms lean on.  Escherion is invulnerable
    while the Staff of Inversion stands, so the rotation aims at ``id.2`` (the
    staff) whenever it is alive and ``id.3`` (Escherion) otherwise -- the C#
    also branches on the target's *state*, but both of its branches resolve to
    one of those two anyway, and this engine's ``Monster`` carries no state.

    With ``item`` unset it fights one spawn to the death.
    """
    if item and await cmd.has_item(item, quant, isTemp=is_temp):
        return
    if item and not is_temp:
        cmd.add_drop(item)
    if item and log:
        cmd.farming_logger(item, quant)

    if item is None:
        # one kill: wait for the spawn, then fight until the cell is clear
        while (cmd.is_still_connected()
               and not cmd.is_monster_alive("*")):
            if not await _travel(cmd, "escherion", "Boss"):
                continue
            await cmd.sleep(500)
        async def goal() -> bool:
            return not cmd.is_monster_alive("*")
    else:
        async def goal() -> bool:
            return await cmd.has_item(item, quant, isTemp=is_temp)

    while cmd.is_still_connected() and not await goal():
        if not await _travel(cmd, "escherion", "Boss"):
            continue
        staff = cmd.get_monster(ESCHERION_STAFF)
        target = ESCHERION_STAFF if (staff and staff.is_alive) else ESCHERION_BOSS
        await cmd.use_next_skill(DEFAULT_SKILL_LIST, target)

    if item:
        await cmd.rest()


async def kill_vath(cmd: Command, item: Optional[str] = None, quant: int = 1,
                    is_temp: bool = False, log: bool = True) -> None:
    """Kill Vath in ``/stalagbite``, optionally for ``item``.

    Stalagbite (``id.8``) takes the hits while it is alive and Vath (``id.7``)
    otherwise -- the same two choices the C# makes from the target's state.
    """
    if item and await cmd.has_item(item, quant, isTemp=is_temp):
        return
    if item and not is_temp:
        cmd.add_drop(item)
    if item and log:
        cmd.farming_logger(item, quant)

    if item is None:
        while (cmd.is_still_connected()
               and not cmd.is_monster_alive("*")):
            if not await _travel(cmd, "stalagbite", "r2"):
                continue
            await cmd.sleep(500)
        async def goal() -> bool:
            return not cmd.is_monster_alive("*")
    else:
        async def goal() -> bool:
            return await cmd.has_item(item, quant, isTemp=is_temp)

    while cmd.is_still_connected() and not await goal():
        if not await _travel(cmd, "stalagbite", "r2"):
            continue
        stalagbite = cmd.get_monster(STALAGBITE)
        target = STALAGBITE if (stalagbite and stalagbite.is_alive) else VATH_BOSS
        await cmd.use_next_skill(DEFAULT_SKILL_LIST, target)


async def dark_makai_item(cmd: Command, item: Optional[str] = "Dark Makai Rune",
                          quantity: int = 1, is_temp: bool = True) -> None:
    """Farm a Dark Makai drop, in Tercessuinotlim or the member/non-member map.

    The C# picks one of the two locations at random to spread the load; that
    stays.  ``/Nulgath`` is the member variant of the drop's second home, with
    ``/evilmarsh`` replacing it otherwise.
    """
    if not item or await cmd.has_item(item, quantity, isTemp=is_temp):
        return

    member = bool(cmd.get_player().is_member)
    map_name, cell = random.choice([
        ("tercessuinotlim", "m1"),
        ("Nulgath" if member else "evilmarsh", "Field1"),
    ])

    while (cmd.is_still_connected()
           and not await cmd.has_item(item, quantity, isTemp=is_temp)):
        if not await _travel(cmd, map_name, cell):
            continue
        await cmd.use_next_skill(DEFAULT_SKILL_LIST, "Dark Makai")

    await equip_class(cmd, solo=True)


async def crags_thirst(cmd: Command, quant: int = 1000) -> None:
    """Diamonds of Nulgath via Crag's Thirst (quest 600).

    Needs the Crag pet and 100 Unidentified 10 banked; the C# bails out
    silently without them, and so does this.
    """
    if (not await cmd.has_item(CRAG_PET)
            or await cmd.has_item("Diamond of Nulgath", quant)
            or not await cmd.has_item(uni(10), 100)):
        return

    cmd.bot.log("[nation] doing Crag's Thirst")
    while (cmd.is_still_connected()
           and await cmd.has_item(uni(10), 100)
           and not await cmd.has_item("Diamond of Nulgath", quant)):
        # the C# calls ResetQuest(600) here, which sends no packet of its own;
        # accepting the quest is the whole of it
        await cmd.ensure_accept_quest(600)
        await dark_makai_item(cmd, "Dark Makai Rune")
        await cmd.ensure_turn_in_quest(600)


async def bloody_chaos(cmd: Command, quant: int = 100, relic: bool = False,
                       hydra_level: int = 85, endless: bool = False) -> None:
    """Blood Gems of the Archfiend via Bloody Chaos (quest 7816 [+2857]).

    Gated on level 80 in the C#.  ``player.LEVEL`` is 0 until the login payload
    is parsed, and 0 is treated as "unknown" rather than "below 80" so a failed
    parse cannot silently skip the whole farm.
    """
    level = cmd.get_player().LEVEL
    if level and level < 80:
        return
    if not endless and await cmd.has_item("Blood Gem of the Archfiend", quant):
        return

    cmd.add_drop(["Blood Gem of the Archfiend", "Hydra Scale Piece"])
    if relic:
        cmd.add_drop(BLOODY_CHAOS_SUPPLIES)
    cmd.farming_logger("Blood Gem of the Archfiend", quant)

    for quest_id in ([7816, 2857] if relic else [7816]):
        await cmd.register_quest(quest_id)
    await equip_class(cmd, solo=True)

    while (cmd.is_still_connected()
           and (endless
                or not await cmd.has_item("Blood Gem of the Archfiend", quant))):
        await kill_escherion(cmd, "Escherion's Helm", is_temp=False)
        await kill_vath(cmd, "Shattered Legendary Sword of Dragon Control",
                        is_temp=False)
        await hunt_item(cmd, "Hydra Scale Piece", 200, "hydrachallenge",
                        monster_name=f"Hydra Head {hydra_level}", is_temp=False)

    cmd.cancel_registered_quests()


async def essence_of_defeat_reagent(cmd: Command, quant: int = 1000) -> None:
    """Dark Crystal Shards via the Essence of Defeat Reagent quest (570).

    Six steps per turn-in, sweeping solo and farm classes in between exactly as
    the C# does.
    """
    if await cmd.has_item("Dark Crystal Shard", quant):
        return

    cmd.add_drop(TERCESS_BAGS + BAG_DROPS)
    cmd.farming_logger("Dark Crystal Shard", quant)
    await cmd.register_quest(570)

    while (cmd.is_still_connected()
           and not await cmd.has_item("Dark Crystal Shard", quant)):
        await equip_class(cmd, solo=True)
        await hunt_item(cmd, "Aracara's Fang", 1, "faerie",
                        monster_name="Aracara", is_temp=False)
        await hunt_item(cmd, "Hydra Scale", 1, "hydra",
                        monster_name="Hydra Head", is_temp=False)
        await kill_vath(cmd, "Strand of Vath's Hair", 1, is_temp=False)
        await hunt_item(cmd, "O-dokuro's Tooth", 1, "yokaiwar",
                        monster_name="O-dokuro's Head", is_temp=False)
        await kill_escherion(cmd, "Escherion's Chain", is_temp=False)

        await equip_class(cmd)
        await hunt_item(cmd, "Defeated Makai", 50, "tercessuinotlim",
                        cell="m2", pad="Left", monster_name="*", is_temp=False)

        await equip_class(cmd, solo=True)
        await hunt_item(cmd, "Tibicenas' Chain", 1, "djinn",
                        monster_name="Tibicenas", is_temp=False)

    cmd.cancel_registered_quests()


async def dirty_deeds_done_dirt_cheap(cmd: Command, quant: int = 1000,
                                      sroe: bool = False,
                                      sroe_items: Optional[Sequence[str]] = None
                                      ) -> None:
    """Unidentified 10 via Dirty Deeds Done Dirt Cheap (quest 7818).

    Needs ``/towerofdoom10`` cleared and a solo class, per the C# docstring.

    Note:
        The optional ``SRoE`` branch buys merge-shop stock with a full bag of
        Unidentified 10 (``GetShopItems`` + ``MaxBuyQuant`` + a capped buy
        loop).  That shop path is not ported; asking for it prints a notice and
        farms the base quest anyway rather than silently doing less.
    """
    cmd.add_drop(["Emerald Pickaxe", "Seraphic Grave Digger Spade",
                  "Unidentified 10", "Receipt of Swindle",
                  "Blood Gem of the Archfiend", "Dark Crystal Shard",
                  "Gem of Nulgath", "Tainted Gem", "Totem of Nulgath"])
    await equip_class(cmd, solo=True)
    await kill_escherion(cmd, "Emerald Pickaxe")
    await hunt_item(cmd, "Seraphic Grave Digger Spade", 1, "legioncrypt",
                    cell="r1", pad="Top", monster_name="Gravedigger",
                    is_temp=False)

    if sroe:
        cmd.bot.log("[nation] the SRoE merge-shop branch is not ported; farming "
              "Unidentified 10 with the base quest only.")

    while (cmd.is_still_connected()
           and not await cmd.has_item("Unidentified 10", quant)):
        await cmd.ensure_accept_quest(7818)
        await hunt_item(cmd, "Slugbutter Digging Advice", 1, "towerofdoom10",
                        monster_name="Slugbutter", is_temp=True)
        await hunt_item(cmd, "Chaotic Tunneling Techniques", 2, "crownsreach",
                        monster_name="Chaos Tunneler", is_temp=True)
        await hunt_item(cmd, "Crystalized Corporate Digging Secrets", 3,
                        "downward", monster_name="Crystal Mana Construct",
                        is_temp=True)
        await cmd.ensure_turn_in_quest(7818)
        cmd.farming_logger("Unidentified 10", quant)


def _quest_rewards_or_warn(cmd: Command, quest_id: int,
                           quest: Optional[Quest]) -> Optional[List[str]]:
    """Reward names for a quest, or ``None`` with a loud, actionable reason.

    A quest can be loaded and still hand over no names: the ``getQuests``
    payload only carries them inside its ``oRewards`` block, and not every
    quest sends one.  An empty list from that looks exactly like "nothing left
    to farm", which quietly ends the run -- so this reports what the payload
    actually carried and tells the caller to name the item.

    Returns:
        Optional[List[str]]: The names, or ``None`` when they are unavailable.
    """
    if quest is None:
        cmd.bot.log(f"[nation] quest {quest_id} is not loaded; nothing to do.")
        return None
    names = quest.reward_names
    if names:
        return names
    ids = quest.reward_ids
    if ids:
        shape = quest.get("oRewards")
        if isinstance(shape, dict):
            detail = f"dict keyed {sorted(shape)[:6]}"
        elif isinstance(shape, list):
            detail = f"list of {len(shape)}"
        else:
            detail = repr(shape)
        cmd.bot.log(f"[nation] quest {quest_id} listed {len(ids)} reward ids ({ids}) "
              f"but sent no names, so its rewards cannot be enumerated from "
              f"the payload. Pass the item you want as the argument instead. "
              f"(oRewards is a {type(shape).__name__}: {detail}; "
              f"payload keys: {sorted(quest.keys())})")
    else:
        cmd.bot.log(f"[nation] quest {quest_id} sent no rewards at all; nothing to "
              f"farm. (payload keys: {sorted(quest.keys())})")
    return None


async def has_obon_pet(cmd: Command) -> bool:
    """True for members holding one of the two OBoN stand-in pets."""
    return (bool(cmd.get_player().is_member)
            and await cmd.has_any_item_id(OBO_PETS))


async def _kill_once(cmd: Command, map_name: str, cell: str, pad: str,
                     monster: str) -> None:
    """Fight one spawn in ``map_name``/``cell`` to the death.

    The reference bot's ``Core.KillMonster`` without an item is a single kill, and its
    callers' outer loops are what repeat it -- so this does the same rather
    than looping internally.
    """
    while cmd.is_still_connected() and not await _travel(cmd, map_name, cell, pad):
        pass
    # wait for the spawn, so this cannot return before the fight even started
    for _ in range(20):
        if cmd.is_monster_alive(monster) or cmd.is_monster_alive("*"):
            break
        await cmd.sleep(500)
    while cmd.is_still_connected() and cmd.is_monster_alive("*"):
        await cmd.use_next_skill(DEFAULT_SKILL_LIST, monster)


async def sell_voucher_of_nulgath(cmd: Command, sell_mem_voucher: bool = True,
                                  item: Optional[str] = None) -> None:
    """Sell the member Voucher of Nulgath, unless it is what is being farmed.

    The reference bot reads the flag from its persisted option store; here it is a
    parameter and the caller passes what it has.
    """
    if not sell_mem_voucher or item == "Voucher of Nulgath":
        return
    if not await cmd.has_item("Voucher of Nulgath"):
        return
    if cmd.is_not_in_cell("Enter"):
        await cmd.jump_cell("Enter", "Spawn")
    await cmd.sell_item("Voucher of Nulgath",
                        cmd.get_quant_item("Voucher of Nulgath"))


def _log_supplies_config(cmd: Command, item: Optional[str], quant: int, ultra_alteon: bool,
                         hydra: bool, keep_voucher: bool,
                         sell_mem_voucher: bool, assistant: bool,
                         return_policy: bool, return_item: Optional[str],
                         voucher_item_during: bool = False) -> None:
    """Print what the Supplies route resolved to, and what each setting does.

    The reference logs the same settings as bare flags; the labels here say what
    each one means, because the flags are what decides how a long run behaves.
    """
    route = ("the Hydra Challenge" if hydra
             else "Ultra Alteon" if ultra_alteon
             else "Escherion, the base quest")
    if keep_voucher:
        voucher = "kept -- never sold, whatever the gold"
    elif sell_mem_voucher:
        voucher = "the member voucher is sold once the account is past 100M gold"
    else:
        voucher = "kept -- after 100M gold the member voucher is not sold"

    cmd.bot.log("[nation] [Supplies] =========================")
    cmd.bot.log("[nation] [Supplies] target      : "
          + (f"{item} x{quant}" if item
             else "every principal reward, each to its max stack"))
    cmd.bot.log(f"[nation] [Supplies] relic route : {route} -- where each turn-in's "
          f"Relic of Chaos comes from")
    cmd.bot.log(f"[nation] [Supplies] voucher     : {voucher}")
    cmd.bot.log("[nation] [Supplies] conversions : "
          + ("spare vouchers are traded for the totem or gem that is short "
             "during the farm" if voucher_item_during
             else "spare vouchers are only converted at the end of a pass"))
    cmd.bot.log("[nation] [Supplies] assistant   : "
          + ("War-Torn Memorabilia is bought with spare gold each pass"
             if assistant else "off"))
    cmd.bot.log("[nation] [Supplies] swindle     : "
          + ("quest 7551 (Swindle's Return Policy) runs each pass"
             if return_policy else "off")
          + (f", asking for {return_item}" if return_policy and return_item
             else ""))
    cmd.bot.log("[nation] [Supplies] =========================")


async def kill_hydra(cmd: Command) -> None:
    """Kill one Hydra Head in ``/hydrachallenge`` h90, for one Relic of Chaos.

    The C# re-reads the relic count each pass and stops as soon as it goes up,
    which is what "one kill" means here too.
    """
    if cmd.is_not_in_map("hydrachallenge"):
        await cmd.join_map("hydrachallenge")
    before = cmd.get_quant_item("Relic of Chaos")

    while (cmd.is_still_connected()
           and cmd.get_quant_item("Relic of Chaos") == before):
        if cmd.is_not_in_cell("h90"):
            await cmd.jump_cell("h90", "Left")
            await cmd.sleep(500)
            continue
        can_we_aggro(cmd)
        await cmd.use_next_skill(DEFAULT_SKILL_LIST, "*")


async def do_swindles_return_area(cmd: Command, return_policy_active: bool,
                                  item: Optional[str] = None) -> None:
    """Complete quest 7551 (Swindle's Return Policy) for ``item`` or the first gap.

    The C# gates on its own client-side "can complete" check; the equivalent
    here is ``can_turnin_quest``, which tests the turn-in requirements against
    the inventory.
    """
    if not return_policy_active:
        return
    if not await all_owned(cmd, [(uni(n), 1) for n in (1, 6, 9, 16, 20)]):
        return

    await cmd.ensure_accept_quest(7551)
    quest = cmd.get_loaded_quest(7551)
    if _quest_rewards_or_warn(cmd, 7551, quest) is None:
        return

    candidates = [entry for entry in quest.reward_entries
                  if entry[0] != SWINDLES_EXCLUDED_REWARD]
    if item is not None:
        wanted = [entry for entry in candidates if entry[1] == item]
        if not wanted:
            cmd.bot.log(f"[nation] {item!r} is not a quest 7551 reward; skipping.")
            return
        if await cmd.has_item(wanted[0][1], wanted[0][2]):
            return
    elif await all_owned(cmd, [(name, stack) for _, name, stack in candidates]):
        return

    await dark_makai_item(cmd, "Dark Makai Rune")

    if not cmd.can_turnin_quest(7551):
        cmd.bot.log("[nation] quest 7551 is not completable yet; skipping the turn-in.")
        return

    chosen = None
    if item is not None:
        chosen = next((e for e in candidates if e[1] == item), None)
    else:
        chosen = await first_missing(cmd, candidates)

    await cmd.ensure_turn_in_quest(7551, chosen[0] if chosen else -1)


async def assistant_during_supplies(cmd: Command, assist: bool = True) -> None:
    """Spend spare gold on War-Torn Memorabilia (quest 2859).

    Only runs past 100k gold; buys up to 250 at a time.
    """
    if not assist:
        return
    gold = cmd.get_player().GOLD
    if gold < 100_000:
        return
    if cmd.is_not_in_cell("Enter"):
        await cmd.jump_cell("Enter", "Spawn")
    quantity = min(gold // 100_000, 250)
    await cmd.ensure_accept_quest(2859)
    await buy_item(cmd, 41, "War-Torn Memorabilia", quantity,
                      map_name="yulgar")
    await cmd.ensure_turn_in_quest(2859, -1, quantity)


async def get_pcod(cmd: Command) -> bool:
    """Obtain the Purified Claymore of Destiny (quest 548).

    Returns:
        bool: True when the claymore is held afterwards, False when a
        prerequisite is missing.

    Note:
        The C# runs ``Farm.Experience(15)`` and ``Farm.GoodREP(8)`` first, and so
        does this -- a Good rank below 8 makes quest 548 unacceptable, which used
        to stop the run with a message.
    """
    if await cmd.has_item("Purified Claymore of Destiny"):
        return True

    await farm_experience(cmd, 15)
    await farm_faction(cmd, "Good", 8)

    rank = cmd.get_faction_rank("Good")
    level = cmd.get_player().LEVEL
    if rank < 8 or (level and level < 15):
        cmd.bot.log(f"[nation] the Purified Claymore still needs Good rank 8 and level "
              f"15 (have rank {rank}, level {level or 'unknown'}). Stopping.")
        return False

    cmd.add_drop("Purified Claymore of Destiny")
    await cmd.ensure_accept_quest(548)
    await hunt_item(cmd, "Warrior Claymore Blade", 1, "battleundera",
                    monster_name="Undead Berserker", is_temp=False)
    await cmd.ensure_turn_in_quest(548)
    return True


async def supplies(cmd: Command, item: Optional[str] = None, quant: int = 1,
                   ultra_alteon: bool = False, keep_voucher: bool = False,
                   assistant_during: bool = False,
                   return_item: Optional[str] = None,
                   return_policy: bool = False,
                   voucher_item_during: bool = False,
                   hydra_challenge: bool = False,
                   sell_mem_voucher: bool = False) -> None:
    """Farm Supplies to Spin the Wheel of Chance (quest 2857) and its extras.

    The broadest Nation route: with ``item`` it farms that one reward, without
    it, every reward the quest offers.

    Note:
        ``sell_mem_voucher`` is the C# struct field ``sellMemVoucher``, which
        it fills from its persisted option store.  This engine has no such
        store, so it is a parameter here instead -- which is the substitution
        the whole ``CBOBool`` family gets.
    """
    if item and await cmd.has_item(item, quant):
        return

    # with no target, stop once every principal drop is already maxed
    if item is None:
        await cmd.ensure_accept_quest(2857)
        quest = cmd.get_loaded_quest(2857)
        if quest is not None and quest.reward_entries:
            stacks = {name: stack for _, name, stack in quest.reward_entries}
            if await all_owned(cmd, [(drop, stacks.get(drop, 1))
                                     for drop in BAG_DROPS_PRINCIPAL]):
                return

    if keep_voucher:
        sell_mem_voucher = False
    elif sell_mem_voucher and cmd.get_player().GOLD >= 100_000_000:
        sell_mem_voucher = False

    _log_supplies_config(cmd, item, quant, ultra_alteon, hydra_challenge,
                         keep_voucher, sell_mem_voucher, assistant_during,
                         return_policy, return_item, voucher_item_during)

    quests = [2857]
    if item != uni(13) and await cmd.has_item_id(38261):
        quests.append(9542)
    if await cmd.has_item("Drudgen the Assistant"):
        quests.append(870)
    for quest_id in quests:
        await cmd.register_quest(quest_id)

    drops: List[str] = []
    if item:
        drops.append(item)
    if return_item:
        drops.append(return_item)
    drops.extend(cmd.get_quest_rewards(9542))
    drops.extend(SUPPLIES_REWARDS)
    if sell_mem_voucher:
        drops.append("Voucher of Nulgath")
    drops.append("Relic of Chaos")
    if return_policy:
        drops.extend([uni(1), uni(6), uni(9), uni(16), uni(20),
                      "Receipt of Swindle"])
    cmd.add_drop(drops)
    await equip_class(cmd, solo=True)

    if item is None or item == "All":
        await _farm_all_supplies(cmd, ultra_alteon, hydra_challenge,
                                 keep_voucher, assistant_during, return_item,
                                 return_policy, sell_mem_voucher)
    else:
        await _farm_single_supply(cmd, item, quant, ultra_alteon,
                                  hydra_challenge, keep_voucher,
                                  assistant_during, return_item, return_policy,
                                  voucher_item_during, sell_mem_voucher)

    cmd.cancel_registered_quests()


async def _farm_all_supplies(cmd: Command, ultra_alteon: bool, hydra: bool,
                             keep_voucher: bool, assistant_during: bool,
                             return_item: Optional[str], return_policy: bool,
                             sell_mem_voucher: bool) -> None:
    """Max every Supplies reward, pet route first when a pet is owned."""
    quest = cmd.get_loaded_quest(2857)
    if _quest_rewards_or_warn(cmd, 2857, quest) is None:
        return

    for thing in SUPPLIES_REWARDS:
        if not cmd.is_still_connected():
            return
        entry = next((e for e in quest.reward_entries if e[1] == thing), None)
        if entry is None:
            continue
        _, name, max_stack = entry

        if not ultra_alteon and not hydra and (await cmd.has_item(CRAG_PET)
                                               or await has_obon_pet(cmd)):
            await bamboozle_vs_drudge(cmd, name, max_stack, keep_voucher,
                                      assistant_during, return_item,
                                      came_from_supplies=True,
                                      sell_mem_voucher=sell_mem_voucher,
                                      return_policy=return_policy)
            continue

        while (cmd.is_still_connected()
               and not await cmd.has_item(name, max_stack)):
            if hydra:
                await kill_hydra(cmd)
            elif ultra_alteon:
                await hunt_item(cmd, "Relic of Chaos", 1, "ultraalteon",
                                cell="r10", pad="Left",
                                monster_name="Ultra Chaos Alteon",
                                is_temp=False)
            else:
                await kill_escherion(cmd, "Relic of Chaos", is_temp=False,
                                     log=False)
            await sell_voucher_of_nulgath(cmd, sell_mem_voucher, None)
            await assistant_during_supplies(cmd, assistant_during)
            await do_swindles_return_area(cmd, return_policy, return_item)
            await handle_voucher_conversions(cmd, name)


async def _farm_single_supply(cmd: Command, item: str, quant: int,
                              ultra_alteon: bool, hydra: bool,
                              keep_voucher: bool, assistant_during: bool,
                              return_item: Optional[str], return_policy: bool,
                              voucher_item_during: bool,
                              sell_mem_voucher: bool) -> None:
    """Farm one Supplies reward up to ``quant``."""
    if not ultra_alteon and not hydra and (await cmd.has_item(CRAG_PET)
                                           or await has_obon_pet(cmd)):
        await bamboozle_vs_drudge(cmd, item, quant, keep_voucher,
                                  assistant_during, return_item,
                                  came_from_supplies=True,
                                  sell_mem_voucher=sell_mem_voucher,
                                  return_policy=return_policy)
        return

    while cmd.is_still_connected() and not await cmd.has_item(item, quant):
        if hydra:
            await kill_hydra(cmd)
        elif ultra_alteon:
            await hunt_item(cmd, "Relic of Chaos", 1, "ultraalteon",
                            cell="r10", pad="Left",
                            monster_name="Ultra Chaos Alteon", is_temp=False)
        else:
            await kill_escherion(cmd, log=False)
        await sell_voucher_of_nulgath(cmd, sell_mem_voucher, item)
        await assistant_during_supplies(cmd, assistant_during)
        await do_swindles_return_area(cmd, return_policy, return_item)
        if voucher_item_during:
            await handle_voucher_conversions(cmd, item)


async def handle_voucher_conversions(cmd: Command, item: str) -> None:
    """Trade spare Vouchers for the totem or gem that is not maxed yet.

    Quest 4778 hands out one or the other; the C# picks the *other* one so the
    two keep pace with each other.
    """
    if (not await cmd.has_item("Voucher of Nulgath (non-mem)")
            or not await cmd.has_item("Essence of Nulgath", 60)):
        return

    diamonds_maxed = await cmd.has_item("Diamond of Nulgath", 1000)
    totems_maxed = await cmd.has_item("Totem of Nulgath", 100)

    if item.lower() == "diamond of nulgath":
        if diamonds_maxed and not totems_maxed:
            await cmd.ensure_turn_in_quest(VOUCHER_CONVERSION_QUEST,
                                           TOTEM_OF_NULGATH, 100)
    elif item.lower() == "totem of nulgath":
        if totems_maxed and not diamonds_maxed:
            await cmd.ensure_turn_in_quest(VOUCHER_CONVERSION_QUEST,
                                           GEM_OF_NULGATH, 1000)
    elif not totems_maxed:
        await cmd.ensure_turn_in_quest(VOUCHER_CONVERSION_QUEST,
                                       TOTEM_OF_NULGATH, 100)
    elif not diamonds_maxed:
        await cmd.ensure_turn_in_quest(VOUCHER_CONVERSION_QUEST,
                                       GEM_OF_NULGATH, 1000)


async def bamboozle_vs_drudge(cmd: Command, item: Optional[str] = None,
                              quant: int = 1, keep_voucher: bool = False,
                              assistant_during: bool = False,
                              return_item: Optional[str] = None,
                              came_from_supplies: bool = False,
                              sell_mem_voucher: bool = False,
                              return_policy: bool = False) -> None:
    """The Bamboozle-vs-Drudge route: kill Tainted Elementals in ``/evilmarsh``.

    Note:
        The C# accepts ``item = null`` and then loops on
        ``!CheckInventory(null, quant)``, which never becomes true -- it spins
        until the bot is stopped.  Rather than reproduce that, ``item`` is
        required here and a null one stops with a message.  Every real caller
        (``Supplies``) passes a name.
    """
    if item is None:
        cmd.bot.log("[nation] bamboozle_vs_drudge needs an item; the C# version "
              "accepts null and then loops forever. Nothing farmed.")
        return
    if await cmd.has_item(item, quant):
        cmd.bot.log(f"[nation] {item} x{quant} already owned.")
        return

    cmd.add_drop(["Relic of Chaos", "Tainted Core", item])
    if return_policy:
        cmd.add_drop([uni(1), uni(6), uni(9), uni(16), uni(20)])
    if not came_from_supplies:
        cmd.bot.log(f"[nation] bamboozle mode: item {item} | keep {keep_voucher} "
              f"| assist {assistant_during}")

    cmd.farming_logger(item, quant)

    quests = [2857]
    if await cmd.has_item(CRAG_PET):
        quests.append(609)
    if await has_obon_pet(cmd):
        cmd.add_drop("Tainted Soul")
        quests.append(599 if await cmd.has_item_id(4809) else 2561)
    if await cmd.has_item_id(38261):
        quests.append(9542)
    for quest_id in dict.fromkeys(quests):
        await cmd.register_quest(quest_id)

    await equip_class(cmd, solo=True)

    while cmd.is_still_connected() and not await cmd.has_item(item, quant):
        await _kill_once(cmd, "evilmarsh", "End", "Left", "Tainted Elemental")
        await sell_voucher_of_nulgath(cmd, sell_mem_voucher, item)
        await assistant_during_supplies(cmd, assistant_during)
        if return_item:
            await do_swindles_return_area(cmd, return_policy, return_item)
        await handle_voucher_conversions(cmd, item)
        if (return_policy and item in (None, "Diamond of Nulgath")
                and not await cmd.has_item("Diamond of Nulgath", 1000)):
            await crags_thirst(cmd)


async def essence_of_nulgath(cmd: Command, quant: int = 60) -> None:
    """Farm Essence of Nulgath off the Dark Makai in Tercessuinotlim."""
    if await cmd.has_item("Essence of Nulgath", quant):
        return
    cmd.add_drop("Essence of Nulgath")
    await equip_class(cmd)
    await hunt_item(cmd, "Essence of Nulgath", quant, "tercessuinotlim",
                    cell="m2", pad="Left", monster_name="Dark Makai",
                    is_temp=False)


async def diamond_exchange(cmd: Command, farm_diamond: bool = True) -> None:
    """Quest 869: swap 15 Diamonds for Unidentified 13, via the Dark Makai Sigil.

    Silently does nothing without the Crag pet or with Uni 13 already full --
    the C# returns on the same two conditions.
    """
    if ((not await cmd.has_item("Diamond of Nulgath", 15) and not farm_diamond)
            or not await cmd.has_item(CRAG_PET)
            or await cmd.has_item(uni(13), 13)):
        return

    cmd.add_drop("Diamond of Nulgath")
    if farm_diamond and (await has_obon_pet(cmd) or await cmd.has_item(CRAG_PET)):
        await bamboozle_vs_drudge(cmd, "Diamond of Nulgath", 15)

    await equip_class(cmd)
    while (cmd.is_still_connected()
           and await cmd.has_item("Diamond of Nulgath", 15)
           and not await cmd.has_item(uni(13), 13)):
        await cmd.ensure_accept_quest(869)
        await dark_makai_item(cmd, "Dark Makai Sigil")
        await cmd.ensure_turn_in_quest(869)


async def contract_exchange(cmd: Command, reward_name: str, quant: int,
                            farm_uni13: bool = True) -> None:
    """Quest 870: trade Unidentified 13 for a named reward.

    Note:
        The C# takes a ``ContractExchangeRewards`` enum; a reward *name* is
        equivalent (the enum only exists to label the same four strings) and
        lets the caller's switch collapse into a plain call.
    """
    if not await cmd.has_item("Drudgen the Assistant"):
        cmd.bot.log('[nation] missing "Drudgen the Assistant"')
        return
    if not await cmd.has_item(uni(13)) and not farm_uni13:
        cmd.bot.log("[nation] contract exchange needs Unidentified 13 and was told "
              "not to farm it")
        return

    cmd.add_drop(BAG_DROPS)
    await equip_class(cmd, solo=True)
    cmd.farming_logger(reward_name, quant)

    reward_id = _reward_id(cmd, 870, reward_name)
    while cmd.is_still_connected() and not await cmd.has_item(reward_name, quant):
        if farm_uni13 and not await cmd.has_item(uni(13)):
            await farm_uni13_quest(cmd, 3)
        await cmd.ensure_accept_quest(870)
        await _kill_once(cmd, "tercessuinotlim", "m4", "Top",
                         "Shadow of Nulgath")
        await cmd.ensure_turn_in_quest(870, reward_id)


def _reward_id(cmd: Command, quest_id: int, name: str) -> int:
    """Item id of a quest reward by name, or -1 when the quest is not loaded."""
    for item_id, reward_name, _ in cmd.get_quest_reward_entries(quest_id):
        if reward_name == name:
            return item_id
    return -1


async def farm_contract_exchage(cmd: Command, item: Optional[str] = None,
                                quant: int = 1) -> None:
    """Farm any of the four quest-870 rewards, through the Supplies route.

    Note:
        The C# switches on the reward to pick an enum; because
        :func:`contract_exchange` takes a name, that whole switch becomes one
        call and the two branches of the C# (targeted vs all four) differ only
        in which ``ReturnItem`` they pass on.
    """
    if (not await cmd.has_item("Drudgen the Assistant")
            or (item and await cmd.has_item(item, quant))):
        if not await cmd.has_item("Drudgen the Assistant"):
            cmd.bot.log('[nation] missing "Drudgen the Assistant"')
        return

    await equip_class(cmd)
    cmd.add_quest_rewards(870)

    if item is None:
        await cmd.ensure_accept_quest(870)
        if _quest_rewards_or_warn(cmd, 870, cmd.get_loaded_quest(870)) is None:
            return

    for name in ([item] if item else list(CONTRACT_REWARDS)):
        await cmd.ensure_accept_quest(870)
        quest = cmd.get_loaded_quest(870)
        entry = next((e for e in (quest.reward_entries if quest else [])
                      if e[1] == name), None)
        if entry is None:
            if item:
                cmd.bot.log(f"[nation] reward {name!r} is not part of quest 870.")
            continue
        _, reward_name, max_stack = entry
        target = quant if quant > 1 else max_stack
        cmd.farming_logger(reward_name, target)
        while (cmd.is_still_connected()
               and not await cmd.has_item(reward_name, target)):
            await supplies(cmd, "Diamond of Nulgath", 45,
                           return_item="Diamond of Nulgath")
            await contract_exchange(cmd, reward_name, target)


async def farm_uni13_quest(cmd: Command, quant: int = 13) -> None:
    """Unidentified 13, stacked to its cap of 13."""
    if await cmd.has_item(uni(13), quant):
        return
    cmd.add_drop(uni(13))
    quant = min(quant, 13)

    if await cmd.has_item(CRAG_PET):
        while (cmd.is_still_connected()
               and not await cmd.has_item(uni(13), quant)):
            await diamond_exchange(cmd)

    await new_worlds_new_opportunities(cmd, uni(13), quant)
    await void_knight_sword_quest(cmd, uni(13), quant)
    await supplies(cmd, uni(13), quant)


async def farm_uni10(cmd: Command, quant: int = 1000) -> None:
    """Unidentified 10, pet route first when one is owned."""
    if await cmd.has_item("Unidentified 10", quant):
        return
    cmd.add_drop("Unidentified 10")
    if await has_obon_pet(cmd) or await cmd.has_item(CRAG_PET):
        await bamboozle_vs_drudge(cmd, "Unidentified 10", quant,
                                  came_from_supplies=True)
    await dirty_deeds_done_dirt_cheap(cmd, quant)


async def farm_dark_crystal_shard(cmd: Command, quant: int = 1000) -> None:
    """Dark Crystal Shard, by every route the account can take."""
    if await cmd.has_item("Dark Crystal Shard", quant):
        return
    cmd.add_drop("Dark Crystal Shard")
    await farm_contract_exchage(cmd, "Dark Crystal Shard", quant)
    await new_worlds_new_opportunities(cmd, "Dark Crystal Shard", quant)
    if await cmd.has_item(CRAG_PET):
        await supplies(cmd, "Dark Crystal Shard", quant,
                       return_item="Dark Crystal Shard")
    await void_knight_sword_quest(cmd, "Dark Crystal Shard", quant)
    await supplies(cmd, "Dark Crystal Shard", quant,
                   return_item="Dark Crystal Shard")
    await essence_of_defeat_reagent(cmd, quant)


async def farm_diamond_of_nulgath(cmd: Command, quant: int = 1000) -> None:
    """Diamond of Nulgath, by every route the account can take."""
    if await cmd.has_item("Diamond of Nulgath", quant):
        return
    cmd.add_drop("Diamond of Nulgath")
    while (cmd.is_still_connected()
           and not await cmd.has_item("Diamond of Nulgath", quant)
           and await cmd.has_item(CRAG_PET)
           and await cmd.has_item(uni(10), 100)):
        await crags_thirst(cmd, quant)
    if await cmd.has_item(CRAG_PET):
        await supplies(cmd, "Diamond of Nulgath", quant,
                       return_item="Diamond of Nulgath")
    await void_knight_sword_quest(cmd, "Diamond of Nulgath", quant)
    await supplies(cmd, "Diamond of Nulgath", quant,
                   return_item="Diamond of Nulgath")


async def farm_gem_of_nulgath(cmd: Command, quant: int = 1000) -> None:
    """Gem of Nulgath, by every route the account can take."""
    if await cmd.has_item("Gem of Nulgath", quant):
        return
    cmd.add_drop("Gem of Nulgath")
    await farm_contract_exchage(cmd, "Gem of Nulgath", quant)
    if await cmd.has_item(CRAG_PET):
        await supplies(cmd, "Gem of Nulgath", quant,
                       return_item="Gem of Nulgath")
    await void_knight_sword_quest(cmd, "Gem of Nulgath", quant)
    await supplies(cmd, "Gem of Nulgath", quant, return_item="Gem of Nulgath")


async def farm_blood_gem(cmd: Command, quant: int = 100,
                         hydra_level: int = 85) -> None:
    """Blood Gem of the Archfiend, by every route the account can take."""
    if await cmd.has_item("Blood Gem of the Archfiend", quant):
        return
    cmd.add_drop("Blood Gem of the Archfiend")
    await farm_contract_exchage(cmd, "Blood Gem of the Archfiend", quant)
    await new_worlds_new_opportunities(cmd, "Blood Gem of the Archfiend", quant)
    await void_knight_sword_quest(cmd, "Blood Gem of the Archfiend", quant)
    await bloody_chaos(cmd, quant, relic=True, hydra_level=hydra_level)
    await kissthe_void(cmd, quant)


async def farm_tainted_gem(cmd: Command, quant: int = 1000) -> None:
    """Tainted Gem, by every route the account can take.

    The Forge route (quest 4919) needs membership and the Gemstone of Nulgath,
    so it refuses by itself when either is missing; the rest runs regardless.
    """
    if await cmd.has_item("Tainted Gem", quant):
        return
    cmd.add_drop("Tainted Gem")
    await farm_contract_exchage(cmd, "Tainted Gem", quant)
    if await cmd.has_item(CRAG_PET):
        await supplies(cmd, "Tainted Gem", quant, return_item="Tainted Gem")
    await forge_tainted_gems(cmd, quant)
    await supplies(cmd, "Tainted Gem", quant, return_item="Tainted Gem")


async def farm_totem_of_nulgath(cmd: Command, quant: int = 100) -> None:
    """Totem of Nulgath: Deal first, then Taro's chain as the fallback."""
    if await cmd.has_item("Totem of Nulgath", quant):
        return
    await deal(cmd, gem_quant=0, totem_quant=quant)
    await new_worlds_new_opportunities(cmd, "Totem of Nulgath", quant)
    await totems_via_taros(cmd, quant)


async def farm_voucher(cmd: Command, member: bool, keep_voucher: bool = False
                       ) -> None:
    """Voucher of Nulgath, member or non-member variant by the flag."""
    name = "Voucher of Nulgath" if member else "Voucher of Nulgath (non-mem)"
    if await cmd.has_item(name):
        return
    cmd.add_drop(name)
    cmd.bot.log(f"[nation] keep voucher set to {keep_voucher}")

    if await has_obon_pet(cmd) or await cmd.has_item(CRAG_PET):
        await bamboozle_vs_drudge(cmd, name, 1, keep_voucher=keep_voucher,
                                  came_from_supplies=True)
    await new_worlds_new_opportunities(cmd, name)
    await void_knight_sword_quest(cmd, name)
    await supplies(cmd, name, keep_voucher=keep_voucher)


async def farm_fiend_token(cmd: Command, quant: int = 30) -> None:
    """Fiend Token, by the three routes the C# tries in order."""
    if await cmd.has_item("Fiend Token", quant):
        return
    await void_knight_sword_quest(cmd, "Fiend Token", quant)
    await assisting_drudgen(cmd, "Fiend Token", quant)
    await feed_the_fiend(cmd)


async def dragon_slayer_reward(cmd: Command) -> None:
    """Unlock the Nation mats by clearing the Lair chain (quests 165-169).

    ``Core.HuntMonsterQuest`` is what ``kill_quest`` already is: accept, hunt
    the monster, turn in.
    """
    if await cmd.is_completed_before(169):
        return

    for quest_id, monster, is_solo in DRAGON_SLAYER_QUESTS:
        if not cmd.is_still_connected():
            return
        if await cmd.is_completed_before(quest_id):
            continue
        await equip_class(cmd, solo=is_solo)
        await kill_quest(cmd, quest_id, "lair", monster)


async def deal(cmd: Command, gem_quant: int = 0, totem_quant: int = 0) -> None:
    """Quest 4777: Gems and/or Totems of Nulgath, Crag pet only."""
    if not await cmd.has_item(CRAG_PET):
        cmd.bot.log(f"[nation] missing {CRAG_PET}; cannot continue.")
        return

    await dragon_slayer_reward(cmd)
    if not await get_pcod(cmd):
        return
    cmd.add_drop(["Gem of Nulgath", "Totem of Nulgath"])

    async def farm_one(item_name: str, quant: int, reward_id: int) -> None:
        if quant <= 0:
            return
        cmd.farming_logger(item_name, quant)
        while (cmd.is_still_connected()
               and not await cmd.has_item(item_name, quant)):
            await cmd.ensure_accept_quest(4777)
            await supplies(cmd, "Unidentified 3",
                           return_item="Blood Gem of the Archfiend")
            await farm_blood_gem(cmd, 2)
            await farm_uni10(cmd, 30)
            await cmd.ensure_turn_in_quest(4777, reward_id)

    await farm_one("Gem of Nulgath", gem_quant, GEM_OF_NULGATH)
    await farm_one("Totem of Nulgath", totem_quant, TOTEM_OF_NULGATH)


async def assisting_drudgen(cmd: Command, item: str = "Any",
                            quant: int = 1) -> None:
    """Quest 5816 (and the daily 3826) for Fiend Tokens.

    Needs ``Drudgen the Assistant``, ``Twin Blade of Nulgath`` and membership.

    Note:
        The C# calls ``Bot.Quests.UpdateQuest(3824)``, which writes a quest
        slot value on the client to unlock the next link.  That has no
        counterpart here, so it is skipped: the following ``IsAvailable`` check
        is reproduced by trying to accept 3826 and seeing whether it lands.
    """
    if (await cmd.has_item(item, quant)
            or not await cmd.has_item("Drudgen the Assistant")
            or not await cmd.has_item("Twin Blade of Nulgath")
            or not cmd.get_player().is_member):
        return

    while cmd.is_still_connected() and not await cmd.has_item(item, quant):
        await cmd.ensure_accept_quest(5816)
        await hunt_item(cmd, "The Secret 1", 1, "willowcreek",
                        monster_name="Hidden Spy", is_temp=False)
        await essence_of_nulgath(cmd, 20)
        await approval_and_favor(cmd, 50, 50)
        await hunt_item(cmd, "Cubes", 50, "boxes", cell="Fort2", pad="Left",
                        monster_name="*", is_temp=False)
        await hunt_item(cmd, "Fiend Seal", 10, "shadowblast", cell="r13",
                        pad="Left", monster_name="*", is_temp=False)

        await cmd.ensure_accept_quest(3826)
        if cmd.get_loaded_quest(3826) is not None and not await cmd.has_item_id(25026):
            await hunt_item(cmd, "Seal of Light", 1, "alteonbattle",
                            monster_name="Ultra Chaos Alteon", is_temp=True)
            await cmd.ensure_turn_in_quest(3826)
        else:
            cmd.bot.log("[nation] the Seal of Light daily (3826) is not available.")
        await cmd.ensure_turn_in_quest(5816)


async def feed_the_fiend(cmd: Command, item: str = "Fiend Token",
                         quant: int = 30) -> None:
    """Quest 3053, members only, for Fiend Tokens."""
    if await cmd.has_item(item, quant) or not cmd.get_player().is_member:
        return
    cmd.add_drop(item)
    await cmd.register_quest(3053)
    await equip_class(cmd, solo=True)

    while cmd.is_still_connected() and not await cmd.has_item(item, quant):
        await farm_diamond_of_nulgath(cmd, 1)
        await hunt_item(cmd, "Dragon Fiend Gem", 13, "lair",
                        monster_name="Red Dragon", is_temp=False)
        await hunt_item(cmd, "Glacial Bones", 3, "battleunderd",
                        cell="r5", pad="Left", monster_name="Glacial Horror",
                        is_temp=False)
        await hunt_item(cmd, "Screamfeeder Heart", 1, "dreammaze",
                        monster_name="Screamfeeder", is_temp=False)

    cmd.cancel_registered_quests()


async def totems_via_taros(cmd: Command, quant: int = 100) -> None:
    """Totem of Nulgath via Taro's chain (quest 726)."""
    if await cmd.has_item("Totem of Nulgath", quant):
        return

    if (cmd.get_player().is_member
            and not await cmd.has_item("Purified Claymore of Destiny")):
        cmd.bot.log("[nation] member route needs the Purified Claymore first.")
        # the C# runs Farm.GoodREP() before GetPCoD(), which needs the same rank
        await farm_faction(cmd, "Good")
        if not await get_pcod(cmd):
            return

    cmd.add_drop("Totem of Nulgath")
    if (cmd.is_still_connected()
            and not await cmd.is_completed_before(9541)):
        # the C# calls ChainComplete(9541) here: accept it, then complete it
        await cmd.ensure_accept_quest(9541)
        await cmd.ensure_turn_in_quest(9541)

    while cmd.is_still_connected() and not await cmd.has_item("Totem of Nulgath", quant):
        await cmd.ensure_accept_quest(726)
        await essence_of_nulgath(cmd, 25)
        if (cmd.get_player().is_member
                and not await cmd.has_item_id(538)):
            await cmd.ensure_accept_quest(1111)
            await farm_gem_of_nulgath(cmd, 10)
            await dark_makai_item(cmd, "Dark Makai Rune")
            await cmd.ensure_turn_in_quest(1111, 538)
        else:
            await equip_class(cmd, solo=True)
            await hunt_item(cmd, "Taro's Manslayer", 1, "tercessuinotlim",
                            monster_name="Taro Blademaster", is_temp=False)
        await cmd.ensure_turn_in_quest(726)

    cmd.cancel_registered_quests()


async def kissthe_void(cmd: Command, quant: int = 100,
                       betrayal_blade: Optional[str] = None,
                       keep_voucher: bool = False,
                       return_policy: bool = False) -> None:
    """Quest 3743: Blood Gems, or one of the Betrayal Blades."""
    watching = betrayal_blade or "Blood Gem of the Archfiend"
    if await cmd.has_item(watching, quant if betrayal_blade is None else 1):
        return

    cmd.add_drop([watching, "Fragment of Chaos", "Blood Gem of the Archfiend",
                  "Broken Betrayal Blade"])
    await equip_class(cmd)
    cmd.farming_logger(watching, quant if betrayal_blade is None else 1)
    cmd.add_drop(SUPPLIES_REWARDS)
    cmd.add_drop("Relic of Chaos")
    await cmd.register_quest(2857)

    while (cmd.is_still_connected()
           and not await cmd.has_item(watching,
                                       quant if betrayal_blade is None else 1)):
        await cmd.ensure_accept_quest(3743)
        if not await cmd.has_item("Tendurrr The Assistant"):
            await hunt_item(cmd, "Tendurrr The Assistant", 1,
                            "tercessuinotlim", cell="m2", pad="Left",
                            monster_name="*", is_temp=False)
        await hunt_item(cmd, "Fragment of Chaos", 80, "blindingsnow",
                        cell="r17", pad="Left", monster_name="*",
                        is_temp=False)
        await hunt_item(cmd, "Broken Betrayal Blade", 8, "evilwarnul",
                        cell="r13", pad="Left", monster_name="Legion Fenrir",
                        is_temp=False)
        await cmd.ensure_turn_in_quest(3743)

        await sell_voucher_of_nulgath(cmd, keep_voucher, watching)
        if not await cmd.has_item("Blood Gem of the Archfiend", 100):
            await do_swindles_return_area(cmd, return_policy,
                                          "Blood Gem of the Archfiend")
        if (await cmd.has_item("Voucher of Nulgath (non-mem)")
                and await cmd.has_item("Essence of Nulgath", 60)
                and (not await cmd.has_item("Diamond of Nulgath", 1000)
                     or not await cmd.has_item("Totem of Nulgath", 100))):
            diamonds_first = not await cmd.has_item("Diamond of Nulgath", 1000)
            await cmd.ensure_turn_in_quest(
                VOUCHER_CONVERSION_QUEST,
                GEM_OF_NULGATH if diamonds_first else TOTEM_OF_NULGATH,
                1000 if diamonds_first else 100)

        if betrayal_blade is None:
            cmd.farming_logger(watching, quant)


async def nation_round_4_medal(cmd: Command) -> None:
    """Clear the four Shadow Blast Arena medals (quests 4744-4747).

    Each medal is dropped from the pickup whitelist once earned, which is what
    the C# does with ``Bot.Drops.Remove``.
    """
    if await cmd.has_item("Nation Round 4 Medal"):
        cmd.bot.log("[nation] medal 4 owned, no need to farm it")
        return

    for medal, quest_id, steps in NATION_MEDALS:
        if not cmd.is_still_connected():
            return
        cmd.add_drop(medal)
        if await cmd.has_item(medal):
            cmd.bot.log(f'[nation] "{medal}" owned.')
            continue
        await cmd.ensure_accept_quest(quest_id)
        for monster, item, qty in steps:
            await hunt_item(cmd, item, qty, "shadowblast",
                            monster_name=monster, is_temp=True)
        await cmd.ensure_turn_in_quest(quest_id)
        cmd.bot.log(f"[nation] medal {medal} acquired")
        cmd.remove_drop(medal)


async def emblem_of_nulgath(cmd: Command, quant: int = 500) -> None:
    """Quest 4748, after the four medals are done.

    Note:
        The C# never cancels the registered quest here, and neither does this:
        the auto-quest task re-accepting 4748 is what keeps the loop fed.  The
        loop ends when the emblem hits ``quant``, not when the task stops.
    """
    if await cmd.has_item("Emblem of Nulgath", quant):
        return
    await nation_round_4_medal(cmd)

    cmd.add_drop(["Fiend Seal", "Gem of Domination", "Emblem of Nulgath"])
    cmd.add_drop(BAG_DROPS)
    await equip_class(cmd)
    cmd.farming_logger("Emblem of Nulgath", quant)
    await cmd.register_quest(4748)

    while (cmd.is_still_connected()
           and not await cmd.has_item("Emblem of Nulgath", quant)):
        await hunt_item(cmd, "Gem of Domination", 1, "shadowblast",
                        monster_name="Shadowrise Guard", is_temp=False)
        # The reference has both routes for this item; the cell one is the one
        # that works here, because this engine has no Flash monster list to walk
        # to a name with: ``KillMonster("shadowblast", "r13", "Left", "*",
        # "Fiend Seal", 10, false)``.
        await hunt_item(cmd, "Fiend Seal", 25, "shadowblast", cell="r13",
                        pad="Left", monster_name="*", is_temp=False)


async def swindle_return(cmd: Command, item: Optional[str] = None,
                         quant: int = 1000) -> None:
    """Quest 7551 (Swindle's Return Policy) for one of its rewards.

    Each pass feeds the quest five Unidentifieds through the Supplies route,
    then the Dark Makai Rune, then turns it in for ``item``.
    """
    await cmd.ensure_accept_quest(7551)
    quest = cmd.get_loaded_quest(7551)
    if _quest_rewards_or_warn(cmd, 7551, quest) is None:
        return

    if item is None:
        # the C# script picks this from its options and, with none set, does
        # nothing at all -- the first reward that is not maxed is taken instead
        # so the run is not a silent no-op
        entry = await first_missing(cmd, quest.reward_entries)
    else:
        entry = next((e for e in quest.reward_entries if e[1] == item), None)
    if entry is None or await cmd.has_item(entry[1], quant):
        return
    _, item_name, _ = entry

    cmd.add_drop(RECEIPT_DROPS)
    cmd.add_drop(item_name)
    cmd.farming_logger(item_name, quant)

    while cmd.is_still_connected() and not await cmd.has_item(item_name, quant):
        await cmd.ensure_accept_quest(7551)
        for uni_nr in (1, 6, 9, 16, 20):
            await supplies(cmd, uni(uni_nr), return_item=item)
        await dark_makai_item(cmd, "Dark Makai Rune")
        await cmd.ensure_turn_in_quest(7551, entry[0])
        await sell_voucher_of_nulgath(cmd, False, item)
        cmd.farming_logger(item_name, quant)


async def swindle_bulk(cmd: Command, quant: int = 1000) -> None:
    """Tainted Gem through Swindle's Bulk Deal.

    Which quest it uses depends on the target: a multiple of 25 buys the big
    quest (7817) and its 500-cube run, anything else the small one (569).
    """
    if await cmd.has_item("Tainted Gem", quant):
        return

    await equip_class(cmd)
    cmd.farming_logger("Tainted Gem", quant)

    bulk = quant % 25 == 0
    quest_id = 7817 if bulk else 569
    cube_count = 500 if bulk else 25
    snow_count = 6 if bulk else 1

    cmd.add_drop(["Cubes", "Tainted Gem"])
    cmd.add_drop(BAG_DROPS)

    attempt = 0
    while cmd.is_still_connected() and not await cmd.has_item("Tainted Gem", quant):
        await cmd.ensure_accept_quest(quest_id)
        await hunt_item(cmd, "Cubes", cube_count, "boxes",
                        cell="Fort2", pad="Left", monster_name="*",
                        is_temp=False)
        await hunt_item(cmd, "Ice Cubes", snow_count, "mountfrost",
                        cell="War", pad="Left", monster_name="Snow Golem",
                        is_temp=True)
        await cmd.ensure_turn_in_quest(quest_id)
        attempt += 1
        cmd.bot.log(f"[nation] completed x{attempt}")


async def dreadrock_gem_exchange(cmd: Command, quant: int = 1000) -> None:
    """Quest 4853: Tainted Gems from the dreadrock mobs."""
    if await cmd.has_item("Tainted Gem", quant):
        return
    await farm_uni13_quest(cmd, 1)
    cmd.add_drop("Tainted Gem")
    await equip_class(cmd)
    cmd.farming_logger("Tainted Gem", quant)
    await cmd.register_quest(4853)
    await hunt_item(cmd, "Tainted Gem", quant, "dreadrock",
                    cell="r3", pad="Bottom", monster_name="*", is_temp=True)
    cmd.cancel_registered_quests()


async def _larvae_step(cmd: Command, item: str, quant: int) -> None:
    """One Larvae turn-in cycle, plus the voucher quest when it applies."""
    await cmd.ensure_accept_quest(LARVAE_QUEST)
    await equip_class(cmd, solo=True)
    await hunt_item(cmd, MANA_ENERGY, 10, "elemental",
                    monster_name="Mana Golem", is_temp=False)
    await equip_class(cmd)

    while (cmd.is_still_connected()
           and not await cmd.has_item(item, quant)
           and await cmd.has_item(MANA_ENERGY)):
        await cmd.ensure_accept_quest(LARVAE_QUEST)
        await hunt_item(cmd, CHARGED_MANA_ENERGY, 5, "elemental",
                        monster_name="Mana Falcon", is_temp=True)
        await cmd.ensure_turn_in_quest(LARVAE_QUEST)

        if (await cmd.has_item("Voucher of Nulgath (non-mem)")
                and await cmd.has_item("Essence of Nulgath", 60)):
            await cmd.ensure_accept_quest(VOUCHER_CONVERSION_QUEST)
            reward_id = _reward_id(cmd, VOUCHER_CONVERSION_QUEST, item)
            if reward_id >= 0:
                await cmd.ensure_turn_in_quest(VOUCHER_CONVERSION_QUEST,
                                               reward_id)


async def nulgath_larvae(cmd: Command, item: Optional[str] = None,
                         quant: int = 1) -> None:
    """Quest 2566 (Nulgath Larvae): Mana Energy in, its rewards out.

    With ``item`` it farms that one reward; without it, every reward that is
    not maxed yet.
    """
    await cmd.ensure_accept_quest(LARVAE_QUEST)
    larvae = cmd.get_loaded_quest(LARVAE_QUEST)
    if item and await cmd.has_item(item, quant):
        return
    names = _quest_rewards_or_warn(cmd, LARVAE_QUEST, larvae)
    if names is None:
        return

    if item is not None:
        if item not in names:
            cmd.bot.log(f"[nation] {item!r} is not a Nulgath Larvae reward.")
            return
        targets = [(item, quant)]
    else:
        targets = [(name, stack) for _, name, stack in larvae.reward_entries
                   if not await cmd.has_item(name, stack)]

    for name, target in targets:
        cmd.add_drop([MANA_ENERGY, name])
        cmd.farming_logger(name, target)
        while cmd.is_still_connected() and not await cmd.has_item(name, target):
            await _larvae_step(cmd, name, target)


async def nulgaths_roulette_of_misfortune(cmd: Command, item: Optional[str],
                                          quant: int) -> None:
    """The same Larvae loop, without the voucher-quest side trip."""
    if item is None:
        cmd.bot.log("[nation] nulgaths_roulette_of_misfortune needs the item name "
              "(the C# takes it as a parameter too); nothing farmed.")
        return
    if await cmd.has_item(item, quant):
        return
    cmd.farming_logger(item, quant)
    cmd.add_drop(item)

    while cmd.is_still_connected() and not await cmd.has_item(item, quant):
        await cmd.ensure_accept_quest(LARVAE_QUEST)
        await equip_class(cmd, solo=True)
        await hunt_item(cmd, MANA_ENERGY, 10, "elemental",
                        monster_name="Mana Golem", is_temp=False)
        await equip_class(cmd)

        while (cmd.is_still_connected()
               and not await cmd.has_item(item, quant)
               and await cmd.has_item(MANA_ENERGY)):
            await cmd.ensure_accept_quest(LARVAE_QUEST)
            await hunt_item(cmd, CHARGED_MANA_ENERGY, 5, "elemental",
                            monster_name="Mana Falcon", is_temp=True)
            await cmd.ensure_turn_in_quest(LARVAE_QUEST)


async def _assistant_step(cmd: Command, item: Optional[str],
                          reward: Optional[str], return_policy: bool) -> None:
    """One Assistant turn-in: buy 10 memorabilia, hand them over, then tidy up."""
    await cmd.ensure_accept_quest(2859)
    await buy_item(cmd, 41, "War-Torn Memorabilia", 10, map_name="yulgar")
    await cmd.ensure_turn_in_quest(2859)
    await do_swindles_return_area(cmd, return_policy, reward)
    await handle_voucher_conversions(cmd, item or "")


async def the_assistant(cmd: Command, item: Optional[str] = None,
                        quant: int = 1000, farm_gold: bool = True,
                        reward: Optional[str] = None,
                        return_policy: bool = False) -> None:
    """Quest 2859 (The Assistant), fed with War-Torn Memorabilia.

    With ``item`` it farms that reward up to ``quant``; without it, every
    principal drop the quest offers.

    Args:
        item: Reward to farm, or ``None`` for all of them.
        quant: Target quantity; clamped to the reward's max stack.
        farm_gold: Whether to keep a Gold farm topped up first.
        reward: Which quest 7551 reward to take, by name.  The valid names are
            Tainted Gem, Dark Crystal Shard, Diamond of Nulgath, Gem of
            Nulgath and Blood Gem of the Archfiend.  ``None`` leaves the
            Swindle's Return step out entirely, as the C# ``None`` enum does.
        return_policy: Run the Swindle's Return step on each pass.

    Note:
        The C#'s ``LogMobItemQuant`` helpers are skipped: they only log, and each
        costs a 1.5 s sleep.
    """
    if item and await cmd.has_item(item, quant):
        return

    await cmd.ensure_accept_quest(7551)
    if cmd.get_loaded_quest(7551) is None:
        cmd.bot.log("[nation] quest 7551 (Swindle's Return Policy) did not load.")
        return
    await cmd.ensure_accept_quest(2859)
    assistant = cmd.get_loaded_quest(2859)
    if _quest_rewards_or_warn(cmd, 2859, assistant) is None:
        return

    cmd.add_drop([item] if item else list(BAG_DROPS_PRINCIPAL))
    cmd.add_drop("Receipt of Swindle")
    if reward:
        cmd.add_drop(reward)
    if return_policy:
        cmd.add_drop([uni(1), uni(6), uni(9), uni(16), uni(20)])
        cmd.add_drop("Blood Gem of the Archfiend")

    if item and quant > 0:
        entry = next((e for e in assistant.reward_entries if e[1] == item), None)
        if entry is None:
            cmd.bot.log(f"[nation] {item!r} is not one of quest 2859's rewards.")
        else:
            quant = min(quant, entry[2])

    if return_policy and reward:
        await do_swindles_return_area(cmd, return_policy, reward)

    if farm_gold and cmd.get_player().GOLD < 1_000_000:
        # the reference's Farm.Gold(1000000) before the memorabilia buy
        await farm_gold(cmd, 1_000_000)

    if item is None:
        for thing in BAG_DROPS_PRINCIPAL:
            entry = next((e for e in assistant.reward_entries if e[1] == thing),
                         None)
            if entry is None:
                continue
            _, name, max_stack = entry
            cmd.farming_logger(name, max_stack)
            while (cmd.is_still_connected()
                   and not await cmd.has_item(name, max_stack)):
                await _assistant_step(cmd, None, reward, return_policy)
        cmd.cancel_registered_quests()
    else:
        cmd.farming_logger(item, quant)
        while cmd.is_still_connected() and not await cmd.has_item(item, quant):
            await _assistant_step(cmd, item, reward, return_policy)

    if return_policy and reward:
        cmd.unregister_quest(7551)


async def voucher_item_totem_of_nulgath(cmd: Command,
                                        reward: str = "Totem of Nulgath",
                                        quant: int = 0) -> None:
    """Trade spare Vouchers for Totems or Gems of Nulgath (quest 4778).

    ``quant = 0`` means the reward's usual cap: 100 for the totem, 1000 for the
    gem, matching the C#.
    """
    if not await cmd.has_item("Voucher of Nulgath (non-mem)"):
        await farm_voucher(cmd, False, keep_voucher=True)

    reward_id = VOUCHER_ITEM_REWARDS.get(reward.lower())
    if reward_id is None:
        cmd.bot.log(f"[nation] {reward!r} is not one of quest 4778's rewards "
              f"({', '.join(VOUCHER_ITEM_REWARDS)}).")
        return
    if quant == 0:
        quant = 100 if reward_id == TOTEM_OF_NULGATH else 1000

    await cmd.ensure_accept_quest(VOUCHER_CONVERSION_QUEST)
    entries = cmd.get_quest_reward_entries(VOUCHER_CONVERSION_QUEST)
    entry = next((e for e in entries if e[0] == reward_id), None)
    if entry is None:
        cmd.bot.log(f"[nation] quest {VOUCHER_CONVERSION_QUEST} did not report "
              f"{reward!r} as a reward; nothing farmed.")
        return
    _, name, _ = entry

    cmd.add_drop(name)
    cmd.farming_logger(name, quant)

    while cmd.is_still_connected() and not await cmd.has_item(name, quant):
        await cmd.ensure_accept_quest(VOUCHER_CONVERSION_QUEST)
        await essence_of_nulgath(cmd)
        # the C# retries the turn-in with a fresh batch of essence when the
        # first attempt reports it cannot complete; can_turnin_quest is the
        # local equivalent of that answer
        if not cmd.can_turnin_quest(VOUCHER_CONVERSION_QUEST):
            have = cmd.get_quant_item("Essence of Nulgath")
            await essence_of_nulgath(cmd, have + 1 if have < 100 else 60)
        await cmd.ensure_turn_in_quest(VOUCHER_CONVERSION_QUEST, reward_id)


async def empowering_items(cmd: Command) -> None:
    """Quest 558 for the Death Scythe of Nulgath.

    Port of ``Nation/EmpoweringItems.cs``, whose logic lives in the script
    itself rather than in the shared class.
    """
    if await cmd.has_item("Death Scythe of Nulgath"):
        return

    cmd.add_drop("Death Scythe of Nulgath")
    await cmd.ensure_accept_quest(558)
    await farm_uni13_quest(cmd, 1)
    await farm_diamond_of_nulgath(cmd, 10)

    if not await cmd.has_item_id(4867):
        await cmd.ensure_accept_quest(623)
        await farm_uni13_quest(cmd, 1)
        await hunt_item(cmd, "The Secret 1", 1, "willowcreek",
                        monster_name="Hidden Spy", is_temp=False)
        await cmd.ensure_turn_in_quest(623)

    await hunt_item(cmd, "Undead Bruiser Sigil", 1, "underworld",
                    monster_name="Undead Bruiser", is_temp=True)
    await cmd.ensure_turn_in_quest(558)


async def time_is_money(cmd: Command) -> None:
    """Quest 6185 rewards, one at a time up to each one's max stack.

    Port of ``Nation/TimeIsMoney.cs``.  Needs the Bounty Hunter Blade Pet
    (item 42581); without it the quest cannot be taken at all.
    """
    if not await cmd.has_item_id(42581):
        cmd.bot.log("[nation] Time is Money needs the Bounty Hunter Blade Pet "
              "(item 42581); nothing farmed.")
        return

    await cmd.ensure_accept_quest(6185)
    entries = cmd.get_quest_reward_entries(6185)
    if not entries:
        _quest_rewards_or_warn(cmd, 6185, cmd.get_loaded_quest(6185))
        return

    cmd.add_drop([name for _, name, _ in entries])

    for _, name, max_stack in entries:
        if await cmd.has_item(name, max_stack):
            cmd.bot.log(f"[nation] {name} is at max stack; checking the next reward.")
            continue
        while (cmd.is_still_connected()
               and not await cmd.has_item(name, max_stack)):
            await cmd.ensure_accept_quest(6185)
            await join_swf(cmd, "mobius", "Slugfit", "Bottom")
            await hunt_item(cmd, "Slugfit Horn", 5, "mobius",
                            cell="Slugfit", pad="Bottom",
                            monster_name="Slugfit", is_temp=True)
            await hunt_item(cmd, "Imp Flame", 3, "mobius",
                            monster_name="Fire Imp", is_temp=True)
            await hunt_item(cmd, "Tanuki Ears", 3, "bamboo",
                            monster_name="Tanuki", is_temp=True)
            await hunt_item(cmd, "Wereboar Tusk", 2, "greenguardwest",
                            cell="West12", pad="Up",
                            monster_name="Big Bad Boar", is_temp=True)
            await hunt_item(cmd, "Onibaba Nails", 5, "junkyard",
                            monster_name="Onibaba", is_temp=True)
            await cmd.ensure_turn_in_quest(6185)


async def _nlr(cmd: Command, items: Sequence[str], quantity: int) -> None:
    """One Nation Loyalty Rewarded cycle for ``items``."""
    if not items or await all_owned(cmd, [(name, quantity) for name in items]):
        cmd.bot.log(f"[nation] {', '.join(items) or 'nothing'} x{quantity} already "
              f"held; skipping.")
        return

    for name in items:
        cmd.farming_logger(name, quantity)
    await equip_class(cmd, solo=True)

    while (cmd.is_still_connected()
           and not await all_owned(cmd, [(name, quantity) for name in items])):
        await cmd.ensure_accept_quest(4749)
        await _kill_once(cmd, "dflesson", "r12", "Right", "id.29")
        await hunt_item(cmd, "Carnax Eye", 1, "aqlesson",
                        monster_name="Carnax", is_temp=True)
        await hunt_item(cmd, "Kathool Tentacle", 1, "deepchaos",
                        monster_name="Kathool", is_temp=True)
        await hunt_item(cmd, "Red Dragon's Fang", 1, "lair",
                        monster_name="Red Dragon", is_temp=True)
        await hunt_item(cmd, "Blood Titan's Blade", 1, "bloodtitan",
                        monster_name="Blood Titan", is_temp=True)
        await equip_class(cmd)
        await hunt_item(cmd, "Defeated Makai", 25, "tercessuinotlim",
                        cell="m2", pad="Left", monster_name="*",
                        is_temp=False)
        await cmd.ensure_turn_in_quest(4749)


async def nation_loyalty_rewarded(cmd: Command,
                                  farm_items: Optional[Sequence[str]] = None,
                                  quantity: int = 0) -> None:
    """Quest 4749 (Nation Loyalty Rewarded).

    With no ``farm_items`` it walks every reward the quest offers, each up to
    its own max stack; with a list it farms just those.
    """
    await cmd.ensure_accept_quest(4749)
    entries = cmd.get_quest_reward_entries(4749)
    if not entries:
        _quest_rewards_or_warn(cmd, 4749, cmd.get_loaded_quest(4749))
        return

    if not farm_items:
        for _, name, max_stack in entries:
            await _nlr(cmd, [name], quantity or max_stack)
        return

    cmd.add_drop(list(farm_items))
    await nation_round_4_medal(cmd)
    await farm_uni13_quest(cmd, 1)

    for name in farm_items:
        entry = next((e for e in entries if e[1] == name), None)
        if entry is None:
            cmd.bot.log(f"[nation] {name!r} is not a quest 4749 reward.")
            continue
        if await cmd.has_item(name, entry[2]):
            continue
        await _nlr(cmd, [name], quantity or entry[2])


async def assisting_crag_and_bamboozle(cmd: Command,
                                       reward_id: Optional[int] = None) -> None:
    """Quest 5817 daily rewards, using the Crag & Bamboozle pet.

    ``reward_id`` picks one reward by item id; ``None`` takes every one that is
    not maxed, as the C# ``Get_whats_not_maxed`` option does.

    Note:
        The C# also *runs* the daily that supplies Sparrow's Blood (quest 803,
        through ``CoreDailies``).  That daily is not ported, so this only works
        from Sparrow's Blood you already hold, and says so instead of looping
        against a quest it cannot feed.
    """
    if not cmd.get_player().is_member or not await cmd.has_item(CRAG_PET):
        return
    if not await cmd.has_item("Sparrow's Blood"):
        cmd.bot.log("[nation] Assisting Crag & Bamboozle is fed by the Sparrow's "
              "Blood daily (quest 803), which is CoreDailies work that is not "
              "ported. Hold Sparrow's Blood first and re-run.")
        return

    await cmd.ensure_accept_quest(5817)
    entries = cmd.get_quest_reward_entries(5817)
    if not entries:
        _quest_rewards_or_warn(cmd, 5817, cmd.get_loaded_quest(5817))
        return

    targets = [e for e in entries
               if not await cmd.has_item(e[1], e[2])
               and (reward_id is None or e[0] == reward_id)]
    if not targets:
        cmd.bot.log("[nation] everything already maxed; no work needed.")
        return

    cmd.add_drop(ACAB_DROPS)
    cmd.bot.log(f"[nation] AssistingCandB targets: {len(targets)}")

    while cmd.is_still_connected() and targets:
        await cmd.ensure_accept_quest(5817)

        if not await cmd.has_item("Tendurrr The Assistant"):
            await hunt_item(cmd, "Tendurrr The Assistant", 1,
                            "tercessuinotlim", cell="m2", pad="Left",
                            monster_name="*", is_temp=False)
        if not await cmd.has_item("Sparrow's Blood"):
            cmd.bot.log("[nation] missing Sparrow's Blood. Stopping.")
            return

        await essence_of_nulgath(cmd, 20)
        await approval_and_favor(cmd, 100, 100)
        await nation_round_4_medal(cmd)
        await cmd.ensure_accept_quest(4748)
        await hunt_item(cmd, "Fiend Seal", 10, "shadowblast",
                        monster_name="Legion Fenrir", is_temp=False)

        finished = []
        for item_id, name, max_stack in targets:
            if await cmd.has_item(name, max_stack):
                finished.append(item_id)
                continue
            await cmd.ensure_turn_in_quest(5817, item_id)
            if await cmd.has_item(name, max_stack):
                finished.append(item_id)
            if not await cmd.has_item("Sparrow's Blood"):
                cmd.bot.log(f"[nation] stopped early after completing {name}")
                return

        targets = [t for t in targets if t[0] not in finished]

    cmd.bot.log("[nation] AssistingCandB complete.")


# ----------------------------------------------------------------------------
# The member Forge chain (quests 4917-4924)
# ----------------------------------------------------------------------------

def _forge_ready(cmd: Command, what: str, strict: bool) -> bool:
    """The reference's own Forge guard, both readings of it kept.

    ``CoreFarms``-style guards for the Forge chain require membership and the
    Gemstone of Nulgath, but the reference writes them two different ways:
    ``ForgeTaintedGems`` refuses when *either* is missing (``||``) while the
    other four refuse only when *both* are (``&&``).  ``strict`` picks which:
    True for the ``||`` guard, False for the ``&&`` one.

    Where the loose guard lets a farm start that the server will then refuse, the
    caller's loop is what notices -- see :func:`_forge_gem`.
    """
    member = bool(cmd.get_player().is_member)
    has_gemstone = cmd.is_in_inventory(GEMSTONE_OF_NULGATH)
    if strict:
        if not member:
            cmd.bot.log(f"[nation] {what} needs membership; nothing farmed.")
            return False
        if not has_gemstone:
            cmd.bot.log(f"[nation] {what} needs {GEMSTONE_OF_NULGATH!r}; nothing "
                  f"farmed.")
            return False
        return True

    if not member and not has_gemstone:
        cmd.bot.log(f"[nation] {what} needs membership and "
              f"{GEMSTONE_OF_NULGATH!r} -- it has neither; nothing farmed.")
        return False
    return True


async def dwobo_coin(cmd: Command, quant: int) -> None:
    """``CoreNation.DwoboCoin``: quest 4798 for members, 4797 without.

    Only the receipt chain asks for it, and the quest is open to everyone, so
    unlike its neighbours it has no membership guard of its own.
    """
    if await cmd.has_item("Dwobo Coin", quant):
        return

    member = bool(cmd.get_player().is_member)
    treasure, tech = (8, 5) if member else (10, 7)
    cmd.bot.log(f"[nation] farming {quant} Dwobo Coins (quest "
          f"{4798 if member else 4797})")
    cmd.farming_logger("Dwobo Coin", quant)
    await cmd.register_quest(4798 if member else 4797)
    cmd.add_drop("Dwobo Coin")

    while cmd.is_still_connected() and not await cmd.has_item("Dwobo Coin", quant):
        await hunt_item(cmd, "Ancient Treasure", treasure, "crashruins",
                        cell="r2", pad="Left", monster_name="Unlucky Explorer",
                        is_temp=False)
        await hunt_item(cmd, "Pieces of Future Tech", tech, "crashruins",
                        cell="r2", pad="Left", monster_name="Spacetime Anomaly",
                        is_temp=False)
        await hunt_item(cmd, "Idol Heart", 1, "crashruins",
                        monster_name="Cluckmoo Idol", is_temp=False)

    cmd.cancel_registered_quests()


async def gem_stone_receipt_of_nulgath(cmd: Command, quant: int = 10) -> None:
    """``CoreNation.GemStoneReceiptOfNulgath``: the Forge chain's currency.

    One pass runs two quests: 4924 hands over the ``Receipt of Nulgath`` the
    chain buys ``Blade of Affliction`` with, and 4917 turns everything gathered
    into the receipt item itself.
    """
    if not cmd.get_player().is_member:
        cmd.bot.log("[nation] Gemstone Receipt of Nulgath needs membership; nothing "
              "farmed.")
        return
    if await cmd.has_item(GEMSTONE_RECEIPT_OF_NULGATH, quant):
        return

    cmd.bot.log(f"[nation] farming {quant} {GEMSTONE_RECEIPT_OF_NULGATH} (quests 4917, "
          f"4924)")
    cmd.add_drop([GEMSTONE_RECEIPT_OF_NULGATH, RECEIPT_OF_NULGATH])

    while (cmd.is_still_connected()
           and not await cmd.has_item(GEMSTONE_RECEIPT_OF_NULGATH, quant)):
        await cmd.ensure_accept_quest(DEMANDING_APPROVAL_QUEST)

        await farm_uni13_quest(cmd, 3)
        await farm_faction(cmd, "Vampire")

        if not await cmd.has_item_id(RECEIPT_OF_NULGATH_ID):
            await dwobo_coin(cmd, 100)
            await buy_item(cmd, 1212, RECEIPT_OF_NULGATH,
                          map_name="crashedruins")

        await cmd.ensure_accept_quest(RECEIPT_OF_NULGATH_QUEST)
        await approval_and_favor(cmd, 0, 100)
        await equip_class(cmd)
        await hunt_item(cmd, "Coal", 15, "Extinction",
                        monster_name="Control Panel", is_temp=False)
        await dwobo_coin(cmd, 10)
        await essence_of_nulgath(cmd, 10)
        await farm_gold(cmd, 1_500_000)
        await buy_item(cmd, 68, "Blade of Affliction",
                          map_name="Tercessuinotlim")
        await cmd.ensure_turn_in_quest(RECEIPT_OF_NULGATH_QUEST)

        await farm_voucher(cmd, True, True)
        await farm_voucher(cmd, False, True)
        await essence_of_nulgath(cmd, 100)
        await farm_totem_of_nulgath(cmd, 1)
        await equip_class(cmd, solo=True)
        await hunt_item(cmd, "Ultimate Darkness Gem", 5, "ShadowfallWar",
                        monster_name="Bonemuncher", is_temp=False)
        await cmd.ensure_turn_in_quest(DEMANDING_APPROVAL_QUEST)


async def gem_stones_of_nulgath(cmd: Command, bloodstone: int = 100,
                                quartz: int = 100, tanzanite: int = 100,
                                uni_gemstone: int = 1) -> None:
    """``CoreNation.GemStonesOfnulgath``: quest 4918's counters.

    Unlocks quests 374 / 375 / 376 in ``/battleundera`` first when they are not
    done, because 4918 needs them.
    """
    if not _forge_ready(cmd, "Gemstones of Nulgath", strict=False):
        return

    wanted = [(name, qty) for name, qty in
              ((GEMSTONE_COUNTERS[0], bloodstone),
               (GEMSTONE_COUNTERS[1], quartz),
               (GEMSTONE_COUNTERS[2], tanzanite),
               (UNI_GEMSTONE_OF_NULGATH, uni_gemstone)) if qty > 0]
    if await all_owned(cmd, wanted):
        return

    await farm_uni13_quest(cmd, 1)
    await gem_stone_receipt_of_nulgath(cmd, 1)
    await supplies(cmd, "Unidentified 4")

    if not await cmd.is_completed_before(376):
        cmd.bot.log("[nation] unlocking quest 4918 (battleundera quests 374-376)")
        await equip_class(cmd)
        if not await cmd.is_completed_before(374):
            await cmd.ensure_accept_quest(374)
            await hunt_item(cmd, "Yara's Ring", 1, "battleundera",
                            monster_name="Skeletal Warrior", is_temp=False)
            await cmd.ensure_turn_in_quest(374)
        if not await cmd.is_completed_before(375):
            await cmd.ensure_accept_quest(375)
            await hunt_item(cmd, "Skeletal Claymore", 6, "battleundera",
                            monster_name="Skeletal Warrior", is_temp=False)
            await hunt_item(cmd, "Bony Chestplate", 3, "battleundera",
                            monster_name="Skeletal Warrior", is_temp=False)
            await cmd.ensure_turn_in_quest(375)
        if not await cmd.is_completed_before(376):
            await cmd.ensure_accept_quest(376)
            await hunt_item(cmd, "Bone Terror's Head", 1, "battleundera",
                            monster_name="Bone Terror", is_temp=False)
            await cmd.ensure_turn_in_quest(376)

    cmd.add_drop(list(GEMSTONE_COUNTERS)
                 + [UNI_GEMSTONE_OF_NULGATH, "Gem of Nulgath"])

    while cmd.is_still_connected() and not await all_owned(cmd, wanted):
        await cmd.ensure_accept_quest(GEMSTONES_FOR_NULGATH_QUEST)
        await equip_class(cmd, solo=True)
        await hunt_item(cmd, "Abbadon's Abide", 1, "Twilight",
                        monster_name="Abaddon", is_temp=False)
        await equip_class(cmd)
        await hunt_item(cmd, "Ultimate Darkness Gem", 1, "ShadowfallWar",
                        cell="Garden1", pad="Bottom", is_temp=False)
        await hunt_item(cmd, "Unidentified Weapon", 1, "battleundera",
                        cell="r3", pad="Left", is_temp=False)
        await cmd.ensure_turn_in_quest(GEMSTONES_FOR_NULGATH_QUEST)


async def _forge_gem(cmd: Command, what: str, quest_id: int, reward: str,
                     gem_of_nulgath: int, counters: Tuple[int, int, int, int],
                     quant: int, strict: bool) -> None:
    """One Forge quest: accept, gather, turn in, until ``reward`` is full.

    The four Forge routines differ only in these numbers and their guard, so they
    share this.  ``strict`` is the guard's flavour, as :func:`_forge_ready`
    explains.

    The reference loops on ``!Bot.ShouldExit`` alone, so a guard that let it
    through without the membership or the gemstone leaves it farming a quest the
    server refuses, forever.  The refusal is caught here instead -- the guard
    itself is untouched.
    """
    if not _forge_ready(cmd, what, strict):
        return
    if await cmd.has_item(reward, quant):
        return

    cmd.bot.log(f"[nation] forging {quant} {reward} (quest {quest_id})")
    await gem_stone_receipt_of_nulgath(cmd, 1)
    await supplies(cmd, "Unidentified 5")
    cmd.add_drop([reward, UNI_GEMSTONE_OF_NULGATH])

    while cmd.is_still_connected() and not await cmd.has_item(reward, quant):
        if not await cmd.ensure_accept_quest(quest_id):
            cmd.bot.log(f"[nation] quest {quest_id} cannot be accepted, so {reward} "
                  f"cannot be forged. Stopping.")
            return
        await farm_gem_of_nulgath(cmd, gem_of_nulgath)
        await gem_stones_of_nulgath(cmd, *counters)
        await cmd.ensure_turn_in_quest(quest_id)


async def forge_tainted_gems(cmd: Command, quant: int = 1000) -> None:
    """``CoreNation.ForgeTaintedGems``: quest 4919.

    Note:
        Its guard is the strict one -- membership *and* the Gemstone of Nulgath --
        which is how the reference writes this one, unlike its three siblings.
    """
    await _forge_gem(cmd, "Forge Tainted Gems", FORGE_TAINTED_GEMS_QUEST,
                     "Tainted Gem", 1, (0, 3, 1, 0), quant, strict=True)


async def forge_dark_crystal_shards(cmd: Command, quant: int = 1000) -> None:
    """``CoreNation.ForgeDarkCrystalShards``: quest 4920.

    Note:
        Two things are the reference's own and are kept verbatim: its guard is
        the loose one (``!gemstone && !member``), and its stop condition checks
        ``"Dark Crystal Shards"`` -- plural, which no item in the tree is named.
        The loop therefore runs until the bot is stopped, exactly as the
        reference does; the loop still reports a quest the server refuses.
    """
    await _forge_gem(cmd, "Forge Dark Crystal Shards",
                     FORGE_DARK_CRYSTAL_SHARDS_QUEST, "Dark Crystal Shards", 1,
                     (0, 5, 2, 0), quant, strict=False)


async def forge_diamonds_of_nulgath(cmd: Command, quant: int = 1000) -> None:
    """``CoreNation.ForgeDiamondsOfNulgath``: quest 4921.

    Note:
        The same loose guard as its sibling, and its stop condition checks
        ``"Diamonds for Nulgath"`` -- which appears nowhere else in the tree and
        is no item's name, so the loop runs until the bot is stopped, as in the
        reference.
    """
    await _forge_gem(cmd, "Forge Diamonds of Nulgath", FORGE_DIAMONDS_QUEST,
                     "Diamonds for Nulgath", 1, (0, 2, 0, 0), quant,
                     strict=False)


async def forge_blood_gems(cmd: Command, quant: int = 100) -> None:
    """``CoreNation.ForgeBloodGems``: quest 4922, with the loose guard."""
    await _forge_gem(cmd, "Forge Blood Gems", FORGE_BLOOD_GEMS_QUEST,
                     "Blood Gem of the Archfiend", 7, (3, 5, 0, 0), quant,
                     strict=False)


async def carve_uni_gem_stone(cmd: Command, item: Optional[str] = None,
                              quant: int = 1000) -> None:
    """``CoreNation.CarveUniGemStone``: quest 4923, for one reward or all.

    Note:
        With ``item=None`` the reference loops until the bot is stopped -- it
        turns the quest in for a reward it never names.  Here "all" means every
        one of quest 4923's rewards, so the run has a goal and an end.
    """
    if not cmd.get_player().is_member:
        cmd.bot.log("[nation] Carve the Unidentified Gemstone needs membership; "
              "nothing farmed.")
        return
    if item is not None and item not in CARVE_REWARD_IDS:
        cmd.bot.log(f"[nation] {item!r} is not one of quest 4923's rewards ("
              f"{', '.join(CARVE_REWARD_IDS)}).")
        return

    rewards = [item] if item else list(CARVE_REWARD_IDS)
    if await all_owned(cmd, [(name, quant) for name in rewards]):
        return

    await hunt_item(cmd, "Hadean Onyx of Nulgath", 1, "tercessuinotlim",
                    cell="m4", pad="Right", monster_name="Shadow of Nulgath",
                    is_temp=False)
    await gem_stone_receipt_of_nulgath(cmd, 1)
    await supplies(cmd, "Unidentified 5")
    cmd.add_drop(rewards)

    while (cmd.is_still_connected()
           and not await all_owned(cmd, [(name, quant) for name in rewards])):
        await cmd.ensure_accept_quest(CARVE_UNI_GEMSTONE_QUEST)
        await hunt_item(cmd, "The Secret 1", 1, "WillowCreek",
                        monster_name="Hidden Spy", is_temp=False)
        await farm_gem_of_nulgath(cmd, 7)
        await gem_stones_of_nulgath(cmd, 1, 3, 1, 1)
        # -1 makes the turn-in a "choose one", which is what the reference does
        # when the reward is not named
        await cmd.ensure_turn_in_quest(CARVE_UNI_GEMSTONE_QUEST,
                                      CARVE_REWARD_IDS.get(item, -1))


async def hire_nulgath_larvae(cmd: Command) -> None:
    """``CoreNation.HireNulgathLarvae``: quest 867, members only."""
    if await cmd.has_item("Nulgath Larvae") or not cmd.get_player().is_member:
        return

    cmd.bot.log("[nation] hiring the Nulgath Larvae (quest 867)")
    cmd.add_drop("Nulgath Larvae")
    await cmd.ensure_accept_quest(867)
    await farm_voucher(cmd, True, True)
    await hunt_item(cmd, "Undead Legend Rune", 1, "underworld",
                    monster_name="Undead Legend", is_temp=False)
    await cmd.ensure_turn_in_quest(867)


async def leery_exchange_gold(cmd: Command, quant: int = 100_000_000) -> None:
    """``CoreNation.LeeryExchangeGold``: swap Unidentified 13 for gold, quest 554."""
    if not cmd.get_player().is_member or cmd.get_player().GOLD >= quant:
        return

    cmd.bot.log(f"[nation] trading Unidentified 13 for gold until {quant}")
    cmd.add_drop(uni(13))
    # the reference toggles its gold boost here; this engine has no boosts

    while cmd.is_still_connected() and cmd.get_player().GOLD < quant:
        await farm_uni13_quest(cmd, 13)
        while cmd.is_still_connected() and await cmd.has_item(uni(13)):
            await cmd.ensure_accept_quest(554)
            await hunt_item(cmd, "Undead Legend Rune", 1, "underworld",
                            cell="r2", pad="up", monster_name="Undead Legend",
                            is_temp=False)
            if not await cmd.ensure_turn_in_quest(554):
                cmd.bot.log("[nation] quest 554 did not complete; stopping the "
                      "exchange.")
                cmd.cancel_registered_quests()
                return

    cmd.cancel_registered_quests()
