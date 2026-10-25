"""The reference bot's ``CoreBots``: the helpers every other core leans on.

Port of ``CoreBots.cs``, kept in ``bot/`` next to the other root cores because
that is where the reference keeps it.  Only the parts the ported cores actually
call live here so far:

======================  ==================================================
``Alignment``           the Good / Evil / Chaos enum
``change_alignment``    ``CoreBots.ChangeAlignment``
``equip_class``         ``CoreBots.EquipClass``
``can_we_aggro``        ``CoreBots.CanWeAggro``
``buy_item``            ``CoreBots.BuyItem``, by name or by item id
``dynamic_quant``       ``CoreBots.dynamicQuant``
``wait_for_item``       ``Bot.Wait.ForPickup``, as a bounded poll
``hunt_monster_quest``  ``CoreBots.HuntMonsterQuest`` (the map/monster tuples)
``get_map_items``       ``CoreBots.GetMapItems``
``register_quests``     ``CoreBots.RegisterQuests``, the plural form
``saved_state``         ``CoreBots.SavedState`` / ``CheckSaveState`` /
                        ``ExecuteSaveState``
``farming_logger``      ``CoreBots.FarmingLogger``
``equip_items``         ``CoreBots.Equip``, the array form
``quest_rewards``       ``CoreBots.QuestRewards``, the plural form
``chain_complete``      ``CoreBots.ChainComplete``
``ensure_complete_choose``  ``CoreBots.EnsureCompleteChoose``
======================  ==================================================

``bot.nation.core_nation`` re-exports ``equip_class`` and ``can_we_aggro`` from
here, so its call sites and tests keep the names they had.
"""
import json
import random
import time
from enum import Enum
from typing import List, Optional, Sequence, Tuple, Union

from core.command import Command
from core.utils import is_valid_json
from model.inventory import ItemType
from templates.hunt import DEFAULT_SKILL_LIST, hunt_item

#: Kitsune's own name -- ``KillKitsune`` attacks it by name.
KITSUNE = "Kitsune"

#: The aura Kitsune takes on when it shapeshifts; it cannot be hurt while it is up.
KITSUNE_SHIFT_AURA = "Shapeshifted"


def parse_message(message) -> Optional[dict]:
    """Unwrap a server payload's ``b.o``, or return ``None``.

    Subscribers get the raw message, and the useful part is one level down.  Kept
    here because a core needs it too -- ``bot/ultra/core_ultra`` has its own copy
    of the same three lines, which is left alone.
    """
    if not message or not is_valid_json(message):
        return None
    try:
        data = json.loads(message)["b"]["o"]
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def kitsune_shifted(message) -> Optional[bool]:
    """Whether Kitsune's ``Shapeshifted`` aura just went on or off.

    The reference's ``KitsuneListener``: on a ``ct`` payload, for the action whose
    aura is exactly ``Shapeshifted``, its ``cmd``'s last character says which way
    it went (``aura+`` on, ``aura-`` off).

    Returns:
        bool | None: True when the aura came up, False when it dropped, and None
        when this message says nothing about it -- so a caller leaves its state
        alone rather than clearing it on every unrelated packet.
    """
    data = parse_message(message)
    if not data or data.get("cmd") != "ct":
        return None
    for action in data.get("a") or []:
        aura = (action.get("aura") or {}).get("nam", "")
        if aura != KITSUNE_SHIFT_AURA:
            continue
        return str(action.get("cmd", ""))[-1:] == "+"
    return None


class Alignment(Enum):
    """The three sides a character can fight for (``CoreBots.Alignment``)."""

    GOOD = 1
    EVIL = 2
    CHAOS = 3


#: The reference bot sends the alignment as the number the enum carries.
ALIGNMENT_VALUES = {"Good": Alignment.GOOD, "Evil": Alignment.EVIL,
                    "Chaos": Alignment.CHAOS}


async def change_alignment(cmd: Command, side: Alignment) -> None:
    """Declare the character's alignment to the server.

    ``CoreBots.ChangeAlignment``: ``updateQuest`` for quest 41, the alignment
    quest, carrying the side as an integer.  The reference then sleeps twice its
    action delay; the same two seconds are spent here.
    """
    cmd.bot.write_message(
        f"%xt%zm%updateQuest%{cmd.bot.areaId}%41%{side.value}%")
    await cmd.sleep(2000)


