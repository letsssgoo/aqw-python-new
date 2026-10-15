"""Farm quest 2857 (Supplies to Spin the Wheel of Chance) and its extras.

Port of ``Nation/SuppliesToSpinTheWheelofChance.cs``.  The C# script exposes its
options as checkboxes; they are the flags below.

``ITEM`` -- reward to farm, or ``None``/``"All"`` for all of them.
``RETURN_ITEM`` -- reward to ask the Swindle's Return step for, or ``None``.

Flags (all ``False`` = the plain route):
  * ``ULTRA_ALTEON``          -- Relic of Chaos from Ultra Chaos Alteon
  * ``HYDRA_CHALLENGE``       -- Relic of Chaos from a Hydra Head
  * ``KEEP_VOUCHER``          -- do not sell the member voucher
  * ``SELL_MEM_VOUCHER``      -- sell the member voucher you hold
  * ``ASSISTANT_DURING``      -- spend gold on War-Torn Memorabilia
  * ``RETURN_POLICY``         -- run the Swindle's Return step each pass
  * ``VOUCHER_ITEM_DURING``   -- trade the voucher for a totem/gem each pass
"""
from core.command import Command
from bot.nation.core_nation import supplies

#: Change per the list above.
ITEM = None
QUANT = 1
ULTRA_ALTEON = False
KEEP_VOUCHER = False
ASSISTANT_DURING = False
RETURN_ITEM = None
RETURN_POLICY = False
VOUCHER_ITEM_DURING = False
HYDRA_CHALLENGE = False
SELL_MEM_VOUCHER = False


async def main(cmd: Command):
    await supplies(cmd, ITEM, QUANT, ULTRA_ALTEON, KEEP_VOUCHER,
                   ASSISTANT_DURING, RETURN_ITEM, RETURN_POLICY,
                   VOUCHER_ITEM_DURING, HYDRA_CHALLENGE, SELL_MEM_VOUCHER)
