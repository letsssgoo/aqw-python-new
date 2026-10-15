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
``has_any_item`` / ``has_item_id`` / ``has_any_item_id``  inventory checks
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
========================  ====================================================

**Not ported yet:**

* The member Forge stack -- ``GemStoneReceiptOfNulgath``, ``DwoboCoin``,
  ``GemStonesOfnulgath``, ``ForgeTaintedGems`` / ``ForgeDarkCrystalShards`` /
  ``ForgeDiamondsOfNulgath`` / ``ForgeBloodGems``, ``CarveUniGemStone``.  They
  route through the Vampire rep and gold farms, which are CoreFarms work that
  has not started.  ``farm_tainted_gem`` says so rather than skipping silently.
* ``EmblemofNulgath`` / ``NationRound4Medal``, ``SwindleReturn`` / ``SwindleBulk``,
  ``NulgathLarvae``, ``NulgathsRouletteofMisfortune``.
* The CoreFarms rep / gold / experience farms (a separate data-heavy pass).

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

from core.command import Command
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
#: (The C# source spells it ``Crag &amp; Bamboozle`` -- an HTML escape that got
#: baked into the string literal, so the reference bot's own Crag checks can never match.)
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


def uni(nr: int) -> str:
    """``Unidentified {nr}`` -- the reference bot's ``CoreNation.Uni``.

    A one-liner, but the name is built in dozens of places, so it lives here
    rather than being re-spelled at every call site.
    """
    return f"Unidentified {nr}"


async def equip_class(cmd: Command, solo: bool = False) -> bool:
    """Equip the configured farm or solo class (the reference bot's ``Core.EquipClass``).

    Args:
        cmd (Command): Facade to act through.
        solo (bool): ``True`` for the solo class, ``False`` for the farm one.

    Returns:
        bool: True when an item was equipped, False when no class is
        configured (the reference bot's ``ClassType`` had no such "unset" case).
    """
    name = cmd.get_solo_class() if solo else cmd.get_farm_class()
    if not name:
        return False
    return await cmd.equip_item(name)


def can_we_aggro(cmd: Command) -> bool:
    """Aggro while another player shares the cell (the reference bot's ``Core.CanWeAggro``).

    the reference bot flips two *client* options here -- ``AggroMonsters`` and
    ``HidePlayers``.  This engine has nothing to hide players with, and asks
    the server to aggro instead, so what is reproduced is the decision: aggro
    when the cell is shared, stop when it is not.

    Returns:
        bool: True when aggro was started.
    """
    player = cmd.get_player()
    me = str(getattr(player, "USER", "") or "").lower()
    others = [p for p in cmd.bot.player_in_area
              if str(p.str_username).lower() != me]
    if not others:
        cmd.stop_aggro()
        return False
    cell = player.CELL
    if cell:
        cmd.start_aggro_by_cell([cell])
        return True
    return False


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
    if (cmd.is_in_inventory("Nulgath's Approval", quant_approval)
            and cmd.is_in_inventory("Archfiend's Favor", quant_favor)):
        return

    cmd.add_drop(["Nulgath's Approval", "Archfiend's Favor"])
    cmd.farming_logger("Nulgath's Approval", quant_approval)
    cmd.farming_logger("Archfiend's Favor", quant_favor)
    await equip_class(cmd)

    while cmd.is_still_connected():
        if (cmd.is_in_inventory("Nulgath's Approval", quant_approval)
                and cmd.is_in_inventory("Archfiend's Favor", quant_favor)):
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
    if cmd.is_in_inventory("Blood From the Void", quant):
        return

    if cmd.is_still_connected() and not await cmd.is_completed_before(10581):
        print("Blood From the Void needs the /tercesinvasion story completed "
              "(quest 10581). Run the TercesInvasion story script first.")
        return

    cmd.add_drop("Blood From the Void")
    await equip_class(cmd, solo=True)
    await cmd.register_quest(10583 if cmd.get_player().is_member else 10582)
    cmd.farming_logger("Blood From the Void", quant)

    while (cmd.is_still_connected()
           and not cmd.is_in_inventory("Blood From the Void", quant)):
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
    if cmd.is_in_inventory("Fiend Emblem", quant):
        print(f"You already have {quant} (max stack) Fiend Emblem")
        return

    cmd.add_drop("Fiend Emblem")

    while cmd.is_still_connected() and not cmd.is_in_inventory("Fiend Emblem", quant):
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


def has_any_item(cmd: Command, names: Sequence[str]) -> bool:
    """True when the inventory holds at least one of ``names`` (``any: true``)."""
    return any(cmd.is_in_inventory(name) for name in names)


def has_item_id(cmd: Command, item_id: int) -> bool:
    """True when the inventory holds ``item_id``.

    the reference bot's ``Core.CheckInventory(int)`` overload; the id-based check is what the
    Void Knight Sword quests gate on, since the two variants are not named
    consistently enough to match by name.
    """
    return cmd.get_player().get_item_inventory_by_id(item_id) is not None


