"""Farm Blood From the Void -- ``/tercesinvasion``.

Port of the reference bot's ``Nation/Materials/BloodFromtheVoid.cs``.  Needs the
``/tercesinvasion`` story (quest 10581) done first, and the farm itself lives
in ``bot.nation.core_nation``.
"""
from core.command import Command
from bot.nation.core_nation import blood_from_the_void


async def main(cmd: Command):
    await blood_from_the_void(cmd, 300)
