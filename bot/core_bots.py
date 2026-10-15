"""The reference bot's ``CoreBots``: the helpers every other core leans on.

Port of ``CoreBots.cs``, kept in ``bot/`` next to the other root cores because
that is where the reference keeps it.  Only the parts the ported cores actually
call live here so far:

======================  ==================================================
``Alignment``           the Good / Evil / Chaos enum
``change_alignment``    ``CoreBots.ChangeAlignment``
``equip_class``         ``CoreBots.EquipClass``
``can_we_aggro``        ``CoreBots.CanWeAggro``
======================  ==================================================

``bot.nation.core_nation`` re-exports ``equip_class`` and ``can_we_aggro`` from
here, so its call sites and tests keep the names they had.
"""
from enum import Enum
from typing import Optional

from core.command import Command


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


async def buy_item(cmd: Command, shop_id: int, item_name: str,
                   qty: int = 1) -> bool:
    """Buy an item from a shop, once the shop is loaded and carries it.

    ``CoreBots.BuyItem`` waits for the shop and then buys.  This engine splits
    that in two -- ``Command.ensure_load_shop`` for the wait and
    ``Command.buy_item`` for the buy -- and ``Command.buy_item`` on its own does
    the *first* half when it has not seen the shop: it asks the server for it and
    returns, so that call buys nothing, silently.  This is the whole of it, plus
    the check the engine does without: whether the shop carries the name at all.

    Args:
        cmd (Command): Facade to act through.
        shop_id (int): Shop to buy from.
        item_name (str): Item to buy; must be in the shop.
        qty (int): How many to buy.

    Returns:
        bool: True when the buy packet was sent.  False is reported, with the
        reason: a shop that never loaded, or an item the shop does not carry.
    """
    if not await cmd.ensure_load_shop(shop_id):
        print(f"[core] shop {shop_id} never loaded; {item_name!r} was not bought.")
        return False
    shop = _find_shop(cmd, shop_id)
    if shop is None or not any(i.item_name == item_name.lower()
                               for i in shop.items):
        print(f"[core] shop {shop_id} does not carry {item_name!r}; nothing "
              f"bought.")
        return False
    await cmd.buy_item(shop_id, item_name, qty)
    return True


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
