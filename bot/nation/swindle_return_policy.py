"""Farm quest 7551 (Swindle's Return Policy) rewards.

Port of ``Nation/SwindlesReturnPolicy.cs``.  That script exposes a reward
choice; ``swindle_return`` takes the reward name directly, so pass the one you
want -- the default here is the first reward quest 7551 offers.
"""
from core.command import Command
from bot.nation.core_nation import swindle_return


async def main(cmd: Command):
    await swindle_return(cmd)