def _find_shop(cmd: Command, shop_id: int):
    """The loaded shop with ``shop_id``, or None when it has not arrived yet."""
    for shop in cmd.bot.loaded_shop_datas:
        if str(shop.shop_id) == str(shop_id):
            return shop
    return None


async def kill_kitsune(cmd: Command, item: Optional[str] = None, quant: int = 1,
                       is_temp: bool = False) -> None:
    """``CoreBots.KillKitsune``: kill Kitsune in /kitsune, optionally for an item.

    Kitsune cannot be hurt while its ``Shapeshifted`` aura is up, so the reference
    subscribes a packet listener for the combat payload that turns it on and off
    and stops attacking meanwhile.  The same listener is used here; what it decides
    is :func:`kitsune_shifted`, so the rule can be read and tested on its own.

    Args:
        cmd (Command): Facade to act through.
        item (str | None): What to farm; without it, one kill.
        quant (int): How many of ``item``.
        is_temp (bool): Whether the item is a temp drop, as the reference's own
            flag says (its caller passes ``true`` for ``Private Reserve Sake``).
    """
    if item and await cmd.has_item(item, quant, isTemp=is_temp):
        return
    if item and not is_temp:
        cmd.add_drop(item)

    #: Set from the listener; read by the loop below.
    shifted = {"on": False}

    def kitsune_listener(message) -> None:
        state = kitsune_shifted(message)
        if state is not None:
            shifted["on"] = state

    cmd.bot.subscribe(kitsune_listener)
    try:
        while cmd.is_still_connected():
            while cmd.is_still_connected() and cmd.is_not_in_map("kitsune"):
                await cmd.join_map("kitsune")
            if cmd.is_not_in_cell("Boss"):
                await cmd.jump_cell("Boss", "Left")

            if item:
                if await cmd.has_item(item, quant, isTemp=is_temp):
                    await cmd.leave_combat()
                    return
            elif not cmd.is_monster_alive(KITSUNE):
                return

            if shifted["on"]:
                # it cannot be damaged while shifted, so wait it out
                await cmd.sleep(500)
                continue
            await cmd.use_next_skill(DEFAULT_SKILL_LIST, KITSUNE)
    finally:
        cmd.bot.unsubscribe(kitsune_listener)


async def buy_item(cmd: Command, shop_id: int, item: Union[int, str],
                   qty: int = 1, map_name: Optional[str] = None,
                   shop_item_id: int = 0) -> bool:
    """Buy an item from a shop, in the map that shop lives in.

    ``CoreBots.BuyItem(map, shopID, item)`` joins the map before anything else --
    a shop only loads where it is, and ``_BuyItem`` says so outright
    (``if Bot.Map.Name != map: Join(map)``).  This engine's ``Command.buy_item``
    does not, so from any other map it asks for a shop the server never sends,
    and the purchase quietly does not happen.

    Args:
        cmd (Command): Facade to act through.
        shop_id (int): Shop to buy from.
        item (int | str): Item to buy, by name or by item id.  The reference has
            an overload for each, and some shop entries are only ever named by
            id -- ``CoreVHL``'s Citadel shop 44, item 38316, is one.
        qty (int): How many to buy.
        map_name (str | None): Map the shop is in.  Without it the shop is asked
            for wherever the character happens to be.
        shop_item_id (int): Which entry to buy when the shop carries the same
            item more than once, as merge shops do.  The reference's
            ``parseShopItem`` looks this up before anything else and treats it as
            the answer, so it is honoured the same way here.

    Returns:
        bool: True when the buy packet was sent, or when the id form found the
        item already in hand.  False is reported, with the reason: the map could
        not be reached, the shop never loaded, or the item is not in it.
    """
    if isinstance(item, int) and await cmd.has_item_id(item):
        # BuyItem(int itemID) opens with CheckInventory(itemID, quant); every
        # call site here asks for one, which is what has_item_id answers for
        return True

    if map_name:
        while cmd.is_still_connected() and cmd.is_not_in_map(map_name):
            await cmd.join_map(map_name)
            await cmd.sleep(1000)
        if not cmd.is_still_connected():
            cmd.bot.log(f"[core] disconnected while joining {map_name}; {item!r} "
                  f"was not bought.")
            return False

    if not await cmd.ensure_load_shop(shop_id):
        cmd.bot.log(f"[core] shop {shop_id} never loaded; {item!r} was not bought.")
        return False
    wanted = _resolve_shop_item(cmd, _find_shop(cmd, shop_id), item, shop_item_id)
    if wanted is None:
        return False
    await cmd.buy_item(shop_id, wanted.item_name, qty,
                       shop_item_id=wanted.shop_item_id)
    return True


