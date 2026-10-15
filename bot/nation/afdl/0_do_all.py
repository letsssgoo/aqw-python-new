"""0 Do All -- the whole AFDL set in one run.

Port of ``AFDL/0DoAll.cs``, which is one line around the AFDL routine in
``EnoughDOOMforanArchfiend``.  The logic lives in
``bot.nation.afdl.enough_doom_for_an_archfiend``.
"""
from core.command import Command
from bot.nation.afdl.enough_doom_for_an_archfiend import afdl


async def main(cmd: Command):
    await afdl(cmd)
