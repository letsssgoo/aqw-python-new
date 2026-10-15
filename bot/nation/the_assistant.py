"""Farm quest 2859 (The Assistant) rewards, spending gold on War-Torn Memorabilia.

Port of ``Nation/TheAssistant.cs``.  With no item it maxes every principal drop
the quest offers; pass one to farm just that.

The C# script also has a ``farmGold`` toggle and a Swindle's Return reward
picker; both are arguments on ``the_assistant``.
"""
from core.command import Command
from bot.nation.core_nation import the_assistant


async def main(cmd: Command):
    await the_assistant(cmd)
