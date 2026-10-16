"""Farm Blood Gems through Kiss the Void (quest 3743).

Port of ``Nation/KisstheVoid.cs``.  With no blade named it farms Blood Gem of
the Archfiend; name one to farm that blade instead.

Choose one:
  * ``None``                              -- Blood Gem of the Archfiend
  * ``"1st Betrayal Blade of Nulgath"``   (…sampai ``"8th …"``)
"""
from core.command import Command
from bot.nation.core_nation import BETRAYAL_BLADES, kissthe_void

#: ``None`` for Blood Gems, or one of ``BETRAYAL_BLADES``.
BLADE = None
QUANT = 100

assert BLADE is None or BLADE in BETRAYAL_BLADES, BLADE


async def main(cmd: Command):
    await kissthe_void(cmd, QUANT, BLADE)
