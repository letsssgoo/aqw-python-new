"""Farm Unidentified 10 through Dirty Deeds Done Dirt Cheap (quest 7818).

Port of ``Nation/DirtyDeedsDoneDirtCheap.cs``.  Needs ``/towerofdoom10``
cleared and a solo class.

``SROE`` -- beli stok merge shop dengan satu tas penuh Unidentified 10.
    Not ported: ``True`` prints a notice and then still runs the base quest,
    rather than quietly doing less.  Leave it ``False`` until that route exists.
"""
from core.command import Command
from bot.nation.core_nation import dirty_deeds_done_dirt_cheap

#: Change per the note above.
QUANT = 1000
SROE = False


async def main(cmd: Command):
    await dirty_deeds_done_dirt_cheap(cmd, QUANT, SROE)