def has_any_item_id(cmd: Command, item_ids: Sequence[int]) -> bool:
    """True when the inventory holds at least one of ``item_ids``."""
    return any(has_item_id(cmd, item_id) for item_id in item_ids)


async def _mobius_horns(cmd: Command, full: bool) -> None:
    """Farm the Slugfit / Cyclops horns the quest needs, in the old /mobius map."""
    horn, cyclops = (10, 6) if full else (5, 3)
    if (cmd.is_in_inventory("Slugfit Horn", horn, isTemp=True)
            and cmd.is_in_inventory("Cyclops Horn", cyclops, isTemp=True)):
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
    if item and cmd.is_in_inventory(item, quant):
        return
    if not has_any_item(cmd, NWNO_PETS):
        return

    quest_id = 6183 if cmd.is_in_inventory("Bounty Hunter's Drone Pet") else 6697
    await equip_class(cmd)
    await cmd.register_quest(quest_id)          # accepts, so rewards load
    cmd.add_quest_rewards(quest_id)

    if item is None:
        quest = cmd.get_loaded_quest(quest_id)
        if quest is None:
            print(f"[nation] quest {quest_id} did not load; cannot enumerate "
                  f"its rewards. Nothing farmed.")
            cmd.cancel_registered_quests()
            return
        for _, name, max_stack in quest.reward_entries:
            if cmd.is_in_inventory(name, max_stack):
                continue
            cmd.farming_logger(name, max_stack)
            while (cmd.is_still_connected()
                   and not cmd.is_in_inventory(name, max_stack)):
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
        print("[nation] all items maxed")
    else:
        cmd.farming_logger(item, quant)
        while cmd.is_still_connected() and not cmd.is_in_inventory(item, quant):
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
    if item and cmd.is_in_inventory(item, quant):
        return
    if not has_any_item_id(cmd, VOID_KNIGHT_SWORDS):
        return

    cmd.add_drop(BAG_DROPS)
    if item:
        cmd.add_drop(item)

    quest_id = 5662 if has_item_id(cmd, 38275) else 5659
    await cmd.ensure_accept_quest(quest_id)      # accepts, so rewards load
    cmd.add_quest_rewards(quest_id)

    if item is None:
        quest = cmd.get_loaded_quest(quest_id)
        if quest is None:
            print(f"[nation] quest {quest_id} did not load; cannot enumerate "
                  f"its rewards. Nothing farmed.")
            return
        for _, name, max_stack in quest.reward_entries:
            if cmd.is_in_inventory(name, max_stack):
                continue
            cmd.farming_logger(name, max_stack)
            while (cmd.is_still_connected()
                   and not cmd.is_in_inventory(name, max_stack)):
                await _void_knight_step(cmd, quest_id)
        print("[nation] all items maxed")
    else:
        cmd.farming_logger(item, quant)
        while cmd.is_still_connected() and not cmd.is_in_inventory(item, quant):
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
    if item and cmd.is_in_inventory(item, quant, isTemp=is_temp):
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
        goal = lambda: not cmd.is_monster_alive("*")            # noqa: E731
    else:
        goal = lambda: cmd.is_in_inventory(item, quant,           # noqa: E731
                                           isTemp=is_temp)

    while cmd.is_still_connected() and not goal():
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
    if item and cmd.is_in_inventory(item, quant, isTemp=is_temp):
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
        goal = lambda: not cmd.is_monster_alive("*")            # noqa: E731
    else:
        goal = lambda: cmd.is_in_inventory(item, quant,           # noqa: E731
                                           isTemp=is_temp)

    while cmd.is_still_connected() and not goal():
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
    if not item or cmd.is_in_inventory(item, quantity, isTemp=is_temp):
        return

    member = bool(cmd.get_player().is_member)
    map_name, cell = random.choice([
        ("tercessuinotlim", "m1"),
        ("Nulgath" if member else "evilmarsh", "Field1"),
    ])

    while (cmd.is_still_connected()
           and not cmd.is_in_inventory(item, quantity, isTemp=is_temp)):
        if not await _travel(cmd, map_name, cell):
            continue
        await cmd.use_next_skill(DEFAULT_SKILL_LIST, "Dark Makai")

    await equip_class(cmd, solo=True)


