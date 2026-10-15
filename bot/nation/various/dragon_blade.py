"""DragonBlade of Nulgath -- quest 766, members only.

Port of ``Nation/Various/DragonBlade[mem].cs``.

Runs both Behemoth Blades first (the same routine the standalone wrapper uses),
then quest 765 for the three twisted items and 766 for the blade itself.

Note:
    Quest 765's turn-in is a choice between its three rewards; the reference lets
    its client pick, and here the first one not yet held is chosen so the three
    fill up.
"""
from core.command import Command
from bot.nation.core_nation import (all_owned, farm_totem_of_nulgath,
                                    first_missing)
from bot.nation.various.behemoth_blades import behemoth_blade_of
from templates.hunt import hunt_item

#: Quest 765's three rewards.
TWISTED_ITEMS = ("DragonFire of Nulgath", "Crimson Plate of Nulgath",
                 "Crimson Face Plate of Nulgath")

#: The blade's own quest, its rune, and the reward id the reference completes it with.
ITEM = "DragonBlade of Nulgath"
BLADE_QUEST = 766
BLADE_RUNE = "Legion Fenrir Rune"
BLADE_FENRIR = "Legion Fenrir"
BLADE_REWARD_ID = 5483

#: The twisted-items quest and its rune.
TWISTED_QUEST = 765
TWISTED_RUNE = "Skull Warrior Rune"
SKULL_WARRIOR = "Skull Warrior"

#: Totems every step of the chain needs.
TOTEMS = 3

#: Map both hunts happen in.
HUNT_MAP = "underworld"


async def main(cmd: Command):
    if await cmd.has_item(ITEM):
        return
    if not cmd.get_player().is_member:
        print("[nation] the DragonBlade of Nulgath is members only; nothing "
              "farmed.")
        return

    cmd.add_drop(list(TWISTED_ITEMS) + [ITEM])

    await behemoth_blade_of(cmd, "Shadow")
    await behemoth_blade_of(cmd, "Light")

    await cmd.ensure_accept_quest(TWISTED_QUEST)
    entries = cmd.get_quest_reward_entries(TWISTED_QUEST)
    while (cmd.is_still_connected()
           and not await all_owned(cmd, [(name, 1) for name in TWISTED_ITEMS])):
        await cmd.ensure_accept_quest(TWISTED_QUEST)
        await farm_totem_of_nulgath(cmd, TOTEMS)
        await hunt_item(cmd, TWISTED_RUNE, 1, HUNT_MAP,
                        monster_name=SKULL_WARRIOR, is_temp=False)
        chosen = await first_missing(cmd, [(item_id, name, 1)
                                           for item_id, name, _ in entries])
        await cmd.ensure_turn_in_quest(TWISTED_QUEST,
                                       chosen[0] if chosen else -1)

    await farm_totem_of_nulgath(cmd, TOTEMS)
    await cmd.ensure_accept_quest(BLADE_QUEST)
    await hunt_item(cmd, BLADE_RUNE, 1, HUNT_MAP, monster_name=BLADE_FENRIR,
                    is_temp=False)
    await cmd.ensure_turn_in_quest(BLADE_QUEST, BLADE_REWARD_ID)
