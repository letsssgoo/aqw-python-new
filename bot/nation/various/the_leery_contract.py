"""The Leery Contract [Member] -- quest 554's three rewards, or one of them.

Port of ``Nation/Various/TheLeeryContract[Member].cs``.

Set ``REWARD`` to one of the three names below, or ``None`` to work through all
of them.  The reference's own option defaults to the axe, which is the default
kept here.

Quest 554 is the same one ``leery_exchange_gold`` turns Unidentified 13 into
gold with; this side of it takes an Undead Legend Rune instead.
"""
from core.command import Command
from bot.nation.core_nation import (all_owned, farm_uni13_quest, first_missing)
from templates.hunt import hunt_item

#: Quest whose rewards this farms.
QUEST_ID = 554

#: ``None`` for all three, or one of: ``"Ddog Sea Serpent Sword"``,
#: ``"Godly Golden Dragon Axe"``, ``"Corpse Maker of Nulgath"``.
REWARD = "Godly Golden Dragon Axe"

#: The rune one turn-in needs.
RUNE = "Undead Legend Rune"
MONSTER = "Undead Legend"
MAP = "EvilWarNul"


async def main(cmd: Command):
    if not cmd.get_player().is_member:
        print("[nation] The Leery Contract is members only; nothing farmed.")
        return

    await cmd.ensure_accept_quest(QUEST_ID)      # accepts, so rewards load
    entries = cmd.get_quest_reward_entries(QUEST_ID)
    if not entries:
        print(f"[nation] quest {QUEST_ID} did not load; nothing farmed.")
        return
    cmd.add_drop([name for _, name, _ in entries])

    if REWARD is None:
        targets = [(name, 1) for _, name, _ in entries]
        reward_id = None
    else:
        match = next(((item_id, name) for item_id, name, _ in entries
                      if name == REWARD), None)
        if match is None:
            names = ", ".join(name for _, name, _ in entries)
            print(f"[nation] {REWARD!r} is not one of quest {QUEST_ID}'s "
                  f"rewards ({names}).")
            return
        targets = [(match[1], 1)]
        reward_id = match[0]

    while cmd.is_still_connected() and not await all_owned(cmd, targets):
        await cmd.ensure_accept_quest(QUEST_ID)
        await farm_uni13_quest(cmd, 1)
        await hunt_item(cmd, RUNE, 1, MAP, monster_name=MONSTER, is_temp=False)
        if reward_id is not None:
            await cmd.ensure_turn_in_quest(QUEST_ID, reward_id)
        else:
            chosen = await first_missing(cmd, [(i, n, 1) for i, n, _ in entries])
            await cmd.ensure_turn_in_quest(QUEST_ID,
                                           chosen[0] if chosen else -1)
