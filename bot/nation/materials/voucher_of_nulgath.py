"""Farm the member Voucher of Nulgath.

Port of ``Nation/Materials/VoucherofNulgath.cs``.
"""
from core.command import Command
from bot.nation.core_nation import farm_voucher


async def main(cmd: Command):
    await farm_voucher(cmd, True)
