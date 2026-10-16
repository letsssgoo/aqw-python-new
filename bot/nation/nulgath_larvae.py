"""Farm Nulgath Larvae (quest 2566) rewards.

Port of ``Nation/NulgathLarvae.cs``.  With ``ITEM = None`` it maxes every reward
the quest offers; set a name to farm just that one.

``ITEM`` must be one of quest 2566's rewards.  The list only exists once the
quest is accepted, and the payload decides it -- so leave ``None`` when unsure:
that farms them all anyway, and a name that is not on the list is reported.
"""
from core.command import Command
from bot.nation.core_nation import nulgath_larvae

#: ``None`` for all of them, or one quest 2566 reward.
ITEM = None
QUANT = 1


async def main(cmd: Command):
    await nulgath_larvae(cmd, ITEM, QUANT)