async def crags_thirst(cmd: Command, quant: int = 1000) -> None:
    """Diamonds of Nulgath via Crag's Thirst (quest 600).

    Needs the Crag pet and 100 Unidentified 10 banked; the C# bails out
    silently without them, and so does this.
    """
    if (not cmd.is_in_inventory(CRAG_PET)
            or cmd.is_in_inventory("Diamond of Nulgath", quant)
            or not cmd.is_in_inventory(uni(10), 100)):
        return

    print("[nation] doing Crag's Thirst")
    while (cmd.is_still_connected()
           and cmd.is_in_inventory(uni(10), 100)
           and not cmd.is_in_inventory("Diamond of Nulgath", quant)):
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
    if not endless and cmd.is_in_inventory("Blood Gem of the Archfiend", quant):
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
                or not cmd.is_in_inventory("Blood Gem of the Archfiend", quant))):
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
    if cmd.is_in_inventory("Dark Crystal Shard", quant):
        return

    cmd.add_drop(TERCESS_BAGS + BAG_DROPS)
    cmd.farming_logger("Dark Crystal Shard", quant)
    await cmd.register_quest(570)

    while (cmd.is_still_connected()
           and not cmd.is_in_inventory("Dark Crystal Shard", quant)):
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
        print("[nation] the SRoE merge-shop branch is not ported; farming "
              "Unidentified 10 with the base quest only.")

    while (cmd.is_still_connected()
           and not cmd.is_in_inventory("Unidentified 10", quant)):
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


def has_obon_pet(cmd: Command) -> bool:
    """True for members holding one of the two OBoN stand-in pets."""
    return bool(cmd.get_player().is_member) and has_any_item_id(cmd, OBO_PETS)


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
    if not cmd.is_in_inventory("Voucher of Nulgath"):
        return
    if cmd.is_not_in_cell("Enter"):
        await cmd.jump_cell("Enter", "Spawn")
    await cmd.sell_item("Voucher of Nulgath",
                        cmd.get_quant_item("Voucher of Nulgath"))


def _log_supplies_config(item: Optional[str], quant: int, ultra_alteon: bool,
                         hydra: bool, keep_voucher: bool,
                         sell_mem_voucher: bool, assistant: bool,
                         return_policy: bool, return_item: Optional[str]) -> None:
    """Print the settings the Supplies route resolved to (the C# logs the same)."""
    def flag(value: bool) -> str:
        return "True" if value else "False"

    print("[nation] [Supplies] =========================")
    print(f"[nation] item      : {item or 'All'} x{quant}")
    print(f"[nation] ultra     : {flag(ultra_alteon)}")
    print(f"[nation] hydra     : {flag(hydra)}")
    print(f"[nation] voucher K : {flag(keep_voucher)}")
    print(f"[nation] voucher S : {flag(sell_mem_voucher)}")
    print(f"[nation] assist    : {flag(assistant)}")
    print(f"[nation] return    : {flag(return_policy)}")
    print(f"[nation] return it : {return_item or 'None'}")
    print("[nation] [Supplies] =========================")


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
    if not all(cmd.is_in_inventory(uni(n)) for n in (1, 6, 9, 16, 20)):
        return

    await cmd.ensure_accept_quest(7551)
    quest = cmd.get_loaded_quest(7551)
    if quest is None or not quest.reward_entries:
        print("[nation] quest 7551 did not load with rewards; skipping the "
              "Swindle's Return turn-in.")
        return

    candidates = [entry for entry in quest.reward_entries
                  if entry[0] != SWINDLES_EXCLUDED_REWARD]
    if item is not None:
        wanted = [entry for entry in candidates if entry[1] == item]
        if not wanted:
            print(f"[nation] {item!r} is not a quest 7551 reward; skipping.")
            return
        if cmd.is_in_inventory(wanted[0][1], wanted[0][2]):
            return
    elif all(cmd.is_in_inventory(name, stack)
             for _, name, stack in candidates):
        return

    await dark_makai_item(cmd, "Dark Makai Rune")

    if not cmd.can_turnin_quest(7551):
        print("[nation] quest 7551 is not completable yet; skipping the turn-in.")
        return

    chosen = None
    if item is not None:
        chosen = next((e for e in candidates if e[1] == item), None)
    else:
        chosen = next((e for e in candidates
                       if not cmd.is_in_inventory(e[1], e[2])), None)

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
    await cmd.buy_item(41, "War-Torn Memorabilia", quantity)
    await cmd.ensure_turn_in_quest(2859, -1, quantity)


