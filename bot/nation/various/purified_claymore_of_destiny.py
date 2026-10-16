"""Purified Claymore of Destiny -- quest 548, after the Good reputation farm.

Port of ``Nation/Various/PurifiedClaymoreOfDestiny.cs``.  The logic lives in
``bot.nation.core_nation.get_pcod``, which also runs the ``Farm.Experience(15)``
and ``Farm.GoodREP(8)`` the reference does first.

This file is also what several other Nation scripts include for its
``GetPCoD``; that is the same function.
"""
from core.command import Command
from bot.nation.core_nation import get_pcod


async def main(cmd: Command):
    await get_pcod(cmd)
