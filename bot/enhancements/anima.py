"""Anima -- quest 8826, on top of Examen.

Port of ``Enhancement/UnlockForgeEnhancements.Anima``: ``Examen`` first, then
Warrior ranked up and 650 Ethereal Essence.
"""
from bot.enhancements.examen import examen
from bot.enhancements.vim import (SELL_QUEST_CLASS, USE_GOLD,
                                  rank_class_and_farm_essence)
from core.command import Command

ANIMA_QUEST = 8826


async def anima(cmd: Command, use_gold: bool = USE_GOLD,
                sell_quest_class: bool = SELL_QUEST_CLASS) -> None:
    """``UnlockForgeEnhancements.Anima``.

    Args:
        cmd (Command): Facade to act through.
        use_gold (bool): Forwarded to :func:`examen`.
        sell_quest_class (bool): The reference's ``SellQuestClass``.
    """
    if await cmd.is_completed_before(ANIMA_QUEST):
        return

    await examen(cmd, use_gold, sell_quest_class)
    cmd.bot.log("Unlocking Enhancement: Anima")

    await cmd.ensure_accept_quest(ANIMA_QUEST)
    await rank_class_and_farm_essence(cmd, 170, "Warrior", 650)

    await cmd.ensure_turn_in_quest(ANIMA_QUEST)
    if sell_quest_class:
        await cmd.sell_item("Warrior")
    cmd.bot.log("Enhancement Unlocked: Anima")


async def main(cmd: Command):
    await anima(cmd)
