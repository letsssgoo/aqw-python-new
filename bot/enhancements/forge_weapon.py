"""Forge (Weapon) -- quest 8738, the first forge enhancement.

Port of ``Enhancement/UnlockForgeEnhancements.ForgeWeaponEnhancement``.  Every
enhancement in that file has the same shape: skip when its quest is already done,
say so, level up, farm Blacksmithing reputation, then kill for the quest's items.

``UseGold`` is the reference's option for the reputation step; its default is
``False``, which is the value kept here.
"""
from bot.core_bots import equip_class, kill_kitsune
from bot.core_farms import blacksmithing_rep, farm_experience
from bot.nation.core_nation import kill_escherion, kill_vath
from bot.story.lordsofchaos.core13loc import escherion
from core.command import Command
from templates.hunt import hunt_item

USE_GOLD = False
FORGE_WEAPON_QUEST = 8738


async def forge_weapon_enhancement(cmd: Command,
                                   use_gold: bool = USE_GOLD) -> None:
    """``UnlockForgeEnhancements.ForgeWeaponEnhancement``.

    Args:
        cmd (Command): Facade to act through.
        use_gold (bool): The reference's ``UseGold`` option, passed on to the
            reputation farm for both of its own flags, as the source does.
    """
    if await cmd.is_completed_before(FORGE_WEAPON_QUEST):
        return

    cmd.bot.log("Unlocking Enhancement: Forge (Weapon)")

    await farm_experience(cmd, 30)
    await escherion(cmd)
    await blacksmithing_rep(cmd, 4, use_gold, use_gold)

    await equip_class(cmd, solo=True)
    await cmd.ensure_accept_quest(FORGE_WEAPON_QUEST)

    await kill_escherion(cmd, "1st Lord Of Chaos Helm")
    await kill_vath(cmd, "Chaos Dragonlord Helm")
    await kill_kitsune(cmd, "Chaos Shogun Helmet")
    await hunt_item(cmd, "Wolfwing Mask", 1, "wolfwing",
                    monster_name="Wolfwing", is_temp=False)

    await cmd.ensure_turn_in_quest(FORGE_WEAPON_QUEST)
    cmd.bot.log("Enhancement Unlocked: Forge (Weapon)")


async def main(cmd: Command):
    await forge_weapon_enhancement(cmd)
