"""Farm Unidentified 10.

Port of ``Nation/Materials/Unidentified10.cs``.
"""
from core.command import Command
from bot.nation.core_nation import farm_uni10


async def main(cmd: Command):
    await farm_uni10(cmd, 1000)
