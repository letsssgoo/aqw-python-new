"""Void Chasm Merge -- shop 2410 in /voidchasm, only what Ravenous needs.

Port of ``Nation/MergeShops/VoidChasmMerge.cs``.  The merge walk itself is the
engine's generic :func:`bot.core_advanced.start_buy_all_merge`; this file owns
the ingredients the shop does not sell:

* **Void Remnant** -- quest **9553** in ``/voidchasm``: ``r10/Left`` Carcano for
  ``Carcano's Teratoma``, ``r9/Left`` Carnage for ``Bloodied Chainlink``, then
  ``r7/Left`` The Hushed for **6** ``Defunct Seal of Approval``;
* **Tainted Gem** and **Essence of Nulgath** -- the Nation farms.

The reference also runs ``VoidChasm.Storyline()`` first.  That chain is not
ported here: the quest-9553 accept is the gate instead, and it says so when the
storyline is missing rather than farming blind.
"""
from typing import Optional

from bot.core_advanced import start_buy_all_merge
from bot.nation.core_nation import essence_of_nulgath, farm_tainted_gem
from core.command import Command
from templates.hunt import hunt_item

MAP = "voidchasm"
SHOP_ID = 2410
PRIME_FIEND_SHARD = "Prime Fiend Shard"

#: ``Void Remnant``'s quest and the three drops one pass of it wants.
VOID_REMNANT_QUEST = 9553
VOID_REMNANT = "Void Remnant"
CARCANO_HUNT = ("Carcano's Teratoma", "r10", "Left", "Carcano", 1)
CARNAGE_HUNT = ("Bloodied Chainlink", "r9", "Left", "Carnage", 1)
HUSHED_HUNT = ("Defunct Seal of Approval", "r7", "Left", "The Hushed", 6)


async def _farm_void_remnant(cmd: Command, quantity: int) -> None:
    """``case "Void Remnant"``: repeat quest 9553 until the stack is there."""
    cmd.add_drop(VOID_REMNANT)
    while (cmd.is_still_connected()
           and not await cmd.has_item(VOID_REMNANT, quantity)):
        if not await cmd.ensure_accept_quest(VOID_REMNANT_QUEST):
            cmd.bot.log(f"[voidchasm] quest {VOID_REMNANT_QUEST} cannot be "
                        f"accepted; the Void Chasm storyline is not done.")
            return
        for item, cell, pad, monster, count in (CARCANO_HUNT, CARNAGE_HUNT,
                                                HUSHED_HUNT):
            await hunt_item(cmd, item, count, MAP, cell=cell, pad=pad,
                            monster_name=monster, is_temp=False)
        await cmd.ensure_turn_in_quest(VOID_REMNANT_QUEST)
        await cmd.sleep(1000)


async def find_ingredients(cmd: Command, item_id: int, name: str,
                           quantity: int) -> None:
    """The merge script's own farmer for what shop 2410 does not sell."""
    if name == VOID_REMNANT:
        await _farm_void_remnant(cmd, quantity)
    elif name == "Tainted Gem":
        await farm_tainted_gem(cmd, quantity)
    elif name == "Essence of Nulgath":
        await essence_of_nulgath(cmd, quantity)
    else:
        # The reference stops on an unknown ingredient ("The bot hasn't been
        # taught how to get ..."); say the same thing instead of guessing.
        cmd.bot.log(f"[voidchasm] no farm is known for {name!r}; it was not "
                    f"obtained.")


async def void_chasm_merge(cmd: Command,
                           buy_only_this: Optional[str] = None) -> None:
    """``VoidChasmMerge.BuyAllMerge``."""
    await start_buy_all_merge(cmd, MAP, SHOP_ID, find_ingredients,
                              buy_only_this)


async def buy_prime_fiend_shard(cmd: Command) -> None:
    """``VoidChasmMerge.BuyAllMerge("Prime Fiend Shard")``."""
    await void_chasm_merge(cmd, PRIME_FIEND_SHARD)


async def main(cmd: Command) -> None:
    """Standalone entry (``python -m bot.nation.merges.void_chasm_merge``)."""
    await void_chasm_merge(cmd)
