"""Farm Dark Crystal Shards through Essence of Defeat Reagent (quest 570).

Port of ``Nation/EssenceofDefeatReagent.cs``.
"""
from core.command import Command
from bot.nation.core_nation import essence_of_defeat_reagent


async def main(cmd: Command):
    await essence_of_defeat_reagent(cmd, 1000)
