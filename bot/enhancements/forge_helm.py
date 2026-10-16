"""Forge (Helm) -- quest 8828, the same four kills as Forge (Weapon) with
different items.

Port of ``Enhancement/UnlockForgeEnhancements.ForgeHelmEnhancement``.  Unlike
Forge (Weapon) it needs no story lead-in: ``KillEscherion``/``KillVath``/
``KillKitsune`` are the item helpers, not the story cores.

``UseGold`` is the reference's option for the reputation step; its default is
``False``.
"""
from bot.core_bots import equip_class, kill_kitsune
from bot.core_farms import blacksmithing_rep, farm_experience
from bot.nation.core_nation import kill_escherion, kill_vath
from core.command import Command
from templates.hunt import hunt_item

USE_GOLD = False
FORGE_HELM_QUEST = 8828


async def forge_helm_enhancement(cmd: Command,
                                 use_gold: bool = USE_GOLD) -> None:
    """``UnlockForgeEnhancements.ForgeHelmEnhancement``.

    Args:
        cmd (Command): Facade to act through.
        use_gold (bool): The reference's ``UseGold`` option, passed on to the
            reputation farm for both of its own flags, as the source does.
    """
    if await cmd.is_completed_before(FORGE_HELM_QUEST):
        return

    cmd.bot.log("Unlocking Enhancement: Forge (Helm)")

    await farm_experience(cmd, 30)
    await blacksmithing_rep(cmd, 4, use_gold, use_gold)

    await equip_class(cmd, solo=True)
    await cmd.ensure_accept_quest(FORGE_HELM_QUEST)

    await kill_escherion(cmd, "1st Lord Of Chaos Staff")
    await kill_vath(cmd, "Chaos Dragonlord Axe")
    await kill_kitsune(cmd, "Hanzamune Dragon Koi Blade")
    await hunt_item(cmd, "Wrath of the Werepyre", 1, "wolfwing",
                    monster_name="Wolfwing", is_temp=False)

    await cmd.ensure_turn_in_quest(FORGE_HELM_QUEST)
    cmd.bot.log("Enhancement Unlocked: Forge (Helm)")


async def main(cmd: Command):
    await forge_helm_enhancement(cmd)
