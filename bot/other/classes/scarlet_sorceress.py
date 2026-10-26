"""Scarlet Sorceress -- the Tower of Mirrors chain plus quest 6236.

Port of ``Other/Classes/ScarletSorceress.GetSSorc``: the Throne of Darkness
regions (``ShatterGlassMaze`` + ``TowerofMirrors``), the Blood Sorceress ranked
and enhanced, then experience 50 and one quest turn-in for the class itself.

``Core.Relogin`` is reproduced: the reference relogs when the class arrives
unenhanced so the game re-applies its enhancement type.
"""
from bot.core_advanced import enhance_item
from bot.core_advanced import rank_up_class as advance_class
from bot.core_bots import chain_complete, check_class_rank, wait_for_item
from bot.core_farms import farm_experience
from bot.other.classes.blood_sorceress import (BLOOD_SORCERESS_ITEM,
                                               get_bsorc)
from bot.story.throne_of_darkness.core_tod import tower_of_mirrors
from core.command import Command

SCARLET = "Scarlet Sorceress"
#: The class's own quest, after the story and the experience.
SCARLET_QUEST = 6236
#: ``Farm.Experience(50)``.
SCARLET_LEVEL = 50


async def get_ssorc(cmd: Command, rank_up_class: bool = True) -> None:
    """``ScarletSorceress.GetSSorc``.

    Args:
        cmd (Command): Facade to act through.
        rank_up_class (bool): Carry the class to rank 10 afterwards.
    """
    if await cmd.has_item(SCARLET):
        if rank_up_class:
            await advance_class(cmd, SCARLET)
        return

    cmd.add_drop(SCARLET)
    cmd.add_drop(BLOOD_SORCERESS_ITEM)

    await tower_of_mirrors(cmd)

    if not await cmd.has_item_id(BLOOD_SORCERESS_ITEM) \
            or check_class_rank(cmd, "Blood Sorceress") < 10:
        await get_bsorc(cmd)
        await wait_for_item(cmd, "Blood Sorceress")
        await enhance_item(cmd, "Blood Sorceress", "Lucky")

    if check_class_rank(cmd, "Blood Sorceress") < 10:
        cmd.bot.request_relogin("\"Blood Sorceress\" arrived unenhanced; "
                                "relogging so the game sets its enhancement type.")
        await advance_class(cmd, item_id=BLOOD_SORCERESS_ITEM)

    if not await cmd.has_item(SCARLET):
        await farm_experience(cmd, SCARLET_LEVEL)
        cmd.stop_aggro()

        await chain_complete(cmd, SCARLET_QUEST)
        await wait_for_item(cmd, SCARLET)
        await enhance_item(cmd, SCARLET, "Lucky")

        if rank_up_class:
            await advance_class(cmd, SCARLET)


async def main(cmd: Command):
    await get_ssorc(cmd)
