"""Farm Unidentified 10 through Dirty Deeds Done Dirt Cheap (quest 7818).

Port of ``Nation/DirtyDeedsDoneDirtCheap.cs``.  Needs ``/towerofdoom10``
cleared and a solo class.  The C# script also offers the SRoE merge-shop
branch; that is not ported and the core function says so if asked.
"""
from core.command import Command
from bot.nation.core_nation import dirty_deeds_done_dirt_cheap


async def main(cmd: Command):
    await dirty_deeds_done_dirt_cheap(cmd, 1000)