async def load_shop_entry(cmd: Command, shop_id: int, item: Union[int, str],
                          map_name: Optional[str] = None,
                          shop_item_id: int = 0):
    """Stand in the shop's map, load it, and resolve ``item`` in it.

    The step ``CoreBots.BuyItem`` and ``CoreAdvanced.BuyItem`` share -- the server
    only sends a shop in the map it lives in -- which leaves each of them only
    what its own purchase does.  Reports and returns None on any failure.
    """
    if map_name:
        while cmd.is_still_connected() and cmd.is_not_in_map(map_name):
            await cmd.join_map(map_name)
            await cmd.sleep(1000)
        if not cmd.is_still_connected():
            cmd.bot.log(f"[core] disconnected while joining {map_name}; {item!r} "
                        f"was not bought.")
            return None

    if not await cmd.ensure_load_shop(shop_id):
        cmd.bot.log(f"[core] shop {shop_id} never loaded; {item!r} was not "
                    f"bought.")
        return None
    return _resolve_shop_item(cmd, _find_shop(cmd, shop_id), item, shop_item_id)


def _resolve_shop_item(cmd: Command, shop, item: Union[int, str],
                       shop_item_id: int = 0):
    """The shop entry ``BuyItem`` would pick, or None (reported).

    ``parseShopItem`` tries the shop item id first -- merge shops carry one item
    under several ids and only that id tells them apart -- then the item id, then
    a name match, which it only accepts when it is unique.
    """
    if shop is None:
        cmd.bot.log("[core] the shop is not in the cache; nothing bought.")
        return None
    entries = list(shop.items)

    if shop_item_id:
        for entry in entries:
            if str(entry.shop_item_id) == str(shop_item_id):
                return entry
        cmd.bot.log(f"[core] shop {shop.shop_id} has no entry {shop_item_id}; falling "
              f"back to {item!r}.")

    if isinstance(item, int):
        for entry in entries:
            if str(entry.item_id) == str(item):
                return entry
        cmd.bot.log(f"[core] shop {shop.shop_id} does not carry item {item}; nothing "
              f"bought.")
        return None

    matches = [e for e in entries if e.item_name.lower() == str(item).lower()]
    if len(matches) > 1:
        cmd.bot.log(f"[core] shop {shop.shop_id} carries {item!r} {len(matches)} times; "
              f"pass shop_item_id to say which entry is meant.")
        return None
    if not matches:
        cmd.bot.log(f"[core] shop {shop.shop_id} does not carry {item!r}; nothing "
              f"bought.")
        return None
    return matches[0]


def dynamic_quant(cmd: Command, item: str, is_temp: bool = False) -> int:
    """``CoreBots.dynamicQuant``: how much of ``item`` the account holds.

    The reference sums the inventory and the bank, and only looks in the temp bag
    when told to; that is the number its "how many more do I need?" arithmetic
    wants.  An item lives in one of those at a time, so the engine's first-match
    lookups answer the same sum.
    """
    player = cmd.bot.player
    if is_temp:
        found = player.get_item_temp_inventory(item)
        return int(getattr(found, "qty", 0) or 0)

    total = 0
    for found in (player.get_item_inventory(item), player.get_item_bank(item)):
        if found is not None:
            total += int(getattr(found, "qty", 0) or 0)
    return total


#: How long :func:`wait_for_item` waits for a turn-in's reward to land.
PICKUP_WAIT_MS = 10_000

