"""Farm the Time is Money quest rewards (quest 6185).

Port of ``Nation/TimeIsMoney.cs``.  Needs the Bounty Hunter Blade Pet.
"""
from core.command import Command
from bot.nation.core_nation import time_is_money


async def main(cmd: Command):
    await time_is_money(cmd)
