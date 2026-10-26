"""Pneuma -- quest 8827, on top of Anima.

Port of ``Enhancement/UnlockForgeEnhancements.Pneuma``: ``Anima`` first, then
Mage ranked up and 650 Ethereal Essence.
"""
from bot.enhancements.anima import anima
from bot.enhancements.vim import (SELL_QUEST_CLASS, USE_GOLD,
                                  rank_class_and_farm_essence)
from core.command import Command

PNEUMA_QUEST = 8827


async def pneuma(cmd: Command, use_gold: bool = USE_GOLD,
                 sell_quest_class: bool = SELL_QUEST_CLASS) -> None:
    """``UnlockForgeEnhancements.Pneuma``.

    Args:
        cmd (Command): Facade to act through.
        use_gold (bool): Forwarded to :func:`anima`.
        sell_quest_class (bool): The reference's ``SellQuestClass``.
    """
    if await cmd.is_completed_before(PNEUMA_QUEST):
        return

    await anima(cmd, use_gold, sell_quest_class)
    cmd.bot.log("Unlocking Enhancement: Pneuma")

    await cmd.ensure_accept_quest(PNEUMA_QUEST)
    await rank_class_and_farm_essence(cmd, 174, "Mage", 650)

    await cmd.ensure_turn_in_quest(PNEUMA_QUEST)
    if sell_quest_class:
        await cmd.sell_item("Mage")
    cmd.bot.log("Enhancement Unlocked: Pneuma")


async def main(cmd: Command):
    await pneuma(cmd)
