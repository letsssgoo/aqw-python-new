"""Void Destroyer -- every reward of quest 5661, banked afterwards.

Port of ``Nation/Various/VoidDestroyer.cs``.

Note:
    The reference guards on ``CheckInventory(Rewards, toInv: false)`` -- its
    inventory only, ignoring the bank -- and then banks the rewards when it
    finishes, so the next run farms all nine again.  The bank-aware check is used
    here instead, as everywhere else in this port.
"""
from core.command import Command
from bot.nation.core_nation import (all_owned, essence_of_nulgath,
                                    farm_dark_crystal_shard,
                                    farm_gem_of_nulgath, farm_tainted_gem,
                                    supplies)

#: Quest whose rewards this farms.
QUEST_ID = 5661

#: The nine rewards the reference tracks.
REWARDS = (
    "Void Destroyer",
    "Void Destruction Blade",
    "Void Spear of War",
    "Horned Void War Helm",
    "Crested Void War Helm",
    "Wrap of the Void",
    "Tainted Destruction Blade",
    "Toxic Void Katana",
    "Dual Toxic Void Katanas",
)


async def main(cmd: Command):
    if await all_owned(cmd, [(name, 1) for name in REWARDS]):
        cmd.bot.log("[nation] every Void Destroyer reward is already held.")
        return

    cmd.add_drop(list(REWARDS))
    while (cmd.is_still_connected()
           and not await all_owned(cmd, [(name, 1) for name in REWARDS])):
        await cmd.ensure_accept_quest(QUEST_ID)
        await supplies(cmd, "Unidentified 4")
        await farm_tainted_gem(cmd, 1)
        await farm_dark_crystal_shard(cmd, 1)
        await essence_of_nulgath(cmd, 1)
        await farm_gem_of_nulgath(cmd, 1)
        await cmd.ensure_turn_in_quest(QUEST_ID)

    # the reference banks them when it is done
    await cmd.inv_to_bank(list(REWARDS))
