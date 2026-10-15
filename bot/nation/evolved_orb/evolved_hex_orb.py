"""Evolved Hex Orb -- gather the parts, then buy it in /archportal.

Port of ``Nation/EvolvedOrb/EvolvedHexOrb.cs``.
"""
from core.command import Command
from bot.core_bots import buy_item
from bot.nation.core_nation import (approval_and_favor,
                                    farm_dark_crystal_shard,
                                    farm_tainted_gem, farm_totem_of_nulgath,
                                    farm_uni13_quest, farm_voucher)

#: Shop and item.
SHOP_ID = 1211
ITEM = "Evolved Hex Orb"

#: Reference quantities, in the order the reference farms them.
UNI_13 = 3
TOTEMS = 10
SHARDS = 30
TAINTED = 30


async def main(cmd: Command):
    if await cmd.has_item(ITEM):
        return

    await approval_and_favor(cmd, 200, 0)
    await farm_uni13_quest(cmd, UNI_13)
    await farm_voucher(cmd, False)
    await farm_totem_of_nulgath(cmd, TOTEMS)
    await farm_dark_crystal_shard(cmd, SHARDS)
    await farm_tainted_gem(cmd, TAINTED)
    await buy_item(cmd, SHOP_ID, ITEM)
