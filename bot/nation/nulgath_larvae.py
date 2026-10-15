"""Farm Nulgath Larvae (quest 2566) rewards.

Port of ``Nation/NulgathLarvae.cs``.  With no item it maxes every reward the
quest offers; pass one to farm just that.
"""
from core.command import Command
from bot.nation.core_nation import nulgath_larvae


async def main(cmd: Command):
    await nulgath_larvae(cmd)