async def get_pcod(cmd: Command) -> bool:
    """Obtain the Purified Claymore of Destiny (quest 548).

    Returns:
        bool: True when the claymore is held afterwards, False when a
        prerequisite is missing.

    Note:
        The C# first runs ``Farm.Experience(15)`` and ``Farm.GoodREP(8)``.  Those
        two rep/exp farms are not ported, so this checks the state they would
        produce and stops with a message when it is not met -- rather than
        silently farming nothing.
    """
    if cmd.is_in_inventory("Purified Claymore of Destiny"):
        return True

    rank = cmd.get_faction_rank("Good")
    level = cmd.get_player().LEVEL
    if rank < 8 or (level and level < 15):
        print(f"[nation] the Purified Claymore needs Good rank 8 and level 15 "
              f"(have rank {rank}, level {level or 'unknown'}). The rep/exp "
              f"farms are not ported yet, so this stops here.")
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
    if item and cmd.is_in_inventory(item, quant):
        return

    # with no target, stop once every principal drop is already maxed
    if item is None:
        await cmd.ensure_accept_quest(2857)
        quest = cmd.get_loaded_quest(2857)
        if quest is not None and quest.reward_entries:
            stacks = {name: stack for _, name, stack in quest.reward_entries}
            if all(cmd.is_in_inventory(drop, stacks.get(drop, 1))
                   for drop in BAG_DROPS_PRINCIPAL):
                return

    if keep_voucher:
        sell_mem_voucher = False
    elif sell_mem_voucher and cmd.get_player().GOLD >= 100_000_000:
        sell_mem_voucher = False

    _log_supplies_config(item, quant, ultra_alteon, hydra_challenge,
                         keep_voucher, sell_mem_voucher, assistant_during,
                         return_policy, return_item)

    quests = [2857]
    if item != uni(13) and has_item_id(cmd, 38261):
        quests.append(9542)
    if cmd.is_in_inventory("Drudgen the Assistant"):
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
    for thing in SUPPLIES_REWARDS:
        if not cmd.is_still_connected():
            return
        quest = cmd.get_loaded_quest(2857)
        entry = next((e for e in (quest.reward_entries if quest else [])
                      if e[1] == thing), None)
        if entry is None:
            continue
        _, name, max_stack = entry

        if not ultra_alteon and not hydra and (cmd.is_in_inventory(CRAG_PET)
                                               or has_obon_pet(cmd)):
            await bamboozle_vs_drudge(cmd, name, max_stack, keep_voucher,
                                      assistant_during, return_item,
                                      came_from_supplies=True,
                                      sell_mem_voucher=sell_mem_voucher,
                                      return_policy=return_policy)
            continue

        while (cmd.is_still_connected()
               and not cmd.is_in_inventory(name, max_stack)):
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
    if not ultra_alteon and not hydra and (cmd.is_in_inventory(CRAG_PET)
                                           or has_obon_pet(cmd)):
        await bamboozle_vs_drudge(cmd, item, quant, keep_voucher,
                                  assistant_during, return_item,
                                  came_from_supplies=True,
                                  sell_mem_voucher=sell_mem_voucher,
                                  return_policy=return_policy)
        return

    while cmd.is_still_connected() and not cmd.is_in_inventory(item, quant):
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
    if (not cmd.is_in_inventory("Voucher of Nulgath (non-mem)")
            or not cmd.is_in_inventory("Essence of Nulgath", 60)):
        return

    diamonds_maxed = cmd.is_in_inventory("Diamond of Nulgath", 1000)
    totems_maxed = cmd.is_in_inventory("Totem of Nulgath", 100)

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
        print("[nation] bamboozle_vs_drudge needs an item; the C# version "
              "accepts null and then loops forever. Nothing farmed.")
        return
    if cmd.is_in_inventory(item, quant):
        print(f"[nation] {item} x{quant} already owned.")
        return

    cmd.add_drop(["Relic of Chaos", "Tainted Core", item])
    if return_policy:
        cmd.add_drop([uni(1), uni(6), uni(9), uni(16), uni(20)])
    if not came_from_supplies:
        print(f"[nation] bamboozle mode: item {item} | keep {keep_voucher} "
              f"| assist {assistant_during}")

    cmd.farming_logger(item, quant)

    quests = [2857]
    if cmd.is_in_inventory(CRAG_PET):
        quests.append(609)
    if has_obon_pet(cmd):
        cmd.add_drop("Tainted Soul")
        quests.append(599 if has_item_id(cmd, 4809) else 2561)
    if has_item_id(cmd, 38261):
        quests.append(9542)
    for quest_id in dict.fromkeys(quests):
        await cmd.register_quest(quest_id)

    await equip_class(cmd, solo=True)

    while cmd.is_still_connected() and not cmd.is_in_inventory(item, quant):
        await _kill_once(cmd, "evilmarsh", "End", "Left", "Tainted Elemental")
        await sell_voucher_of_nulgath(cmd, sell_mem_voucher, item)
        await assistant_during_supplies(cmd, assistant_during)
        if return_item:
            await do_swindles_return_area(cmd, return_policy, return_item)
        await handle_voucher_conversions(cmd, item)
        if (return_policy and item in (None, "Diamond of Nulgath")
                and not cmd.is_in_inventory("Diamond of Nulgath", 1000)):
            await crags_thirst(cmd)


