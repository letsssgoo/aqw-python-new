"""Farm Gem of Nulgath.

Port of ``Nation/Materials/GemofNulgath.cs``.
"""
from core.command import Command
from bot.nation.core_nation import farm_gem_of_nulgath


async def main(cmd: Command):
    await farm_gem_of_nulgath(cmd, 1000)
