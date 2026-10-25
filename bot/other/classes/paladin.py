"""Paladin -- Warrior + Healer ranked, Good rep, then the class.

Port of ``Good/Paladin.GetPaladin``: members only, all purchases from the
/necropolis shop 26.
"""
from bot.core_advanced import buy_item
from bot.core_advanced import rank_up_class as advance_class
from bot.core_farms import good_rep
from core.command import Command

PALADIN = "Paladin"
SHOP_MAP = "necropolis"
SHOP_ID = 26


async def get_paladin(cmd: Command, rank_up_class: bool = True) -> None:
    """``Paladin.GetPaladin``.

    Args:
        cmd (Command): Facade to act through.
        rank_up_class (bool): Carry the class to rank 10 afterwards.
    """
    if await cmd.has_item(PALADIN) or not cmd.get_player().is_member:
        return

    await buy_item(cmd, SHOP_ID, "Warrior", map_name=SHOP_MAP)
    await buy_item(cmd, SHOP_ID, "Healer", map_name=SHOP_MAP)
    await advance_class(cmd, "Warrior")
    await advance_class(cmd, "Healer")

    await good_rep(cmd, 5)

    await buy_item(cmd, SHOP_ID, PALADIN, map_name=SHOP_MAP)
    if rank_up_class:
        await advance_class(cmd, PALADIN)


async def main(cmd: Command):
    await get_paladin(cmd)
