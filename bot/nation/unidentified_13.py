"""Farm Unidentified 13, which caps at 13.

Port of ``Nation/Materials/Unidentified13.cs``.
"""
from core.command import Command
from bot.nation.core_nation import farm_uni13_quest


async def main(cmd: Command):
    await farm_uni13_quest(cmd, 13)
