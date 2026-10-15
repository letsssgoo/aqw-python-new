"""Evolved Blood Orb -- gather the parts, then buy it in /archportal.

Port of ``Nation/EvolvedOrb/EvolvedBloodOrb.cs``.

The reference passes the item *id* (33196) and a shop item id (4181); the shop
lookup here is by name, and ``Evolved Blood Orb`` is the name it checks for at
the top and the one the shop carries.
"""
from core.command import Command
from bot.core_bots import buy_item
from bot.nation.core_nation import (approval_and_favor, farm_diamond_of_nulgath,
                                    farm_totem_of_nulgath, farm_uni13_quest,
                                    farm_voucher)

#: Shop and item.
SHOP_ID = 1211
ITEM = "Evolved Blood Orb"

#: Reference quantities, in the order the reference farms them.
UNI_13 = 3
TOTEMS = 10
DIAMONDS = 30


async def main(cmd: Command):
    if await cmd.has_item(ITEM):
        return

    await approval_and_favor(cmd, 200, 0)
    await farm_uni13_quest(cmd, UNI_13)
    await farm_voucher(cmd, False)
    await farm_totem_of_nulgath(cmd, TOTEMS)
    await farm_diamond_of_nulgath(cmd, DIAMONDS)
    await buy_item(cmd, SHOP_ID, ITEM)
