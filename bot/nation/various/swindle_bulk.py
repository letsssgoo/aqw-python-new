"""Tainted Gem through Swindle's Bulk Deal.

Port of ``Nation/Various/SwindleBulk.cs``, which is one line around
``CoreNation.SwindleBulk``.  The logic lives in
``bot.nation.core_nation.swindle_bulk``.

The reference's ``CoreNation.SwindlesBilk`` -- a near-namesake -- only whitelists
its drops and does nothing else, so there is nothing to port from it.
"""
from core.command import Command
from bot.nation.core_nation import swindle_bulk

#: Tainted Gems to farm.  A multiple of 25 takes the bulk quest (7817).
QUANT = 1000


async def main(cmd: Command):
    await swindle_bulk(cmd, QUANT)
