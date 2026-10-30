"""Scroll stock and equipping for Ultra V2.

The reference's ``PrepareScrolls`` wants a safety stock before the first pull:
80 Scrolls of Enrage (they feed the taunt every attempt), or 10 of the optional
Decay / Mystify.  ``EquipScroll`` then puts one in slot 5.

What is **not** ported yet, and is reported by name instead of faked: the
crafting half of ``PrepareScrolls`` (``SpellCrafting`` rank 5, gold-voucher
turn-ins for Enrage, the farmed materials for Decay/Mystify).  When the stock is
short the run says how many it has, how many it needs, and stops there --
buying or crafting scrolls is a separate job.
"""
from __future__ import annotations

from typing import Optional

ENRAGE = "Scroll of Enrage"
DECAY = "Scroll of Decay"
MYSTIFY = "Scroll of Mystify"

#: ``CoreLoneWolf``'s stock levels.
ENRAGE_THRESHOLD = 80
OPTIONAL_SCROLL_THRESHOLD = 10

SUPPORTED = (ENRAGE, DECAY, MYSTIFY)


def threshold(name: str) -> int:
    return ENRAGE_THRESHOLD if name == ENRAGE else OPTIONAL_SCROLL_THRESHOLD


async def prepare(cmd, name: Optional[str]) -> bool:
    """Make sure the account holds the reference's stock of ``name``.

    Returns True when it does (or when it can be brought over from the bank).
    """
    if not name:
        return True
    if name not in SUPPORTED:
        cmd.bot.log(f"[v2] scroll {name!r} is not supported; nothing prepared.")
        return False

    wanted = threshold(name)
    held = await _quantity(cmd, name)
    if held >= wanted:
        cmd.bot.log(f"[v2] {name} already available ({held}/{wanted}).")
        return True
    if cmd.is_in_bank(name):
        await cmd.bank_to_inv(name)
        held = await _quantity(cmd, name)
        if held >= wanted:
            cmd.bot.log(f"[v2] {name} withdrawn from the bank ({held}/{wanted}).")
            return True

    cmd.bot.log(f"[v2] {name} x{held} < {wanted}; scroll crafting is not ported "
                f"yet, so this run stops instead of starting short. Bring "
                f"{wanted - held} more.")
    return False


async def equip(cmd, name: Optional[str]) -> bool:
    """Put a scroll in slot 5, saying why when it cannot."""
    if not name:
        return True
    if name not in SUPPORTED:
        cmd.bot.log(f"[v2] scroll {name!r} is not supported.")
        return False
    if not await cmd.has_item(name):
        if cmd.is_in_bank(name):
            await cmd.bank_to_inv(name)
        if not await cmd.has_item(name):
            cmd.bot.log(f"[v2] {name} is not in the inventory, so slot 5 keeps "
                        f"what it had.")
            return False
    equipped = await cmd.equip_scroll(name)
    if equipped:
        cmd.bot.log(f"[v2] {name} equipped.")
    else:
        cmd.bot.log(f"[v2] {name} could not be equipped.")
    return equipped


async def _quantity(cmd, name: str) -> int:
    item = cmd.bot.player.get_item_inventory(name)
    return int(getattr(item, "qty", 0) or 0) if item else 0
