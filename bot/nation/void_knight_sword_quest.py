"""Farm the Void Knight Sword quest rewards (5662 / 5659).

Port of ``Nation/VoidKnightSwordQuest.cs``.  Which quest applies depends on
owning item 38275; without either sword there is nothing to do.

``ITEM`` must be one of quest 5662's or 5659's rewards.  The list only exists
once the quest is accepted, so leave ``None`` when unsure -- that farms them
all anyway.
"""
from core.command import Command
from bot.nation.core_nation import void_knight_sword_quest

#: ``None`` for all of them, or one reward name.
ITEM = None
QUANT = 1


async def main(cmd: Command):
    await void_knight_sword_quest(cmd, ITEM, QUANT)
