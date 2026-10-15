"""Farm Totem of Nulgath.

Port of ``Nation/Materials/TotemofNulgath.cs``.  The C# has a commented-out
option block choosing between Taro and the Voucher item; ``farm_totem_of_nulgath``
runs Deal first and falls back to Taro's chain, which is the live path.
"""
from core.command import Command
from bot.nation.core_nation import farm_totem_of_nulgath


async def main(cmd: Command):
    await farm_totem_of_nulgath(cmd, 100)
