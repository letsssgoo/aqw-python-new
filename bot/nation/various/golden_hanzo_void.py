"""Golden Hanzo Void -- gather the parts, then buy it in /evilwarnul.

Port of ``Nation/Various/GoldenHanzoVoid.cs``.

The reference passes the item id (27843) and a shop item id (2694); the shop
lookup here is by name, which is the name it checks for at the top.
"""
from core.command import Command
from bot.core_bots import buy_item
from bot.nation.core_nation import (approval_and_favor,
                                    farm_diamond_of_nulgath, farm_tainted_gem,
                                    farm_voucher, the_assistant)

#: Shop and item.
SHOP_ID = 456
ITEM = "Golden Hanzo Void"

#: Reference quantities, in the order the reference farms them.
APPROVAL = 50
TAINTED = 45
SHARDS = 45
DIAMONDS = 75


async def main(cmd: Command):
    if await cmd.has_item(ITEM):
        return

    await approval_and_favor(cmd, APPROVAL, 0)
    await farm_tainted_gem(cmd, TAINTED)
    await the_assistant(cmd, "Dark Crystal Shard", SHARDS)
    await farm_diamond_of_nulgath(cmd, DIAMONDS)
    await farm_voucher(cmd, False)
    await buy_item(cmd, SHOP_ID, ITEM, map_name="evilwarnul")
