"""Tendurrr The Assistant quests -- quest 5814's four rewards, or one of them.

Port of ``Nation/Various/TendurrrTheAssistantQuests.cs``.

Set ``REWARD`` to one of the four names below, or ``None`` to work through all of
them.  The reference's option defaults to the first one, which is the default
kept here.

Note:
    Three slips in the reference make it farm nothing at all, and they are not
    reproduced:

    * its reward option holds *indices* (0-3) while it looks them up as item
      ids, so the lookup misses and the loop never starts;
    * the "All" branch tests ``CheckInventory(rewards)`` without the ``!``, so it
      would farm only while every reward is already held;
    * it reads the reward list of quest 837, which is a different quest.

    The rewards come from quest 5814's own live payload here, and the named
    reward is the one turned in for.
"""
from core.command import Command
from bot.nation.core_nation import (all_owned, approval_and_favor,
                                    essence_of_nulgath, farm_blood_gem,
                                    farm_dark_crystal_shard,
                                    farm_diamond_of_nulgath,
                                    farm_gem_of_nulgath, farm_tainted_gem,
                                    farm_totem_of_nulgath, farm_uni13_quest,
                                    farm_voucher, first_missing)
from templates.hunt import hunt_item

#: Quest whose rewards this farms.
QUEST_ID = 5814

#: ``None`` for all four, or one of: ``"Tendurrr on your Back"``,
#: ``"Asuka's Flaming Stick"``, ``"Tendurrr's Flaming Stick"``,
#: ``"Tendurrr Morph"``.
REWARD = "Tendurrr on your Back"

#: The pet every pass needs, off the Dark Makai in /tercessuinotlim.
PET = "Tendurrr The Assistant"
PET_MAP = "tercessuinotlim"
PET_CELL = "m2"
PET_PAD = "Left"


async def main(cmd: Command):
    if not await cmd.has_item(PET):
        await hunt_item(cmd, PET, 1, PET_MAP, cell=PET_CELL, pad=PET_PAD,
                        monster_name="*", is_temp=False)
    await farm_uni13_quest(cmd, 1)

    await cmd.ensure_accept_quest(QUEST_ID)      # accepts, so rewards load
    entries = cmd.get_quest_reward_entries(QUEST_ID)
    if not entries:
        cmd.bot.log(f"[nation] quest {QUEST_ID} did not load; nothing farmed.")
        return
    cmd.add_drop([name for _, name, _ in entries])

    if REWARD is None:
        targets = [(item_id, name, 1) for item_id, name, _ in entries]
        reward_id = None
    else:
        match = next(((item_id, name, 1) for item_id, name, _ in entries
                      if name == REWARD), None)
        if match is None:
            names = ", ".join(name for _, name, _ in entries)
            cmd.bot.log(f"[nation] {REWARD!r} is not one of quest {QUEST_ID}'s "
                  f"rewards ({names}).")
            return
        targets = [match]
        reward_id = match[0]

    while (cmd.is_still_connected()
           and not await all_owned(cmd, [(name, qty) for _, name, qty
                                         in targets])):
        await cmd.ensure_accept_quest(QUEST_ID)
        await approval_and_favor(cmd, 500, 500)
        await essence_of_nulgath(cmd, 20)
        await farm_gem_of_nulgath(cmd, 30)
        await farm_dark_crystal_shard(cmd, 30)
        await farm_tainted_gem(cmd, 30)
        await farm_diamond_of_nulgath(cmd, 30)
        await farm_voucher(cmd, True)
        await farm_blood_gem(cmd, 10)
        await farm_totem_of_nulgath(cmd, 3)

        if reward_id is not None:
            await cmd.ensure_turn_in_quest(QUEST_ID, reward_id)
        else:
            chosen = await first_missing(cmd, targets)
            await cmd.ensure_turn_in_quest(QUEST_ID,
                                           chosen[0] if chosen else -1)