async def essence_of_nulgath(cmd: Command, quant: int = 60) -> None:
    """Farm Essence of Nulgath off the Dark Makai in Tercessuinotlim."""
    if cmd.is_in_inventory("Essence of Nulgath", quant):
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
    if ((not cmd.is_in_inventory("Diamond of Nulgath", 15) and not farm_diamond)
            or not cmd.is_in_inventory(CRAG_PET)
            or cmd.is_in_inventory(uni(13), 13)):
        return

    cmd.add_drop("Diamond of Nulgath")
    if farm_diamond and (has_obon_pet(cmd) or cmd.is_in_inventory(CRAG_PET)):
        await bamboozle_vs_drudge(cmd, "Diamond of Nulgath", 15)

    await equip_class(cmd)
    while (cmd.is_still_connected()
           and cmd.is_in_inventory("Diamond of Nulgath", 15)
           and not cmd.is_in_inventory(uni(13), 13)):
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
    if not cmd.is_in_inventory("Drudgen the Assistant"):
        print('[nation] missing "Drudgen the Assistant"')
        return
    if not cmd.is_in_inventory(uni(13)) and not farm_uni13:
        print("[nation] contract exchange needs Unidentified 13 and was told "
              "not to farm it")
        return

    cmd.add_drop(BAG_DROPS)
    await equip_class(cmd, solo=True)
    cmd.farming_logger(reward_name, quant)

    reward_id = _reward_id(cmd, 870, reward_name)
    while cmd.is_still_connected() and not cmd.is_in_inventory(reward_name, quant):
        if farm_uni13 and not cmd.is_in_inventory(uni(13)):
            await farm_uni13_quest(cmd, 3)
        await cmd.ensure_accept_quest(870)
        await _kill_once(cmd, "tercessuinotlim", "m4", "Top",
                         "Shadow of Nulgath")
        await cmd.ensure_turn_in_quest(870, reward_id)


def _reward_id(cmd: Command, quest_id: int, name: str) -> int:
    """Item id of a quest reward by name, or -1 when the quest is not loaded."""
    quest = cmd.get_loaded_quest(quest_id)
    for item_id, reward_name, _ in (quest.reward_entries if quest else []):
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
    if (not cmd.is_in_inventory("Drudgen the Assistant")
            or (item and cmd.is_in_inventory(item, quant))):
        if not cmd.is_in_inventory("Drudgen the Assistant"):
            print('[nation] missing "Drudgen the Assistant"')
        return

    await equip_class(cmd)
    cmd.add_quest_rewards(870)

    for name in ([item] if item else list(CONTRACT_REWARDS)):
        await cmd.ensure_accept_quest(870)
        quest = cmd.get_loaded_quest(870)
        entry = next((e for e in (quest.reward_entries if quest else [])
                      if e[1] == name), None)
        if entry is None:
            if item:
                print(f"[nation] reward {name!r} is not part of quest 870.")
            continue
        _, reward_name, max_stack = entry
        target = quant if quant > 1 else max_stack
        cmd.farming_logger(reward_name, target)
        while (cmd.is_still_connected()
               and not cmd.is_in_inventory(reward_name, target)):
            await supplies(cmd, "Diamond of Nulgath", 45,
                           return_item="Diamond of Nulgath")
            await contract_exchange(cmd, reward_name, target)


async def farm_uni13_quest(cmd: Command, quant: int = 13) -> None:
    """Unidentified 13, stacked to its cap of 13."""
    if cmd.is_in_inventory(uni(13), quant):
        return
    cmd.add_drop(uni(13))
    quant = min(quant, 13)

    if cmd.is_in_inventory(CRAG_PET):
        while (cmd.is_still_connected()
               and not cmd.is_in_inventory(uni(13), quant)):
            await diamond_exchange(cmd)

    await new_worlds_new_opportunities(cmd, uni(13), quant)
    await void_knight_sword_quest(cmd, uni(13), quant)
    await supplies(cmd, uni(13), quant)


async def farm_uni10(cmd: Command, quant: int = 1000) -> None:
    """Unidentified 10, pet route first when one is owned."""
    if cmd.is_in_inventory("Unidentified 10", quant):
        return
    cmd.add_drop("Unidentified 10")
    if has_obon_pet(cmd) or cmd.is_in_inventory(CRAG_PET):
        await bamboozle_vs_drudge(cmd, "Unidentified 10", quant,
                                  came_from_supplies=True)
    await dirty_deeds_done_dirt_cheap(cmd, quant)


async def farm_dark_crystal_shard(cmd: Command, quant: int = 1000) -> None:
    """Dark Crystal Shard, by every route the account can take."""
    if cmd.is_in_inventory("Dark Crystal Shard", quant):
        return
    cmd.add_drop("Dark Crystal Shard")
    await farm_contract_exchage(cmd, "Dark Crystal Shard", quant)
    await new_worlds_new_opportunities(cmd, "Dark Crystal Shard", quant)
    if cmd.is_in_inventory(CRAG_PET):
        await supplies(cmd, "Dark Crystal Shard", quant,
                       return_item="Dark Crystal Shard")
    await void_knight_sword_quest(cmd, "Dark Crystal Shard", quant)
    await supplies(cmd, "Dark Crystal Shard", quant,
                   return_item="Dark Crystal Shard")
    await essence_of_defeat_reagent(cmd, quant)