#: ``CoreBots.RepThresholds``: the reputation points each rank costs.  Rank is
#: ``PointsToLevel``-style, i.e. the first rank whose threshold the points reach.
REP_THRESHOLDS = (
    (1, 0), (2, 900), (3, 3600), (4, 10000), (5, 22500),
    (6, 44100), (7, 78400), (8, 129600), (9, 202500), (10, 302500),
)


def points_to_level(points: int) -> int:
    """``CoreBots.PointsToLevel``: the rank a reputation total earns.

    The reference walks its table and takes the first rank whose requirement the
    points reach, so 0 is rank 1, 44100 is rank 6, and anything at or above the
    last threshold is rank 10.
    """
    for rank, required in REP_THRESHOLDS:
        if points <= required:
            return rank
    return 10


def find_class_item(cmd: Command, class_name: str):
    """The class item with that name, from the inventory or the bank.

    ``CoreBots.CheckClassRank`` looks its class up in both, and insists the item
    is a class.
    """
    for candidate in list(cmd.bot.player.INVENTORY) + list(cmd.bot.player.BANK):
        if (candidate.s_name.strip().lower() == class_name.strip().lower()
                and candidate.s_es == ItemType.CLASS.value):
            return candidate
    return None


def check_class_rank(cmd: Command, class_name: Optional[str] = None,
                     current_class: bool = False) -> int:
    """``CoreBots.CheckClassRank``: a class's rank, read from its class points.

    The reference finds the class item in the inventory or the bank and walks its
    ``ClassPointRanks`` table -- the same thresholds as ``RepThresholds`` -- so
    under 900 is rank 1 and 302500 is rank 10.  A class that is not owned reports
    rank 1, as the source's fall-through does.

    Note:
        The source's ``CurrentClass`` branch returns a *client* value
        (``Bot.Player.CurrentClassRank``) rather than deriving it, so it is not
        ported here: derive the rank by passing the class name instead.  Whether
        this engine can read that client value at all is an open question.
    """
    if current_class and class_name is None:
        equipped = cmd.get_equipped_class()
        class_name = equipped.s_name if equipped else None
    if not class_name:
        return 1

    item = find_class_item(cmd, class_name)
    if item is None:
        return 1
    return points_to_level(int(item.qty))


async def wait_for_item(cmd: Command, item_name: str, quant: int = 1,
                        timeout_ms: int = PICKUP_WAIT_MS) -> bool:
    """``Bot.Wait.ForPickup`` as a bounded poll: True once the item is held.

    The reference blocks here after a turn-in until the reward reaches the
    inventory.  This engine polls, so the wait is bounded and a timeout is
    reported -- the drop is on its way, but a caller that assumed it had arrived
    would send the next packet against an inventory that does not have it yet.
    """
    waited = 0
    while cmd.is_still_connected() and waited < timeout_ms:
        if await cmd.has_item(item_name, quant):
            return True
        await cmd.sleep(500)
        waited += 500
    if cmd.is_still_connected():
        cmd.bot.log(f"[core] {item_name!r} has not arrived after {timeout_ms} ms; "
              f"continuing without it.")
    return False


async def equip_class(cmd: Command, solo: bool = False) -> bool:
    """Equip the configured farm or solo class (``CoreBots.EquipClass``).

    Args:
        cmd (Command): Facade to act through.
        solo (bool): ``True`` for the solo class, ``False`` for the farm one.

    Returns:
        bool: True when an item was equipped, False when no class is configured
        (the reference bot's ``ClassType`` had no such "unset" case -- its
        options always name one).  False is reported, because a farm that runs
        with the wrong class for hours is worse than a loud stop.
    """
    name = cmd.get_solo_class() if solo else cmd.get_farm_class()
    if not name:
        cmd.bot.log("[core] no class configured: set the farm/solo class before "
              "farming, or equip one by hand. Continuing anyway.")
        return False
    return await cmd.equip_item(name)


