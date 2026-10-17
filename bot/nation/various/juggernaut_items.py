"""Juggernaut Items of Nulgath -- quest 837's twenty rewards, or one of them.

Port of ``Nation/Various/JuggernautItems.cs``.

Set ``REWARD`` to one of the twenty names below, or ``None`` to work through all
of them.  The reference's own option defaults to ``Oblivion of Nulgath``; the
default kept here is ``None``, i.e. every reward, which is what a run of this
script is for.

The reference guards on ``CheckInventory(..., toInv: false)`` -- its inventory
only; the bank-aware check is used here instead, as everywhere else in this port.
"""
from core.command import Command
from bot.nation.core_nation import (all_owned, farm_dark_crystal_shard,
                                    farm_diamond_of_nulgath,
                                    farm_gem_of_nulgath, farm_tainted_gem,
                                    farm_totem_of_nulgath, farm_uni13_quest,
                                    farm_voucher, first_missing)
from templates.hunt import hunt_item

#: Quest whose rewards this farms.
QUEST_ID = 837

#: ``None`` for all twenty, or one of:
#: ``"Oblivion of Nulgath"``, ``"Ungodly Reavers of Nulgath"``,
#: ``"Warlord of Nulgath"``, ``"Arcane of Nulgath"``,
#: ``"Dimensional Champion of Nulgath"``,
#: ``"Crystal Phoenix Blade of Nulgath"``, ``"Overfiend Blade of Nulgath"``,
#: ``"Battlefiend Blade of Nulgath"``, ``"Dark Makai of Nulgath"``,
#: ``"Nulgath Armor"``, ``"Polish Hussar"``, ``"Polish Hussar Helm"``,
#: ``"Polish Hussar Spear"``, ``"Polish Hussar Wings"``, ``"Void Cowboy"``,
#: ``"Void Cowboy Hat"``, ``"Void Cowboy Morph"``,
#: ``"Void Cowboy's Mask + Locks"``, ``"Void Cowboy's Pistol"``,
#: ``"Dual Void Cowboy Pistols"``.
REWARD = None

#: The rune one turn-in needs.
RUNE = "Undead Bruiser Rune"
MONSTER = "Undead Bruiser"
MAP = "underworld"


async def main(cmd: Command):
    await cmd.ensure_accept_quest(QUEST_ID)      # accepts, so rewards load
    entries = cmd.get_quest_reward_entries(QUEST_ID)
    if not entries:
        cmd.bot.log(f"[nation] quest {QUEST_ID} did not load; nothing farmed.")
        return
    cmd.add_drop([name for _, name, _ in entries])

    if REWARD is None:
        targets = [(name, 1) for _, name, _ in entries]
        reward_id = None
    else:
        match = next(((item_id, name) for item_id, name, _ in entries
                      if name == REWARD), None)
        if match is None:
            cmd.bot.log(f"[nation] {REWARD!r} is not one of quest {QUEST_ID}'s "
                  f"rewards.")
            return
        targets = [(match[1], 1)]
        reward_id = match[0]

    while cmd.is_still_connected() and not await all_owned(cmd, targets):
        await farm_uni13_quest(cmd, 1)
        await cmd.ensure_accept_quest(QUEST_ID)
        await farm_diamond_of_nulgath(cmd, 13)
        await farm_dark_crystal_shard(cmd, 50)
        await farm_totem_of_nulgath(cmd, 3)
        await farm_gem_of_nulgath(cmd, 20)
        await farm_voucher(cmd, False)
        await farm_tainted_gem(cmd, 50)
        await hunt_item(cmd, RUNE, 1, MAP, monster_name=MONSTER, is_temp=False)

        if reward_id is not None:
            await cmd.ensure_turn_in_quest(QUEST_ID, reward_id)
        else:
            chosen = await first_missing(cmd, [(i, n, 1) for i, n, _ in entries])
            await cmd.ensure_turn_in_quest(QUEST_ID,
                                           chosen[0] if chosen else -1)
