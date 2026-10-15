"""Forge Gem Stones for Nulgath -- quest 4918 in /battleundera.

Port of ``Nation/Various/ForgeGemStonesForNulgath[Member].cs``, which is one
line around ``CoreNation.GemStonesOfnulgath``.  The logic lives in
``bot.nation.core_nation``.

Membership and the Gemstone of Nulgath are both required; a run without either
stops with a report.
"""
from core.command import Command
from bot.nation.core_nation import gem_stones_of_nulgath

#: Reward quantities.  The reference defaults to these.
BLOODSTONE = 100
QUARTZ = 100
TANZANITE = 100
UNI_GEMSTONE = 1


async def main(cmd: Command):
    await gem_stones_of_nulgath(cmd, BLOODSTONE, QUARTZ, TANZANITE, UNI_GEMSTONE)
