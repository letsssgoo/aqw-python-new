"""Blood Sorceress -- class item 36298, a drop in /towerofmirrors.

Port of ``Other/Classes/BloodSorceress.GetBSorc``: one kill on the Groglurk
(monster map id 32) at ``r16/Top``, then the class is ranked up by id.
"""
from bot.core_advanced import rank_up_class as advance_class
from bot.core_bots import equip_class
from core.command import Command
from templates.hunt import hunt_item_by_id

BLOOD_SORCERESS = "Blood Sorceress"
BLOOD_SORCERESS_ITEM = 36298
MAP = "towerofmirrors"
CELL, PAD = "r16", "Top"
#: The Groglurk, the monster this class drops from.
MONSTER_MAP_ID = 32


async def get_bsorc(cmd: Command, rank_up_class: bool = True) -> None:
    """``BloodSorceress.GetBSorc``.

    Args:
        cmd (Command): Facade to act through.
        rank_up_class (bool): Carry the class to rank 10 afterwards.
    """
    if await cmd.has_item_id(BLOOD_SORCERESS_ITEM):
        if rank_up_class:
            await advance_class(cmd, item_id=BLOOD_SORCERESS_ITEM)
        return

    await equip_class(cmd, solo=True)
    await hunt_item_by_id(cmd, BLOOD_SORCERESS_ITEM, 1, MAP, cell=CELL, pad=PAD,
                          monster_map_id=MONSTER_MAP_ID, is_temp=False)

    if rank_up_class:
        await advance_class(cmd, item_id=BLOOD_SORCERESS_ITEM)


async def main(cmd: Command):
    await get_bsorc(cmd)
