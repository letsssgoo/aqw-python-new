"""Farm Blood Gems through Kiss the Void (quest 3743).

Port of ``Nation/KisstheVoid.cs``.
"""
from core.command import Command
from bot.nation.core_nation import kissthe_void


async def main(cmd: Command):
    await kissthe_void(cmd, 100)
