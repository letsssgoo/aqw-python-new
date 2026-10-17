"""Absolution -- quest 8743, capes and the Slimed Sigil.

Port of ``Enhancement/UnlockForgeEnhancements.Absolution``.  Two items the run may
already own shorten the sigil farm: the C# starts at 150 and takes 100 off for
``Ascended Paladin`` and 50 off for ``Ascended Paladin Sword``.

``UseGold`` is the reference's option for the reputation step; its default is
``False``.
"""
from bot.core_advanced import buy_item
from bot.core_bots import equip_class
from bot.core_farms import blacksmithing_rep, farm_experience, good_rep
from core.command import Command
from templates.hunt import hunt_item

USE_GOLD = False
ABSOLUTION_QUEST = 8743
SLIMED_SIGIL = "Slimed Sigil"
SIGIL_TARGET = 150
RIFT_MAP = "therift"
RIFT_SHOP = 1399

#: ``(item id, how much of the sigil farm it saves)``, as the C# subtracts them.
SIGIL_CREDITS = ((39091, 100),    # Ascended Paladin
                 (39094, 50))     # Ascended Paladin Sword


async def absolution(cmd: Command, use_gold: bool = USE_GOLD) -> None:
    """``UnlockForgeEnhancements.Absolution``.

    Args:
        cmd (Command): Facade to act through.
        use_gold (bool): The reference's ``UseGold`` option, passed on to the
            reputation farm for both of its own flags.
    """
    if await cmd.is_completed_before(ABSOLUTION_QUEST):
        return

    cmd.bot.log("Unlocking Enhancement: Absolution")

    await farm_experience(cmd, 90)
    await good_rep(cmd, 10)
    await blacksmithing_rep(cmd, 9, use_gold, use_gold)

    sigil = SIGIL_TARGET
    for item_id, credit in SIGIL_CREDITS:
        if await cmd.has_item_id(item_id):
            sigil -= credit

    await equip_class(cmd)
    await hunt_item(cmd, SLIMED_SIGIL, sigil, "charredpath", cell="r5",
                    pad="Left", monster_name="Plague Spreader", is_temp=False)

    await buy_item(cmd, RIFT_SHOP, "Ascended Paladin", map_name=RIFT_MAP)
    await buy_item(cmd, RIFT_SHOP, "Ascended Paladin Sword", map_name=RIFT_MAP)

    # Core.ChainComplete: accept, then turn in -- this engine's turn-in is a
    # no-op for a quest that is not in progress.
    await cmd.ensure_accept_quest(ABSOLUTION_QUEST)
    await cmd.ensure_turn_in_quest(ABSOLUTION_QUEST)
    cmd.bot.log("Enhancement Unlocked: Absolution")


async def main(cmd: Command):
    await absolution(cmd)
