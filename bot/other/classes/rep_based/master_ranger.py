"""Master Ranger -- ``Other/Classes/REP-based/MasterRanger.cs``.

A one-step class: bought from the Sandsea shop, then ranked up.  The rank-up is
``Adv.RankUpClass``, which needs the class rank -- this engine cannot read one --
so it is reported rather than guessed at, the same gap ``bot/core_farms`` reports
for its own ``rank_up_class`` argument.

The C# also calls ``Core.SetOptions`` around its entry point, which this port
replaces with the constants the launcher is given.
"""
from bot.core_bots import buy_item
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
        _rank_up(cmd, rank_up_class)
        return

    await buy_item(cmd, SANDSEA_SHOP, MASTER_RANGER_ITEM_ID,
                   map_name=SANDSEA_MAP,
                   shop_item_id=MASTER_RANGER_SHOP_ITEM_ID)
    _rank_up(cmd, rank_up_class)


def _rank_up(cmd: Command, rank_up_class: bool) -> None:
    """``Adv.RankUpClass``, which this engine cannot do for want of a class rank."""
    if not rank_up_class:
        return
    cmd.bot.log(f'[class] "{MASTER_RANGER}" would be ranked up here, but rank-up '
                f"work needs the class rank, which this engine cannot read; "
                f"skipping it. The class itself is unaffected.")


async def main(cmd: Command):
    """``MasterRanger.ScriptMain``."""
    await get_mr(cmd)
