"""Farm Dark Crystal Shard.

Port of ``Nation/Materials/DarkCrystalShards.cs``.
"""
from core.command import Command
from bot.nation.core_nation import farm_dark_crystal_shard


async def main(cmd: Command):
    await farm_dark_crystal_shard(cmd, 1000)
