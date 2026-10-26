"""Glacial Berserker -- the whole Glacera story, its reputation, then the class.

Port of ``Other/Classes/REP-based/GlacialBerserker.GetGB``: ``Glacera.DoAll()``,
``Farm.GlaceraREP()``, the purchase only when neither class item is owned, then
the rank-up.
"""
from bot.core_advanced import buy_item
from bot.core_advanced import rank_up_class as advance_class
from bot.core_farms import glacera_rep
from bot.story.glacera import do_all as glacera_do_all
from core.command import Command

GLACIAL_BERSERKER = "Glacial Berserker"
#: ``CheckInventory(new[] { 38049, 38084 }, any: true)`` -- either is the class.
CLASS_ITEM_IDS = (38049, 38084)
SHOP_MAP = "icewindpass"
SHOP_ID = 1339
SHOP_ITEM_ID = 22266


async def get_gb(cmd: Command, rank_up_class: bool = True) -> None:
    """``GlacialBerserker.GetGB``.

    Args:
        cmd (Command): Facade to act through.
        rank_up_class (bool): Carry the class to rank 10 afterwards.
    """
    if await cmd.has_item(GLACIAL_BERSERKER):
        if rank_up_class:
            await advance_class(cmd, GLACIAL_BERSERKER)
        return

    await glacera_do_all(cmd)
    await glacera_rep(cmd)

    owned = False
    for item_id in CLASS_ITEM_IDS:
        if await cmd.has_item_id(item_id):
            owned = True
            break
    if not owned:
        await buy_item(cmd, SHOP_ID, GLACIAL_BERSERKER, map_name=SHOP_MAP,
                       shop_item_id=SHOP_ITEM_ID)

    if rank_up_class:
        await advance_class(cmd, GLACIAL_BERSERKER)


async def main(cmd: Command):
    await get_gb(cmd)
