"""Dark War Legion Gold: gold from quests 8584 / 8585 in /darkwarlegion.

Port of ``Farm/DarkWarLegionGold.cs``.  The logic lives in ``bot.core_farms``.

The reference runs ``DarkWarLegionandNation.DarkWarLegion()`` first to unlock
those quests; that story is not ported, so this stops with a report if the quest
cannot be accepted -- rather than farming gold for a turn-in that never comes.
"""
from core.command import Command
from bot.core_bots import equip_class
from bot.core_farms import dark_war_legion

#: Gold to farm.
QUANT = 100_000_000


async def main(cmd: Command):
    await equip_class(cmd)
    await dark_war_legion(cmd, QUANT)
