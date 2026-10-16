"""Yulgath's Inn -- gathered parts, then bought in /archportal.

Port of ``Nation/Various/YulgathsInn.cs``.

One part is a drop rather than a purchase: ``Yulgath's Hut`` off the Fiend
Champion in ``/originul``.
"""
from core.command import Command
from bot.core_bots import buy_item
from bot.nation.core_nation import (farm_dark_crystal_shard,
                                    farm_diamond_of_nulgath, farm_tainted_gem,
                                    farm_uni10, farm_uni13_quest, farm_voucher)
from templates.hunt import hunt_item

#: Shop and item.
SHOP_ID = 1211
ITEM = "Yulgath's Inn"
HUT = "Yulgath's Hut"

#: Reference quantities, in the order the reference farms them.
UNI_10 = 400
TAINTED = 200
SHARDS = 250
DIAMONDS = 200
UNI_13 = 1


async def main(cmd: Command):
    if await cmd.has_item(ITEM):
        return

    cmd.add_drop([HUT, ITEM])
    await hunt_item(cmd, HUT, 1, "originul", monster_name="Fiend Champion",
                    is_temp=False)
    await farm_uni10(cmd, UNI_10)
    await farm_tainted_gem(cmd, TAINTED)
    await farm_dark_crystal_shard(cmd, SHARDS)
    await farm_diamond_of_nulgath(cmd, DIAMONDS)
    await farm_uni13_quest(cmd, UNI_13)
    await farm_voucher(cmd, False)
    await buy_item(cmd, SHOP_ID, ITEM, map_name="archportal")
