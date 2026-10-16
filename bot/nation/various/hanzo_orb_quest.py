"""Hanzo Orb Quest -- whichever of the two orb pets you own runs its quest.

Port of ``Nation/Various/HanzoOrbQuest.cs``.

``Astral Orb Pet`` selects quest 4020 and ``Crimson Orb Pet`` 4019; owning
neither stops the run.  ``REWARD`` names the reward to farm -- the reference's
default, ``"Any"``, is not a reward name and would loop forever, so an unknown
name is reported instead.  Set ``ANY_REWARD`` to work through every reward the
quest offers, each to its own max stack.
"""
from typing import Optional, Tuple

from core.command import Command
from templates.hunt import hunt_item

#: Quest per pet, exactly as the reference chooses between them.
QUESTS = {"Astral Orb Pet": 4020, "Crimson Orb Pet": 4019}

#: Reward to farm by name -- the quest's own rewards are listed in the log when
#: the name is wrong.
REWARD = "Any"

#: ``True`` to farm every reward the quest offers instead of one name.
ANY_REWARD = False

#: Target for the named reward.
QUANT = 1


async def _turn_in_materials(cmd: Command) -> None:
    """The four drops one turn-in needs, in the reference's order."""
    await hunt_item(cmd, "Jacked Eye", 5, "graveyard",
                    monster_name="Big Jack Sprat", is_temp=False)
    await hunt_item(cmd, "Dreadspider Silk", 1, "marsh",
                    monster_name="Dreadspider", is_temp=False)
    await hunt_item(cmd, "Makai Fang", 5, "tercessuinotlim", cell="m2",
                    pad="Left", monster_name="*", is_temp=False)
    await hunt_item(cmd, "Rattle Bones", 3, "bludrut",
                    monster_name="Rattlebones", is_temp=False)


async def main(cmd: Command):
    quest_id = 0
    for pet, pet_quest in QUESTS.items():
        if await cmd.has_item(pet):
            cmd.bot.log(f"[nation] using the {pet} quest ({pet_quest})")
            quest_id = pet_quest
            break
    if not quest_id:
        cmd.bot.log("[nation] neither the Astral nor the Crimson Orb Pet is owned; "
              "nothing farmed.")
        return

    await cmd.register_quest(quest_id)          # accepts, so rewards load
    entries = cmd.get_quest_reward_entries(quest_id)
    if not entries:
        cmd.bot.log(f"[nation] quest {quest_id} reported no rewards; nothing farmed.")
        cmd.cancel_registered_quests()
        return
    cmd.add_drop([name for _, name, _ in entries])

    targets: list[Tuple[str, int]] = []
    if ANY_REWARD:
        targets = [(name, stack) for _, name, stack in entries]
    else:
        match = next(((name, stack) for _, name, stack in entries
                      if name == REWARD), None)
        if match is None:
            names = ", ".join(name for _, name, _ in entries)
            cmd.bot.log(f"[nation] {REWARD!r} is not one of quest {quest_id}'s "
                  f"rewards ({names}). Set ANY_REWARD = True for all of them.")
            cmd.cancel_registered_quests()
            return
        targets = [(match[0], QUANT)]

    for name, target in targets:
        cmd.farming_logger(name, target)
        while cmd.is_still_connected() and not await cmd.has_item(name, target):
            await _turn_in_materials(cmd)

    cmd.cancel_registered_quests()
