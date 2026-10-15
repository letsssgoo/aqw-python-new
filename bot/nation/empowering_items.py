"""Farm the Death Scythe of Nulgath (quest 558).

Port of ``Nation/EmpoweringItems.cs``.
"""
from core.command import Command
from bot.nation.core_nation import empowering_items


async def main(cmd: Command):
    await empowering_items(cmd)
