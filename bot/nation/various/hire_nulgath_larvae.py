"""Hire Nulgath Larvae -- quest 867, members only.

Port of ``Nation/Various/HireNulgathLarvae.cs``.  The logic lives in
``bot.nation.core_nation.hire_nulgath_larvae``.
"""
from core.command import Command
from bot.nation.core_nation import hire_nulgath_larvae


async def main(cmd: Command):
    await hire_nulgath_larvae(cmd)
