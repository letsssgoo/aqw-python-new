"""Smite -- quest 8740, on the back of the Shadowfall Rise story.

Port of ``Enhancement/UnlockForgeEnhancements.Smite``.  Its ``CoreSS.ShadowfallRise``
step is :func:`bot.story.sepulchure_saga.core_sepulchure.shadowfall_rise`, which is
where most of the work is; everything after it is one quest.

``UseGold`` is the reference's option for the reputation step; its default is
``False``.
"""
from bot.core_advanced import buy_item
from bot.core_bots import equip_class
from bot.core_farms import blacksmithing_rep, farm_experience
from bot.nation.core_nation import kill_escherion
from bot.story.sepulchure_saga.core_sepulchure import shadowfall_rise
from core.command import Command
from templates.hunt import hunt_item

USE_GOLD = False
SMITE_QUEST = 8740


async def smite(cmd: Command, use_gold: bool = USE_GOLD) -> None:
    """``UnlockForgeEnhancements.Smite``.

    Args:
        cmd (Command): Facade to act through.
        use_gold (bool): The reference's ``UseGold`` option, passed on to the
            reputation farm for both of its own flags.
    """
    if await cmd.is_completed_before(SMITE_QUEST):
        return

    cmd.bot.log("Unlocking Enhancement: Smite")

    await farm_experience(cmd, 60)
    await blacksmithing_rep(cmd, 6, use_gold, use_gold)
    await shadowfall_rise(cmd)

    await cmd.ensure_accept_quest(SMITE_QUEST)
    await equip_class(cmd, solo=True)

    await hunt_item(cmd, "Death's Power", 3, "shadowattack",
                    monster_name="Death", is_temp=False)
    await kill_escherion(cmd, "Chaotic Power", 7)
    await hunt_item(cmd, "Empowered Essence", 50, "shadowrealmpast",
                    monster_name="Pure Shadowscythe", is_temp=False)
    await hunt_item(cmd, "Gem Power", 25, "undergroundlabb",
                    monster_name="Ultra Battle Gem", is_temp=False)
    await buy_item(cmd, 2116, "Power Tonic", 10, map_name="alchemyacademy")

    await cmd.ensure_turn_in_quest(SMITE_QUEST)
    cmd.bot.log("Enhancement Unlocked: Smite")


async def main(cmd: Command):
    await smite(cmd)