def can_we_aggro(cmd: Command) -> bool:
    """Aggro while another player shares the cell (``CoreBots.CanWeAggro``).

    The reference flips two *client* options here -- ``AggroMonsters`` and
    ``HidePlayers``.  This engine has nothing to hide players with, and asks the
    server to aggro instead, so what is reproduced is the decision: aggro when
    the cell is shared, stop when it is not.

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


# ---------------------------------------------------------------------------
# HuntMonsterQuest / GetMapItems / RegisterQuests
# ---------------------------------------------------------------------------
def _requirement_rows(quest) -> list:
    """A quest's requirements as ``[(item_id, name, qty, is_temp), ...]``.

    ``turnin`` is the authoritative requirement list (the same one
    :meth:`Quest.requirements_met` reads); its rows carry the id, the quantity
    and the temp flag.  Names are not always in ``turnin`` -- ``oItems`` is what
    carries them -- so the name is resolved by id from there, and a requirement
    whose name cannot be resolved is reported by the caller instead of being
    hunted under a guessed name.
    """
    names = {}
    for entry in getattr(quest, "items", []) or []:
        item_id = int(entry.get("ItemID") or entry.get("id") or 0)
        name = str(entry.get("sName") or entry.get("Name") or "")
        if item_id and name:
            names[item_id] = name

    rows = []
    for entry in getattr(quest, "turn_in_requirements", []) or []:
        item_id = int(entry.get("ItemID") or 0)
        qty = int(entry.get("iQty") or 1) or 1
        is_temp = bool(int(entry.get("bTemp") or 0))
        name = str(entry.get("sName") or names.get(item_id, ""))
        rows.append((item_id, name, qty, is_temp))
    return rows


def _held_by_id(cmd: Command, item_id: int, is_temp: bool) -> int:
    """How many of an item id the account holds, in the bag the quest uses."""
    player = cmd.bot.player
    item = None
    if is_temp:
        item = player.get_item_temp_inventory_by_id(item_id)
    item = item or player.get_item_inventory_by_id(item_id)
    return int(item.qty) if item is not None else 0


async def hunt_monster_quest(cmd: Command,
                             quest_id: int,
                             *targets: Tuple[str, str, bool],
                             log: bool = True) -> bool:
    """``CoreBots.HuntMonsterQuest``: farm a quest's requirements on given maps.

    The reference walks the quest's own requirement list and pairs each one with
    a ``(map, monster, classType)`` tuple from the caller; a requirement already
    held is skipped, and anything past the end of the tuple list is left alone.

    Args:
        cmd (Command): Facade to act through.
        quest_id (int): Quest to accept, farm and turn in.
        targets (Tuple[str, str, bool]): ``(map_name, monster_name, solo)`` per
            requirement, in the quest's order.
        log (bool): Kept for signature parity; hunts always report their map.

    Returns:
        bool: True when the quest was accepted, farmed and turned in.
    """
    if not await cmd.ensure_accept_quest(quest_id):
        cmd.bot.log(f"[core] quest {quest_id} cannot be accepted right now; "
                    f"nothing farmed.")
        return False
    quest = cmd.get_loaded_quest(quest_id)
    if quest is None:
        cmd.bot.log(f"[core] quest {quest_id} did not load; nothing farmed.")
        return False

    for index, (item_id, name, qty, is_temp) in enumerate(_requirement_rows(quest)):
        if _held_by_id(cmd, item_id, is_temp) >= qty:
            continue
        if index >= len(targets):
            break
        if not name:
            cmd.bot.log(f"[core] quest {quest_id} requirement {item_id} arrived "
                        f"without a name; cannot hunt it by name.")
            continue
        map_name, monster, solo = targets[index]
        await equip_class(cmd, solo=bool(solo))
        await hunt_item(cmd, name, qty, map_name, monster_name=monster or "*",
                        is_temp=is_temp)

    return await cmd.ensure_turn_in_quest(quest_id)


async def get_map_items(cmd: Command,
                        items: Sequence[Tuple[int, int]],
                        map_name: Optional[str] = None) -> None:
    """``CoreBots.GetMapItems``: click every map item, once per quantity.

    Args:
        cmd (Command): Facade to act through.
        items (Sequence[Tuple[int, int]]): ``(item_id, qty)`` pairs.
        map_name (str): Map to join first, when given.
    """
    if not items:
        return
    if map_name:
        await cmd.join_map(map_name)
    for item_id, qty in items:
        await cmd.get_map_item(item_id, qty)


async def register_quests(cmd: Command, *quest_ids: int) -> None:
    """``CoreBots.RegisterQuests``: register several quests for auto turn-in."""
    for quest_id in quest_ids:
        await cmd.register_quest(quest_id)


# ---------------------------------------------------------------------------
# SavedState -- hop to /whitemap on a 30-60 minute timer
# ---------------------------------------------------------------------------
SAVE_STATE_MIN_S = 30 * 60
SAVE_STATE_MAX_S = 60 * 60


def _save_state_interval_s() -> float:
    """``GetRandomInterval``: the 30-60 minute window, in seconds."""
    return random.uniform(SAVE_STATE_MIN_S, SAVE_STATE_MAX_S)


def saved_state(cmd: Command, on: bool = True, previous_map: str = "") -> None:
    """``CoreBots.SavedState``: arm or disarm the periodic save-state hop.

    Enabling needs a map to come back to; disabling never does -- the reference
    once returned on the empty map for both directions, so ``SavedState(false)``
    could not disarm it.

    Args:
        cmd (Command): Facade to act through.
        on (bool): True to arm, False to disarm.
        previous_map (str): Map to return to after the hop.
    """
    enabled = bool(getattr(cmd.bot, "save_state_enabled", False))
    if on:
        if not previous_map or enabled:
            return
        cmd.bot.save_state_enabled = True
        cmd.bot.save_state_map = previous_map
        cmd.bot.save_state_next = time.time() + _save_state_interval_s()
        cmd.bot.log("[core] SaveState [True] we'll randomly go to /whitemap to "
                    "save your progress every 30 minutes to an hour")
        return
    if not enabled:
        return
    cmd.bot.save_state_enabled = False
    cmd.bot.log("[core] SaveState [False]")


def check_save_state(cmd: Command) -> bool:
    """``CoreBots.CheckSaveState``: whether the save-state hop is due."""
    if not getattr(cmd.bot, "save_state_enabled", False):
        return False
    return time.time() >= getattr(cmd.bot, "save_state_next", 0)


async def execute_save_state(cmd: Command) -> None:
    """``CoreBots.ExecuteSaveState``: hop to the house map and come back."""
    if not getattr(cmd.bot, "save_state_enabled", False):
        return
    previous_map = getattr(cmd.bot, "save_state_map", "")
    if not previous_map:
        return
    await cmd.jump_cell("Enter", "Spawn")
    await cmd.join_map("whitemap", 100000)
    await cmd.join_map(previous_map)
    cmd.bot.save_state_next = time.time() + _save_state_interval_s()


async def hunt_monster_quest_single(cmd: Command,
                                    quest_id: int,
                                    map_name: str,
                                    monster: str,
                                    solo: bool = False,
                                    log: bool = True) -> bool:
    """``CoreBots.HuntMonsterQuest(questId, mapName, monsterName)``.

    The same map and monster serve every requirement, which is the overload a
    single-monster daily uses.
    """
    if not await cmd.ensure_accept_quest(quest_id):
        cmd.bot.log(f"[core] quest {quest_id} cannot be accepted right now; "
                    f"nothing farmed.")
        return False
    quest = cmd.get_loaded_quest(quest_id)
    if quest is None:
        cmd.bot.log(f"[core] quest {quest_id} did not load; nothing farmed.")
        return False
    targets = [(map_name, monster, solo)] * len(_requirement_rows(quest))
    return await hunt_monster_quest(cmd, quest_id, *targets, log=log)


# ---------------------------------------------------------------------------
# FarmingLogger / Equip / QuestRewards / ChainComplete / EnsureCompleteChoose
# ---------------------------------------------------------------------------
def farming_logger(cmd: Command, item: str, quant: int = 1) -> None:
    """``CoreBots.FarmingLogger``: how much of ``item`` is held, out of ``quant``.

    The reference counts the temp bag as well, because quest progress items land
    there; both bags are read here for the same reason.
    """
    held = 0
    if item:
        # ``Bot.TempInv.GetQuantity(item) + Bot.Inventory.GetQuantity(item)``:
        # the temp half is what ``dynamic_quant`` already answers, the inventory
        # half is the model's own lookup.
        held = dynamic_quant(cmd, item, is_temp=True)
        held += int(getattr(cmd.bot.player.get_item_inventory(item), "qty", 0)
                    or 0)
    cmd.bot.log(f"Farming {item} ({held}/{quant})")


async def equip_items(cmd: Command, *gear: str) -> None:
    """``CoreBots.Equip``: equip each named item, skipping what is already worn.

    Args:
        cmd (Command): Facade to act through.
        gear (str): Item names, in order; empty entries are skipped.
    """
    for name in gear:
        if not name or not name.strip():
            continue
        held = cmd.bot.player.get_item_inventory(name)
        if held is not None and held.is_equipped:
            continue
        if not await cmd.has_item(name):
            cmd.bot.log(f'Equipping Failed: "{name}" not found in Inventory or '
                        f'Bank')
            continue
        if not await cmd.equip_item(name):
            cmd.bot.log(f'Equipping Failed: "{name}" could not be equipped.')


def quest_rewards(cmd: Command, *quest_ids: int) -> List[str]:
    """``CoreBots.QuestRewards``: every reward name across the given quests."""
    names: List[str] = []
    for quest_id in quest_ids:
        for name in cmd.get_quest_rewards(quest_id):
            if name not in names:
                names.append(name)
    return names


async def chain_complete(cmd: Command, quest: int,
                         item_id: int = -1) -> bool:
    """``CoreBots.ChainComplete``: accept and complete a no-requirement quest.

    The reference's version exists for quests that only ask to be turned in
    (592, 10047, 1213, 1238); ``item_id`` picks the reward when there is a
    choice.
    """
    if not await cmd.ensure_accept_quest(quest):
        cmd.bot.log(f"[core] quest {quest} cannot be accepted right now; "
                    f"nothing completed.")
        return False
    if not await cmd.ensure_turn_in_quest(quest, item_id):
        cmd.bot.log(f"[core] quest {quest} could not be turned in.")
        return False
    return True


async def ensure_complete_choose(cmd: Command, quest_id: int,
                                 *item_names: str) -> bool:
    """``CoreBots.EnsureCompleteChoose``: turn in, picking one reward by name.

    Args:
        cmd (Command): Facade to act through.
        quest_id (int): Quest whose reward choice is made.
        item_names (str): Candidate rewards, in the caller's order; the first one
            the quest actually offers is the one taken.

    Returns:
        bool: True when the turn-in went out.
    """
    quest = cmd.get_loaded_quest(quest_id)
    if quest is None:
        cmd.bot.log(f"[core] quest {quest_id} is not loaded, so no reward can "
                    f"be chosen.")
        return False
    offered = {name: item_id for item_id, name, _max in quest.reward_entries}
    for item_name in item_names:
        if item_name in offered:
            return await cmd.ensure_turn_in_quest(quest_id, offered[item_name])
    cmd.bot.log(f"[core] quest {quest_id} offers none of "
                f"{', '.join(item_names)}; not turned in.")
    return False


#: How many attack ticks :func:`kill_once` gives a kill before it reports.
KILL_ONE_TRIES = 60


async def kill_once(cmd: Command, map_name: str = "", cell: str = "",
                    pad: str = "Left", monster: str = "*") -> bool:
    """``Core.KillMonster(map, cell, pad, monster)``: one kill, with no item.

    The reference has kill helpers that take no item -- reputation farming, the
    Blade of Awe loop, ``Bot.Kill.Monster("*")`` in a class quest -- and
    ``hunt_item`` cannot express them because it needs an item name.  This is
    that mode: join, hold the cell, and attack until nothing in it is alive.

    Args:
        cmd (Command): Facade to act through.
        map_name (str): Map to join first, when given.
        cell (str): Cell to hold, when given.
        pad (str): Pad inside ``cell``.
        monster (str): Monster name, or ``"*"`` for whatever is there.

    Returns:
        bool: True when the cell came up empty (the kill landed or there was
        nothing to kill), False when the bounded loop ran out.
    """
    if map_name:
        await cmd.join_map(map_name)
    if cell:
        await cmd.jump_cell(cell, pad)

    for _ in range(KILL_ONE_TRIES):
        if not cmd.is_still_connected():
            return False
        here = str(getattr(cmd.bot.player, "CELL", "") or "").lower()
        alive = [mon for mon in cmd.bot.monsters
                 if (not here or str(mon.frame or "").lower() == here)
                 and mon.is_alive and mon.current_hp > 0
                 and (monster == "*" or mon.mon_name.lower() == monster.lower())]
        if alive:
            await cmd.use_next_skill(DEFAULT_SKILL_LIST, monster)
            continue
        if cell:
            return True
        # No cell was asked for, so this is a map-wide hunt: walk to the monster
        # when it is alive somewhere else instead of reporting an empty cell.
        elsewhere = [mon for mon in cmd.bot.monsters
                     if mon.is_alive and mon.current_hp > 0
                     and (monster == "*" or mon.mon_name.lower() == monster.lower())]
        if not elsewhere:
            return True
        await cmd.jump_to_monster(monster)

    cmd.bot.log(f"[core] nothing died in {map_name or 'this map'} "
                f"({monster}); carrying on.")
    return False


# ---------------------------------------------------------------------------
# DoomKitten
# ---------------------------------------------------------------------------
#: ``KillDoomKitten``'s recommended classes, in the reference's order.
DOT_CLASSES = (
    "Dragon of Time", "Blaze Binder", "FireLord Summoner",
    "ShadowStalker of Time", "ShadowWeaver of Time", "ShadowWalker of Time",
    "Infinity Knight", "Interstellar Knight", "Timeless Dark Caster",
    "Frostval Barbarian", "DeathKnight", "DragonSoul Shinobi",
    "Shadow Dragon Shinobi", "Legion Revenant", "Void Highlord",
)
DOOM_KITTEN_MAP = "doomkitten"


async def kill_doom_kitten(cmd: Command, item: str = None, quant: int = 1,
                           is_temp: bool = False, log: bool = True) -> None:
    """``CoreBots.KillDoomKitten``: fight DoomKitten until its drop lands.

    The reference equips the first owned class from its DoT list, then runs one
    of three class-specific skill rotations (Shinobi, BlazeBinder, generic).  The
    class pick and the map are reproduced here; the rotations are not -- this
    engine casts the caller's normal rotation -- so the fight is slower on those
    two classes, never wrong about what it is doing.

    Args:
        cmd (Command): Facade to act through.
        item (str): Drop to wait for; ``None`` kills once.
        quant (int): How many.
        is_temp (bool): Whether the drop lands in the temporary bag.
        log (bool): Kept for signature parity; the class pick always reports.
    """
    if item is not None and await cmd.has_item(item, quant, isTemp=is_temp):
        return

    owned = None
    for class_name in DOT_CLASSES:
        if await cmd.has_item(class_name):
            owned = class_name
            break
    if owned is not None:
        await cmd.equip_item(owned)
    else:
        cmd.bot.log("No recommended DoT class found - using the equipped class.")
        cmd.bot.log("Suggested Classes: " + ", ".join(DOT_CLASSES))

    await cmd.join_map(DOOM_KITTEN_MAP)

    if item is None:
        await kill_once(cmd, DOOM_KITTEN_MAP, monster="*")
        await cmd.sleep(500)
        return

    if await cmd.has_item(item, quant, isTemp=is_temp):
        return
    await kill_once(cmd, DOOM_KITTEN_MAP, monster="*")
    await wait_for_item(cmd, item, quant)


# ---------------------------------------------------------------------------
# Achievements
# ---------------------------------------------------------------------------
async def set_achievement(cmd: Command, achievement_id: int,
                          ia: str = "ia0") -> None:
    """``CoreBots.SetAchievement``: the badge packet.

    The reference reads the badge first -- ``Core.HasAchievement`` is a client
    ``world.getAchievement`` call -- and only sends when it is missing.  This
    engine has no client to ask, so the packet always goes out; the server keeps
    a badge it already has.

    Args:
        cmd (Command): Facade to act through.
        achievement_id (int): Badge id, e.g. ``22`` for Combat.
        ia (str): The badge page the reference passes as ``ia0``.
    """
    await cmd.send_packet(f"%xt%zm%setAchievement%{cmd.bot.areaId}%{ia}%"
                          f"{achievement_id}%1%")
