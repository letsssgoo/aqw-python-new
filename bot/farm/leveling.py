"""Leveling [1-100]: farm experience to the level in ``LEVEL``.

Port of ``Farm/Leveling.cs``, which is a one-liner around
``CoreFarms.Experience``.  The logic lives in ``bot.core_farms``.

``RANK_UP_CLASS`` mirrors the reference's ``rankUpClass`` parameter, kept off:
this engine cannot read the equipped class's rank yet, so a rank-up run would
not know when to stop.  Turning it on says so in the log and farms the level
instead.
"""
from core.command import Command
from bot.core_farms import farm_experience

#: Level to stop at.
LEVEL = 100

#: ``True`` to rank the class up instead -- reported as unsupported for now.
RANK_UP_CLASS = False


async def main(cmd: Command):
    await farm_experience(cmd, LEVEL, RANK_UP_CLASS)
