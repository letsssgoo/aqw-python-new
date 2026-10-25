"""Dragonslayer -- the class from /lair shop 38.

Port of ``Other/Classes/Dragonslayer.GetDragonslayer``: Galanoth's Lair line
(quests 165-168), one purchase, then the rank-up.
"""
from bot.core_advanced import buy_item
from bot.core_advanced import rank_up_class as advance_class
from bot.story.lair import galanoth
from core.command import Command

DRAGONSLAYER = "Dragonslayer"
LAIR_MAP = "lair"
LAIR_SHOP = 38


async def get_dragonslayer(cmd: Command, rank_up_class: bool = True) -> None:
    """``Dragonslayer.GetDragonslayer``.

    Args:
        cmd (Command): Facade to act through.
        rank_up_class (bool): Carry the class to rank 10 afterwards.
    """
    if await cmd.has_item(DRAGONSLAYER):
        if rank_up_class:
            await advance_class(cmd, DRAGONSLAYER)
        return

    await galanoth(cmd)
    await buy_item(cmd, LAIR_SHOP, DRAGONSLAYER, map_name=LAIR_MAP)

    if rank_up_class:
        await advance_class(cmd, DRAGONSLAYER)


async def main(cmd: Command):
    await get_dragonslayer(cmd)
