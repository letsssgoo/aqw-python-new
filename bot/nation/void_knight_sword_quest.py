"""Farm the Void Knight Sword quest rewards (5662 / 5659).

Port of ``Nation/VoidKnightSwordQuest.cs``.  Which quest applies depends on
owning item 38275; without either sword there is nothing to do.
"""
from core.command import Command
from bot.nation.core_nation import void_knight_sword_quest


async def main(cmd: Command):
    await void_knight_sword_quest(cmd)
