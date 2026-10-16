"""Farm quest 6697 / 6183 rewards with the Birthday Gift or Drone pet.

Port of ``Nation/NewWorldsNewOpportunities.cs``.  With ``ITEM = None`` it maxes
every reward the quest offers.

``ITEM`` must be one of quest 6183's rewards (with the Bounty Hunter's Drone
Pet) or 6697's.  The list only exists once the quest is accepted, so leave
``None`` when unsure -- that farms them all anyway.
"""
from core.command import Command
from bot.nation.core_nation import new_worlds_new_opportunities

#: ``None`` for all of them, or one reward name.
ITEM = None
QUANT = 1


async def main(cmd: Command):
    await new_worlds_new_opportunities(cmd, ITEM, QUANT)
