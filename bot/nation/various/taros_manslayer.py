"""Taro's Manslayer -- one drop for non-members, both rewards for members.

Port of ``Nation/Various/TarosManslayer.cs``.

The reference picks its own mode from membership: a non-member gets the plain
drop off the Taro Blademaster, a member runs quest 1111 for the manslayer and the
guardian both.  That is reproduced rather than exposed as a constant, because the
reference computes it the same way.

Note:
    Quest 1111's turn-in is a *choice* between its two rewards; the reference
    passes both and lets its client pick.  Here the first one not yet held is
    chosen, so the pair actually fills up.
"""
from core.command import Command
from bot.nation.core_nation import (all_owned, dark_makai_item,
                                    farm_faction, farm_gem_of_nulgath,
                                    first_missing, get_pcod)
from templates.hunt import hunt_item

#: Both rewards, and the single one the drop-only mode wants.
MAN_SLAYER = "Taro's Manslayer"
REWARDS = (MAN_SLAYER, "Taro Blademaster Guardian")

#: Quest the member route turns in, and the rune it needs.
QUEST_ID = 1111
RUNE = "Dark Makai Rune"


async def main(cmd: Command):
    manslayer_only = not cmd.get_player().is_member
    wanted = (MAN_SLAYER,) if manslayer_only else REWARDS
    if await all_owned(cmd, [(name, 1) for name in wanted]):
        return

    if manslayer_only:
        cmd.add_drop(list(wanted))
        await hunt_item(cmd, MAN_SLAYER, 1, "tercessuinotlim",
                        monster_name="Taro Blademaster", is_temp=False)
        return

    # the member route, in the reference's own order
    await farm_faction(cmd, "Good")
    if not await get_pcod(cmd):
        return

    await cmd.ensure_accept_quest(QUEST_ID)      # accepts, so rewards load
    entries = cmd.get_quest_reward_entries(QUEST_ID)
    if not entries:
        cmd.bot.log(f"[nation] quest {QUEST_ID} did not load; nothing farmed.")
        return
    cmd.add_drop([name for _, name, _ in entries])

    while (cmd.is_still_connected()
           and not await all_owned(cmd, [(name, 1) for name in wanted])):
        await cmd.ensure_accept_quest(QUEST_ID)
        await farm_gem_of_nulgath(cmd, 10)
        # the reference calls ResetQuest(7551) here, which sends no packet of
        # its own; accepting the quest is the whole of it
        await cmd.ensure_accept_quest(7551)
        await dark_makai_item(cmd, RUNE)
        chosen = await first_missing(cmd, [(item_id, name, 1)
                                           for item_id, name, _ in entries
                                           if name in wanted])
        await cmd.ensure_turn_in_quest(QUEST_ID,
                                       chosen[0] if chosen else -1)
