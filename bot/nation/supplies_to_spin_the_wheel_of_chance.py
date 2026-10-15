"""Farm quest 2857 (Supplies to Spin the Wheel of Chance) and its extras.

Port of ``Nation/SuppliesToSpinTheWheelofChance.cs``.  The C# script exposes
its options as checkboxes; ``supplies`` takes them as arguments, so edit the
call below to change route (ultra / hydra / keep-voucher / return policy).
"""
from core.command import Command
from bot.nation.core_nation import supplies


async def main(cmd: Command):
    await supplies(cmd)
