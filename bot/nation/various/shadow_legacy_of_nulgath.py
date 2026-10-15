"""Shadow Legacy of Nulgath -- gather the parts, then buy it in /archportal.

Port of ``Nation/Various/ShadowLegacyofNulgath.cs``.  No quest of its own: the
five steps below feed a shop purchase.

The reference also adds both items to its ``BankingBlackList``.  This engine has
no auto-bank task, so there is nothing to blacklist.
"""
from core.command import Command
from bot.core_bots import buy_item
from bot.core_farms import farm_gold
from bot.nation.core_nation import (approval_and_favor, essence_of_nulgath,
                                    supplies)
from templates.hunt import hunt_item

#: Shop and item.
SHOP_ID = 1211
ITEM = "Shadow Legacy of Nulgath"

#: Gold the reference farms before the purchase.
GOLD = 3_000_000


async def main(cmd: Command):
    if await cmd.has_item(ITEM):
        return

    cmd.add_drop([ITEM, "Letter from Asuka and Tendou"])
    await approval_and_favor(cmd, 100, 0)
    await supplies(cmd, "Voucher of Nulgath (non-mem)")
    await essence_of_nulgath(cmd, 100)
    await hunt_item(cmd, "Hadean Onyx of Nulgath", 1, "tercessuinotlim",
                    cell="m4", pad="Right", monster_name="Shadow of Nulgath",
                    is_temp=False)
    await hunt_item(cmd, "Letter from Asuka and Tendou", 1, "Citadel",
                    monster_name="Burning Witch", is_temp=False)
    await farm_gold(cmd, GOLD)
    await buy_item(cmd, SHOP_ID, ITEM, map_name="archportal")