async def farm_diamond_of_nulgath(cmd: Command, quant: int = 1000) -> None:
    """Diamond of Nulgath, by every route the account can take."""
    if cmd.is_in_inventory("Diamond of Nulgath", quant):
        return
    cmd.add_drop("Diamond of Nulgath")
    while (cmd.is_still_connected()
           and not cmd.is_in_inventory("Diamond of Nulgath", quant)
           and cmd.is_in_inventory(CRAG_PET)
           and cmd.is_in_inventory(uni(10), 100)):
        await crags_thirst(cmd, quant)
    if cmd.is_in_inventory(CRAG_PET):
        await supplies(cmd, "Diamond of Nulgath", quant,
                       return_item="Diamond of Nulgath")
    await void_knight_sword_quest(cmd, "Diamond of Nulgath", quant)
    await supplies(cmd, "Diamond of Nulgath", quant,
                   return_item="Diamond of Nulgath")


async def farm_gem_of_nulgath(cmd: Command, quant: int = 1000) -> None:
    """Gem of Nulgath, by every route the account can take."""
    if cmd.is_in_inventory("Gem of Nulgath", quant):
        return
    cmd.add_drop("Gem of Nulgath")
    await farm_contract_exchage(cmd, "Gem of Nulgath", quant)
    if cmd.is_in_inventory(CRAG_PET):
        await supplies(cmd, "Gem of Nulgath", quant,
                       return_item="Gem of Nulgath")
    await void_knight_sword_quest(cmd, "Gem of Nulgath", quant)
    await supplies(cmd, "Gem of Nulgath", quant, return_item="Gem of Nulgath")


async def farm_blood_gem(cmd: Command, quant: int = 100,
                         hydra_level: int = 85) -> None:
    """Blood Gem of the Archfiend, by every route the account can take."""
    if cmd.is_in_inventory("Blood Gem of the Archfiend", quant):
        return
    cmd.add_drop("Blood Gem of the Archfiend")
    await farm_contract_exchage(cmd, "Blood Gem of the Archfiend", quant)
    await new_worlds_new_opportunities(cmd, "Blood Gem of the Archfiend", quant)
    await void_knight_sword_quest(cmd, "Blood Gem of the Archfiend", quant)
    await bloody_chaos(cmd, quant, relic=True, hydra_level=hydra_level)
    await kissthe_void(cmd, quant)


async def farm_tainted_gem(cmd: Command, quant: int = 1000) -> None:
    """Tainted Gem, by every route the account can take.

    Note:
        The C# also runs ``ForgeTaintedGems`` here.  That Forge route is not
        ported -- it goes through ``GemStoneReceiptOfNulgath``, which needs the
        Vampire rep and gold farms that are still outstanding -- so it is
        skipped with a notice instead of silently missing.
    """
    if cmd.is_in_inventory("Tainted Gem", quant):
        return
    cmd.add_drop("Tainted Gem")
    await farm_contract_exchage(cmd, "Tainted Gem", quant)
    if cmd.is_in_inventory(CRAG_PET):
        await supplies(cmd, "Tainted Gem", quant, return_item="Tainted Gem")
    print("[nation] the Forge route (quest 4919) is not ported; farming "
          "Tainted Gem through the other three steps only.")
    await supplies(cmd, "Tainted Gem", quant, return_item="Tainted Gem")


async def farm_totem_of_nulgath(cmd: Command, quant: int = 100) -> None:
    """Totem of Nulgath: Deal first, then Taro's chain as the fallback."""
    if cmd.is_in_inventory("Totem of Nulgath", quant):
        return
    await deal(cmd, gem_quant=0, totem_quant=quant)
    await new_worlds_new_opportunities(cmd, "Totem of Nulgath", quant)
    await totems_via_taros(cmd, quant)


async def farm_voucher(cmd: Command, member: bool, keep_voucher: bool = False
                       ) -> None:
    """Voucher of Nulgath, member or non-member variant by the flag."""
    name = "Voucher of Nulgath" if member else "Voucher of Nulgath (non-mem)"
    if cmd.is_in_inventory(name):
        return
    cmd.add_drop(name)
    print(f"[nation] keep voucher set to {keep_voucher}")

    if has_obon_pet(cmd) or cmd.is_in_inventory(CRAG_PET):
        await bamboozle_vs_drudge(cmd, name, 1, keep_voucher=keep_voucher,
                                  came_from_supplies=True)
    await new_worlds_new_opportunities(cmd, name)
    await void_knight_sword_quest(cmd, name)
    await supplies(cmd, name, keep_voucher=keep_voucher)


