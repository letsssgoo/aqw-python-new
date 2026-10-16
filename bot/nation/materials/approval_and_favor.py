"""Farm Nulgath's Approval and Archfiend's Favor -- ``/evilwarnul``.

Port of the reference bot's ``Nation/Materials/ApprovalAndFavor.cs``.  The script itself is
a one-liner around ``CoreNation.ApprovalAndFavor``; the logic lives in
``bot.nation.core_nation``.
"""
from core.command import Command
from bot.nation.core_nation import approval_and_favor


async def main(cmd: Command):
    await approval_and_favor(cmd)
