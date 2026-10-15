"""Farm quest 7551 (Swindle's Return Policy) rewards.

Port of ``Nation/SwindlesReturnPolicy.cs``.  That script picks the reward from
its options; here you set it below.  With ``ITEM = None`` the first reward that
is not maxed is taken, so the run is never a silent no-op.

Choose one:
  * ``None``                          -- the first reward that is not maxed
  * ``"Tainted Gem"``
  * ``"Dark Crystal Shard"``
  * ``"Diamond of Nulgath"``
  * ``"Gem of Nulgath"``
  * ``"Blood Gem of the Archfiend"``
"""
from core.command import Command
from bot.nation.core_nation import swindle_return

#: Change to one of the above.
ITEM = None
QUANT = 1000


async def main(cmd: Command):
    await swindle_return(cmd, ITEM, QUANT)