async def farm_fiend_token(cmd: Command, quant: int = 30) -> None:
    """Fiend Token, by the three routes the C# tries in order."""
    if cmd.is_in_inventory("Fiend Token", quant):
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
    if not cmd.is_in_inventory(CRAG_PET):
        print(f"[nation] missing {CRAG_PET}; cannot continue.")
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
               and not cmd.is_in_inventory(item_name, quant)):
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
    if (cmd.is_in_inventory(item, quant)
            or not cmd.is_in_inventory("Drudgen the Assistant")
            or not cmd.is_in_inventory("Twin Blade of Nulgath")
            or not cmd.get_player().is_member):
        return

    while cmd.is_still_connected() and not cmd.is_in_inventory(item, quant):
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
        if cmd.get_loaded_quest(3826) is not None and not has_item_id(cmd, 25026):
            await hunt_item(cmd, "Seal of Light", 1, "alteonbattle",
                            monster_name="Ultra Chaos Alteon", is_temp=True)
            await cmd.ensure_turn_in_quest(3826)
        else:
            print("[nation] the Seal of Light daily (3826) is not available.")
        await cmd.ensure_turn_in_quest(5816)


async def feed_the_fiend(cmd: Command, item: str = "Fiend Token",
                         quant: int = 30) -> None:
    """Quest 3053, members only, for Fiend Tokens."""
    if cmd.is_in_inventory(item, quant) or not cmd.get_player().is_member:
        return
    cmd.add_drop(item)
    await cmd.register_quest(3053)
    await equip_class(cmd, solo=True)

    while cmd.is_still_connected() and not cmd.is_in_inventory(item, quant):
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
    if cmd.is_in_inventory("Totem of Nulgath", quant):
        return

    if (cmd.get_player().is_member
            and not cmd.is_in_inventory("Purified Claymore of Destiny")):
        print("[nation] member route needs the Purified Claymore first.")
        if not await get_pcod(cmd):
            return

    cmd.add_drop("Totem of Nulgath")
    if (cmd.is_still_connected()
            and not await cmd.is_completed_before(9541)):
        # the C# calls ChainComplete(9541) here: accept it, then complete it
        await cmd.ensure_accept_quest(9541)
        await cmd.ensure_turn_in_quest(9541)

    while cmd.is_still_connected() and not cmd.is_in_inventory("Totem of Nulgath", quant):
        await cmd.ensure_accept_quest(726)
        await essence_of_nulgath(cmd, 25)
        if (cmd.get_player().is_member
                and not has_item_id(cmd, 538)):
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
    if cmd.is_in_inventory(watching, quant if betrayal_blade is None else 1):
        return

    cmd.add_drop([watching, "Fragment of Chaos", "Blood Gem of the Archfiend",
                  "Broken Betrayal Blade"])
    await equip_class(cmd)
    cmd.farming_logger(watching, quant if betrayal_blade is None else 1)
    cmd.add_drop(SUPPLIES_REWARDS)
    cmd.add_drop("Relic of Chaos")
    await cmd.register_quest(2857)

    while (cmd.is_still_connected()
           and not cmd.is_in_inventory(watching,
                                       quant if betrayal_blade is None else 1)):
        await cmd.ensure_accept_quest(3743)
        if not cmd.is_in_inventory("Tendurrr The Assistant"):
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
        if not cmd.is_in_inventory("Blood Gem of the Archfiend", 100):
            await do_swindles_return_area(cmd, return_policy,
                                          "Blood Gem of the Archfiend")
        if (cmd.is_in_inventory("Voucher of Nulgath (non-mem)")
                and cmd.is_in_inventory("Essence of Nulgath", 60)
                and (not cmd.is_in_inventory("Diamond of Nulgath", 1000)
                     or not cmd.is_in_inventory("Totem of Nulgath", 100))):
            diamonds_first = not cmd.is_in_inventory("Diamond of Nulgath", 1000)
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
    if cmd.is_in_inventory("Nation Round 4 Medal"):
        print("[nation] medal 4 owned, no need to farm it")
        return

    for medal, quest_id, steps in NATION_MEDALS:
        if not cmd.is_still_connected():
            return
        cmd.add_drop(medal)
        if cmd.is_in_inventory(medal):
            print(f'[nation] "{medal}" owned.')
            continue
        await cmd.ensure_accept_quest(quest_id)
        for monster, item, qty in steps:
            await hunt_item(cmd, item, qty, "shadowblast",
                            monster_name=monster, is_temp=True)
        await cmd.ensure_turn_in_quest(quest_id)
        print(f"[nation] medal {medal} acquired")
        cmd.remove_drop(medal)


async def emblem_of_nulgath(cmd: Command, quant: int = 500) -> None:
    """Quest 4748, after the four medals are done.

    Note:
        The C# never cancels the registered quest here, and neither does this:
        the auto-quest task re-accepting 4748 is what keeps the loop fed.  The
        loop ends when the emblem hits ``quant``, not when the task stops.
    """
    if cmd.is_in_inventory("Emblem of Nulgath", quant):
        return
    await nation_round_4_medal(cmd)

    cmd.add_drop(["Fiend Seal", "Gem of Domination", "Emblem of Nulgath"])
    cmd.add_drop(BAG_DROPS)
    await equip_class(cmd)
    cmd.farming_logger("Emblem of Nulgath", quant)
    await cmd.register_quest(4748)

    while (cmd.is_still_connected()
           and not cmd.is_in_inventory("Emblem of Nulgath", quant)):
        await hunt_item(cmd, "Gem of Domination", 1, "shadowblast",
                        monster_name="Shadowrise Guard", is_temp=False)
        await hunt_item(cmd, "Fiend Seal", 25, "shadowblast",
                        monster_name="Legion Fenrir", is_temp=False)


