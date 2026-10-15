"""Farm Emblem of Nulgath in Shadow Blast Arena (quest 4748).

Port of ``Nation/EmblemofNulgath.cs``.
"""
from core.command import Command
from bot.nation.core_nation import emblem_of_nulgath


async def main(cmd: Command):
    await emblem_of_nulgath(cmd, 500)
