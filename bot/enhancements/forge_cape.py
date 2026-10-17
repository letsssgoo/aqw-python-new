"""Forge (Cape) -- quest 8758, on the back of the Kitsune story.

Port of ``Enhancement/UnlockForgeEnhancements.ForgeCapeEnhancement``.  Its
``LOC.Kitsune()`` step is
:func:`bot.story.lordsofchaos.core13loc.kitsune`, which is where most of the work
is; the cape's own four kills are one per map.

``UseGold`` is the reference's option for the reputation step; its default is
``False``.
"""
from bot.core_bots import equip_class
from bot.core_farms import blacksmithing_rep, farm_experience
from bot.story.lordsofchaos.core13loc import kitsune
from core.command import Command
from templates.hunt import hunt_item

USE_GOLD = False
FORGE_CAPE_QUEST = 8758

#: ``(map, monster, item)`` -- the source's four ``HuntMonster`` calls, in order.
WINGS = (("lostruinswar", "Diabolical Warlord", "Prismatic Celestial Wings"),
         ("lostruins", "Infernal Warlord", "Broken Wings"),
         ("infernalspire", "Azkorath", "Shadow's Wings"),
         ("infernalspire", "Malxas", "Wings Of Destruction"))


async def forge_cape_enhancement(cmd: Command,
                                 use_gold: bool = USE_GOLD) -> None:
    """``UnlockForgeEnhancements.ForgeCapeEnhancement``.

    Args:
        cmd (Command): Facade to act through.
        use_gold (bool): The reference's ``UseGold`` option, passed on to the
            reputation farm for both of its own flags.
    """
    if await cmd.is_completed_before(FORGE_CAPE_QUEST):
        return

    cmd.bot.log("Unlocking Enhancement: Forge (Cape)")

    await farm_experience(cmd, 30)
    await kitsune(cmd)
    await blacksmithing_rep(cmd, 4, use_gold, use_gold)

    await equip_class(cmd, solo=True)
    await cmd.ensure_accept_quest(FORGE_CAPE_QUEST)

    for map_name, monster, item in WINGS:
        await hunt_item(cmd, item, 1, map_name, monster_name=monster,
                        is_temp=False)

    await cmd.ensure_turn_in_quest(FORGE_CAPE_QUEST)
    cmd.bot.log("Enhancement Unlocked: Forge (Cape)")


async def main(cmd: Command):
    await forge_cape_enhancement(cmd)
