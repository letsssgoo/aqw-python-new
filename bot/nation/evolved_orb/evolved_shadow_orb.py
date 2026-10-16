"""Evolved Shadow Orb [Mem] -- members only, gathered then bought in /archportal.

Port of ``Nation/EvolvedOrb/EvolvedShadowOrb[Mem].cs``.

Unlike its two siblings this one farms *both* voucher variants, which is why it
is the member-only orb.
"""
from core.command import Command
from bot.core_bots import buy_item
from bot.nation.core_nation import (approval_and_favor, farm_gem_of_nulgath,
                                    farm_totem_of_nulgath, farm_uni13_quest,
                                    farm_voucher)

#: Shop, its map, and the item.
SHOP_ID = 1211
SHOP_MAP = "archportal"
ITEM = "Evolved Shadow Orb"

#: Reference quantities, in the order the reference farms them.
UNI_13 = 3
TOTEMS = 10
GEMS = 20


async def main(cmd: Command):
    if await cmd.has_item(ITEM):
        return
    if not cmd.get_player().is_member:
        cmd.bot.log("[nation] the Evolved Shadow Orb is members only; nothing farmed.")
        return

    await approval_and_favor(cmd, 200, 0)
    await farm_uni13_quest(cmd, UNI_13)
    await farm_voucher(cmd, False)
    await farm_voucher(cmd, True)
    await farm_totem_of_nulgath(cmd, TOTEMS)
    await farm_gem_of_nulgath(cmd, GEMS)
    await buy_item(cmd, SHOP_ID, ITEM, map_name=SHOP_MAP)
