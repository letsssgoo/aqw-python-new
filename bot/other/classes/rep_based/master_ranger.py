"""Master Ranger -- ``Other/Classes/REP-based/MasterRanger.cs``.

A one-step class: bought from the Sandsea shop, then ranked up with
``Adv.RankUpClass`` (:func:`bot.core_advanced.rank_up_class`).

The C# also calls ``Core.SetOptions`` around its entry point, which this port
replaces with the constants the launcher is given.
"""
from bot.core_advanced import buy_item, rank_up_class as advance_class
from core.command import Command

MASTER_RANGER = "Master Ranger"

#: ``Adv.BuyItem("sandsea", 242, 7260, shopItemID: 5682)``.
SANDSEA_MAP = "sandsea"
SANDSEA_SHOP = 242
MASTER_RANGER_ITEM_ID = 7260
MASTER_RANGER_SHOP_ITEM_ID = 5682


async def get_mr(cmd: Command, rank_up_class: bool = True) -> None:
    """``MasterRanger.GetMR``: buy the class if it is missing, then rank it up."""
    if await cmd.has_item(MASTER_RANGER):
        await _rank_up(cmd, rank_up_class)
        return

    await buy_item(cmd, SANDSEA_SHOP, MASTER_RANGER_ITEM_ID,
                   map_name=SANDSEA_MAP,
                   shop_item_id=MASTER_RANGER_SHOP_ITEM_ID)
    await _rank_up(cmd, rank_up_class)


async def _rank_up(cmd: Command, rank_up_class: bool) -> None:
    """``Adv.RankUpClass``, which keeps the class on while the arena ranks it."""
    if not rank_up_class:
        return
    await advance_class(cmd, MASTER_RANGER)


async def main(cmd: Command):
    """``MasterRanger.ScriptMain``."""
    await get_mr(cmd)
