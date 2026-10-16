"""Farm Tainted Gems through the Dreadrock Gem Exchange (quest 4853).

Port of ``Nation/DreadrockGemExchange.cs``.
"""
from core.command import Command
from bot.nation.core_nation import dreadrock_gem_exchange


async def main(cmd: Command):
    await dreadrock_gem_exchange(cmd, 1000)
