"""Farm Diamond of Nulgath.

Port of ``Nation/Materials/DiamondofNulgath.cs``.
"""
from core.command import Command
from bot.nation.core_nation import farm_diamond_of_nulgath


async def main(cmd: Command):
    await farm_diamond_of_nulgath(cmd, 1000)
