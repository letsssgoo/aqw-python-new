"""Lacerate -- quest 8739, with the 90 -> 91 -> 92 prerequisite chain.

Port of ``Enhancement/UnlockForgeEnhancements.Lacerate``.

The reference gates its prerequisite chain on ``Bot.Quests.IsUnlocked``: a client
check of the live quest-slot value.  This engine has no client to ask, and all of
these are one-time quests (``bOnce``), so "is it unlocked" is answered by "is it
already done" instead -- ``is_completed_before`` -- and the chain is walked in
order, which is what makes the next quest unlockable.  A quest the server still
refuses is reported by ``ensure_accept_quest``.

``QuestProgression``'s recovery loop (re-completing the previous quest, relogging
after five tries) has no counterpart here; it is in the deviation register.

``UseGold`` is the reference's option for the reputation step; its default is
``False``.
"""
from bot.core_bots import equip_class
from bot.core_farms import black_knight_orb, blacksmithing_rep, farm_experience
from bot.core_story import kill_quest
from core.command import Command
from templates.hunt import hunt_item

USE_GOLD = False
LACERATE_QUEST = 8739
PIRATE_QUEST = 90
WALLET_QUEST = 91
GREEN_GUARD_QUEST = 92

#: Quest 91's wallets: ``(cell, pad, monster, item, qty)``, in the source's order.
WALLETS = (
    ("West1", "Left", "Kittarian", "Kittarian's Wallet", 2),
    ("West9", "Left", "River Fishman", "River Fishman's Wallet", 2),
    ("West10", "Left", "Slime", "Slime-Soaked Wallet", 2),
    ("West3", "Left", "Frogzard", "Frogzard's Lint Hoard", 2),
    ("West12", "Up", "Big Bad Boar", "Big Bad Boar's Wallet", 1),
)


async def lacerate(cmd: Command, use_gold: bool = USE_GOLD) -> None:
    """``UnlockForgeEnhancements.Lacerate``.

    Args:
        cmd (Command): Facade to act through.
        use_gold (bool): The reference's ``UseGold`` option, passed on to the
            reputation farm for both of its own flags.
    """
    if await cmd.is_completed_before(LACERATE_QUEST):
        return

    cmd.bot.log("Unlocking Enhancement: Lacerate")

    await _prerequisite_chain(cmd)

    await farm_experience(cmd, 40)
    await blacksmithing_rep(cmd, 5, use_gold, use_gold)

    await cmd.ensure_accept_quest(LACERATE_QUEST)

    await equip_class(cmd, solo=True)
    await hunt_item(cmd, "Undead Plague Spear", 1, "graveyard",
                    monster_name="Big Jack Sprat", is_temp=False)
    await hunt_item(cmd, "Kuro's Wrath", 1, "river", monster_name="Kuro",
                    is_temp=False)

    if not await cmd.has_item("Massive Horc Cleaver"):
        cmd.add_drop("Massive Horc Cleaver")
        await cmd.ensure_accept_quest(279)
        await hunt_item(cmd, "Boss Prize", 1, "warhorc",
                        monster_name="Horc Master")
        await cmd.ensure_turn_in_quest(279)

    if not await cmd.has_item("Sword in the Stone"):
        cmd.add_drop("Sword in the Stone")
        await cmd.ensure_accept_quest(316)
        await cmd.join_map("greenguardeast")
        await cmd.get_map_item(54, 7)
        await hunt_item(cmd, "Tiny Sword", 1, "greenguardeast",
                        monster_name="Spider")
        await cmd.ensure_turn_in_quest(316)

    if not await cmd.has_item("Forest Axe"):
        cmd.add_drop("Forest Axe")
        await cmd.ensure_accept_quest(301)
        await cmd.join_map("farm")
        await cmd.get_map_item(55, 4)
        await hunt_item(cmd, "Mosquito Juice", 1, "farm",
                        monster_name="Mosquito")
        await cmd.ensure_turn_in_quest(301)

    await black_knight_orb(cmd)

    await cmd.ensure_turn_in_quest(LACERATE_QUEST)
    cmd.bot.log("Enhancement Unlocked: Lacerate")


async def _prerequisite_chain(cmd: Command) -> None:
    """Quests 90 -> 91 -> 92, the chain the reference runs while 8739 is locked."""
    if not await cmd.is_completed_before(PIRATE_QUEST):
        await cmd.ensure_accept_quest(PIRATE_QUEST)
        await hunt_item(cmd, "Pirate Medallion", 12, "pirates",
                        monster_name="Shark Bait")
        await cmd.ensure_turn_in_quest(PIRATE_QUEST)

    if not await cmd.is_completed_before(WALLET_QUEST):
        await cmd.ensure_accept_quest(WALLET_QUEST)
        for cell, pad, monster, item, qty in WALLETS:
            await hunt_item(cmd, item, qty, "greenguardwest", cell=cell, pad=pad,
                            monster_name=monster)
        await cmd.ensure_turn_in_quest(WALLET_QUEST)

    await kill_quest(cmd, GREEN_GUARD_QUEST, "greenguardwest",
                     ["Breken the Vile", "Ogug Stoneaxe"])


async def main(cmd: Command):
    await lacerate(cmd)
