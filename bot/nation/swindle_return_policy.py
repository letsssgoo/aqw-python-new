"""Farm quest 7551 (Swindle's Return Policy) rewards.

Port of ``Nation/SwindlesReturnPolicy.cs``.  That script picks the reward from
its options; with none given, ``swindle_return`` takes the first reward quest
7551 offers that is not maxed yet, rather than doing nothing.  Pass a name to
choose a specific one.
"""
from core.command import Command
from bot.nation.core_nation import swindle_return


async def main(cmd: Command):
    await swindle_return(cmd)
