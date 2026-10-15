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
========================  ====================================================

**Not ported yet:** the Supplies cluster (``Supplies``, ``TheAssistant``,
``AssistantDuringSupplies``, ``BambloozevsDrudgen``, ``Deal``,
``FarmContractExchage``, ``DiamondExchange``, ``ContractExchange``,
``TotemsViaTaros``, ``GetPCoD``, ``KillHydra``, ``HandleVoucherConversions``,
``SellVoucherOfNulgath``), ``EmblemofNulgath`` / ``NationRound4Medal``,
``KisstheVoid``, ``Forge*``, the SRoE merge-shop branch, and the ``FarmX``
family.

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
from typing import Optional, Sequence, Tuple

from core.command import Command
from templates.hunt import DEFAULT_SKILL_LIST, hunt_item

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
#: baked into the string literal, so Skua's own Crag checks can never match.)
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
