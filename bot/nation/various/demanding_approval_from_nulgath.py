"""Demanding Approval From Nulgath [Member] -- the Forge chain's receipt item.

Port of ``Nation/Various/DemandingApprovalFromNulgath[Member].cs``, which is one
line around ``CoreNation.GemStoneReceiptOfNulgath``.  The logic lives in
``bot.nation.core_nation.gem_stone_receipt_of_nulgath``.
"""
from core.command import Command
from bot.nation.core_nation import gem_stone_receipt_of_nulgath

#: Receipts to farm.
QUANT = 10


async def main(cmd: Command):
    await gem_stone_receipt_of_nulgath(cmd, QUANT)
