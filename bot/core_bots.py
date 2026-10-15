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
======================  ==================================================

``bot.nation.core_nation`` re-exports ``equip_class`` and ``can_we_aggro`` from
here, so its call sites and tests keep the names they had.
"""
import json
from enum import Enum
from typing import Optional, Union

from core.command import Command
from core.utils import is_valid_json
from templates.hunt import DEFAULT_SKILL_LIST

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
            print(f"[core] disconnected while joining {map_name}; {item!r} "
                  f"was not bought.")
            return False

    if not await cmd.ensure_load_shop(shop_id):
        print(f"[core] shop {shop_id} never loaded; {item!r} was not bought.")
        return False
    wanted = _resolve_shop_item(_find_shop(cmd, shop_id), item, shop_item_id)
    if wanted is None:
        return False
    await cmd.buy_item(shop_id, wanted.item_name, qty,
                       shop_item_id=wanted.shop_item_id)
    return True


def _resolve_shop_item(shop, item: Union[int, str], shop_item_id: int = 0):
    """The shop entry ``BuyItem`` would pick, or None (reported).

    ``parseShopItem`` tries the shop item id first -- merge shops carry one item
    under several ids and only that id tells them apart -- then the item id, then
    a name match, which it only accepts when it is unique.
    """
    if shop is None:
        print("[core] the shop is not in the cache; nothing bought.")
        return None
    entries = list(shop.items)

    if shop_item_id:
        for entry in entries:
            if str(entry.shop_item_id) == str(shop_item_id):
                return entry
        print(f"[core] shop {shop.shop_id} has no entry {shop_item_id}; falling "
              f"back to {item!r}.")

    if isinstance(item, int):
        for entry in entries:
            if str(entry.item_id) == str(item):
                return entry
        print(f"[core] shop {shop.shop_id} does not carry item {item}; nothing "
              f"bought.")
        return None

    matches = [e for e in entries if e.item_name.lower() == str(item).lower()]
    if len(matches) > 1:
        print(f"[core] shop {shop.shop_id} carries {item!r} {len(matches)} times; "
              f"pass shop_item_id to say which entry is meant.")
        return None
    if not matches:
        print(f"[core] shop {shop.shop_id} does not carry {item!r}; nothing "
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
        print(f"[core] {item_name!r} has not arrived after {timeout_ms} ms; "
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
        print("[core] no class configured: set the farm/solo class before "
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