async def swindle_return(cmd: Command, item: Optional[str] = None,
                         quant: int = 1000) -> None:
    """Quest 7551 (Swindle's Return Policy) for one of its rewards.

    Each pass feeds the quest five Unidentifieds through the Supplies route,
    then the Dark Makai Rune, then turns it in for ``item``.
    """
    await cmd.ensure_accept_quest(7551)
    quest = cmd.get_loaded_quest(7551)
    if quest is None:
        print("[nation] quest 7551 did not load.")
        return

    entry = next((e for e in quest.reward_entries if e[1] == item), None)
    if entry is None or cmd.is_in_inventory(entry[1], quant):
        return
    _, item_name, _ = entry

    cmd.add_drop(RECEIPT_DROPS)
    if item:
        cmd.add_drop(item)
    cmd.farming_logger(item_name, quant)

    while cmd.is_still_connected() and not cmd.is_in_inventory(item_name, quant):
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
    if cmd.is_in_inventory("Tainted Gem", quant):
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
    while cmd.is_still_connected() and not cmd.is_in_inventory("Tainted Gem", quant):
        await cmd.ensure_accept_quest(quest_id)
        await hunt_item(cmd, "Cubes", cube_count, "boxes",
                        cell="Fort2", pad="Left", monster_name="*",
                        is_temp=False)
        await hunt_item(cmd, "Ice Cubes", snow_count, "mountfrost",
                        cell="War", pad="Left", monster_name="Snow Golem",
                        is_temp=True)
        await cmd.ensure_turn_in_quest(quest_id)
        attempt += 1
        print(f"[nation] completed x{attempt}")


async def dreadrock_gem_exchange(cmd: Command, quant: int = 1000) -> None:
    """Quest 4853: Tainted Gems from the dreadrock mobs."""
    if cmd.is_in_inventory("Tainted Gem", quant):
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
           and not cmd.is_in_inventory(item, quant)
           and cmd.is_in_inventory(MANA_ENERGY)):
        await cmd.ensure_accept_quest(LARVAE_QUEST)
        await hunt_item(cmd, CHARGED_MANA_ENERGY, 5, "elemental",
                        monster_name="Mana Falcon", is_temp=True)
        await cmd.ensure_turn_in_quest(LARVAE_QUEST)

        if (cmd.is_in_inventory("Voucher of Nulgath (non-mem)")
                and cmd.is_in_inventory("Essence of Nulgath", 60)):
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
    if larvae is None:
        print("[nation] quest 2566 (Nulgath Larvae) did not load.")
        return
    if item and cmd.is_in_inventory(item, quant):
        return

    known = [name for _, name, _ in larvae.reward_entries]
    if item is not None:
        if item not in known:
            print(f"[nation] {item!r} is not a Nulgath Larvae reward.")
            return
        targets = [(item, quant)]
    else:
        targets = [(name, stack) for _, name, stack in larvae.reward_entries
                   if not cmd.is_in_inventory(name, stack)]

    for name, target in targets:
        cmd.add_drop([MANA_ENERGY, name])
        cmd.farming_logger(name, target)
        while cmd.is_still_connected() and not cmd.is_in_inventory(name, target):
            await _larvae_step(cmd, name, target)


async def nulgaths_roulette_of_misfortune(cmd: Command, item: Optional[str],
                                          quant: int) -> None:
    """The same Larvae loop, without the voucher-quest side trip."""
    if item is None or cmd.is_in_inventory(item, quant):
        return
    cmd.farming_logger(item, quant)
    cmd.add_drop(item)

    while cmd.is_still_connected() and not cmd.is_in_inventory(item, quant):
        await cmd.ensure_accept_quest(LARVAE_QUEST)
        await equip_class(cmd, solo=True)
        await hunt_item(cmd, MANA_ENERGY, 10, "elemental",
                        monster_name="Mana Golem", is_temp=False)
        await equip_class(cmd)

        while (cmd.is_still_connected()
               and not cmd.is_in_inventory(item, quant)
               and cmd.is_in_inventory(MANA_ENERGY)):
            await cmd.ensure_accept_quest(LARVAE_QUEST)
            await hunt_item(cmd, CHARGED_MANA_ENERGY, 5, "elemental",
                            monster_name="Mana Falcon", is_temp=True)
            await cmd.ensure_turn_in_quest(LARVAE_QUEST)
