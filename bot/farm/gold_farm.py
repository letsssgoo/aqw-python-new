"""Gold Farm: honour hall for members, Battle Ground E for the rest.

Port of ``Farm/GoldFarm.cs``.  The logic lives in ``bot.core_farms``.

The reference also disables class swapping and starts its drop filter here.
Neither has an equivalent: the class is a manual choice in this engine, and the
drop whitelist is always on.
"""
from core.command import Command
from bot.core_bots import equip_class
from bot.core_farms import farm_gold

#: Gold to farm.
QUANT = 100_000_000


async def main(cmd: Command):
    await equip_class(cmd)
    await farm_gold(cmd, QUANT)
