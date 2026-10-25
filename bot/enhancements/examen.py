"""Examen -- quest 8825, on top of Vim.

Port of ``Enhancement/UnlockForgeEnhancements.Examen``: ``Vim`` first, then
Healer ranked up and 250 Ethereal Essence.  It does **not** farm Blacksmithing
again -- only ``Vim`` does.
"""
from bot.enhancements.vim import (SELL_QUEST_CLASS, USE_GOLD,
                                  rank_class_and_farm_essence, vim)
from core.command import Command

EXAMEN_QUEST = 8825


async def examen(cmd: Command, use_gold: bool = USE_GOLD,
                 sell_quest_class: bool = SELL_QUEST_CLASS) -> None:
    """``UnlockForgeEnhancements.Examen``.

    Args:
        cmd (Command): Facade to act through.
        use_gold (bool): Forwarded to :func:`vim`.
        sell_quest_class (bool): The reference's ``SellQuestClass``.
    """
    if await cmd.is_completed_before(EXAMEN_QUEST):
        return

    await vim(cmd, use_gold, sell_quest_class)
    cmd.bot.log("Unlocking Enhancement: Examen")

    await cmd.ensure_accept_quest(EXAMEN_QUEST)
    await rank_class_and_farm_essence(cmd, 176, "Healer", 250)

    await cmd.ensure_turn_in_quest(EXAMEN_QUEST)
    if sell_quest_class:
        await cmd.sell_item("Healer")
    cmd.bot.log("Enhancement Unlocked: Examen")


async def main(cmd: Command):
    await examen(cmd)
