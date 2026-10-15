"""Farm Tainted Gem.

Port of ``Nation/Materials/TaintedGem.cs``.  ``farm_tainted_gem`` announces the
one route it cannot take yet -- the member Forge quest, which needs the
Vampire rep and gold farms.
"""
from core.command import Command
from bot.nation.core_nation import farm_tainted_gem


async def main(cmd: Command):
    await farm_tainted_gem(cmd, 1000)
