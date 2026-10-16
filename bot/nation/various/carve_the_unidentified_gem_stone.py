"""Carve the Unidentified Gemstone -- quest 4923, for one reward or all.

Port of ``Nation/Various/CarveTheUnidentifiedGemStone[Member].cs``.  The logic
lives in ``bot.nation.core_nation``.

Set ``REWARD`` to one of the names below, or ``None`` to work on all of them
until each is at ``QUANT``.  The reference only offers four of the five in its
own menu (it leaves Tainted Gem out) and passes the enum member through with
underscores, which is not an item name -- both are slips; the real names work
here, and ``None`` stops when every reward is full instead of never.
"""
from core.command import Command
from bot.nation.core_nation import carve_uni_gem_stone

#: ``None`` for all of them, or one of:
#: ``"Tainted Gem"``, ``"Dark Crystal Shard"``, ``"Diamond of Nulgath"``,
#: ``"Gem of Nulgath"``, ``"Blood Gem of the Archfiend"``.
REWARD = None

#: Target quantity per reward.
QUANT = 1000


async def main(cmd: Command):
    await carve_uni_gem_stone(cmd, REWARD, QUANT)
