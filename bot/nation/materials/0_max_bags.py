"""Farm the max stack of every Nation material, best route per account.

Port of ``Nation/Materials/0MaxBags.cs``.  The C# also seeds its own banking
blacklist first; this engine never auto-banks, so there is nothing to seed.
"""
from core.command import Command
from bot.nation.core_nation import (
    BAG_DROPS, farm_blood_gem, farm_dark_crystal_shard, farm_diamond_of_nulgath,
    farm_gem_of_nulgath, farm_tainted_gem, farm_totem_of_nulgath, farm_uni10,
    farm_uni13_quest, farm_voucher)


async def main(cmd: Command):
    cmd.add_drop(BAG_DROPS[:9])
    await farm_blood_gem(cmd)
    await farm_dark_crystal_shard(cmd)
    await farm_diamond_of_nulgath(cmd)
    await farm_totem_of_nulgath(cmd)
    await farm_gem_of_nulgath(cmd)
    await farm_tainted_gem(cmd)
    await farm_uni10(cmd)
    await farm_uni13_quest(cmd)
    await farm_voucher(cmd, True)
    await farm_voucher(cmd, False)
