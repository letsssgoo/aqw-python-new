"""Farm quest 6697 / 6183 rewards with the Birthday Gift or Drone pet.

Port of ``Nation/NewWorldsNewOpportunities.cs``.  With no item it maxes every
reward the quest offers.
"""
from core.command import Command
from bot.nation.core_nation import new_worlds_new_opportunities


async def main(cmd: Command):
    await new_worlds_new_opportunities(cmd)
