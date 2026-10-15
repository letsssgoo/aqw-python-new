"""Trade spare Vouchers for Totems or Gems of Nulgath (quest 4778).

Port of ``Nation/VoucherItemChoose.cs``.  The C# script asks which reward to
take; here you set it below.

Choose one:
  * ``"Totem of Nulgath"``  -- cap 100
  * ``"Gem of Nulgath"``    -- cap 1000
"""
from core.command import Command
from bot.nation.core_nation import voucher_item_totem_of_nulgath

#: Change to one of the names above.
REWARD = "Totem of Nulgath"


async def main(cmd: Command):
    await voucher_item_totem_of_nulgath(cmd, REWARD)
