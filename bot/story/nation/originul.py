"""The Originul questline -- quests 7881-7889 in /Originul.

Port of ``Story/Nation/Originul.cs``.

Nine quests: seven plain kills (one of which names three monsters), and two that
the reference writes out itself because they need a specific cell -- 7887 for five
Dreadfiends in r7, 7889 for twenty-five Bloodfiends in r10 -- each behind the same
``QuestProgression`` guard the helper carries.
"""
from core.command import Command
from bot.core_bots import equip_class
from bot.core_story import kill_quest
from templates.hunt import hunt_item

#: The map, and the quest that gates the chain.
MAP_NAME = "Originul"
LAST_QUEST = 7889

#: The plain kills, in order, as ``(quest, monster or monsters)``.
KILLS = (
    (7881, "Inquisitor Guard"),
    (7882, "Inquisitor Captain"),
    (7883, "Grand Inquisitor"),
    (7884, ("Inquisitor Guard", "Inquisitor Captain", "Grand Inquisitor")),
    (7885, "Bloodfiend"),
    (7886, "Bloodfiend"),
    (7888, "Fiend Champion"),
)

#: The two cell-bound quests, as ``(quest, cell, pad, monster, item, qty)``.
CELL_QUESTS = (
    (7887, "r7", "left", "Dreadfiend", "Dreadfiend Executed", 5),
    (LAST_QUEST, "r10", "Top", "Bloodfiend", "Mutineer Crushed", 25),
)

#: Which of the kills the reference does with the solo class.
SOLO_QUEST = 7888


async def main(cmd: Command):
    if await cmd.is_completed_before(LAST_QUEST):
        return

    for quest_id, monsters in KILLS:
        if quest_id == SOLO_QUEST:
            await equip_class(cmd, solo=True)
        await kill_quest(cmd, quest_id, MAP_NAME, monsters)

    await equip_class(cmd)
    for quest_id, cell, pad, monster, item, qty in CELL_QUESTS:
        await _cell_quest(cmd, quest_id, cell, pad, monster, item, qty)
    cmd.bot.log("[nation] Originul questline completed.")


async def _cell_quest(cmd: Command, quest_id: int, cell: str, pad: str,
                      monster: str, item: str, qty: int) -> None:
    """One of the two quests the reference writes out with its own cell."""
    if await cmd.is_completed_before(quest_id):
        return
    await cmd.ensure_accept_quest(quest_id)
    await hunt_item(cmd, item, qty, MAP_NAME, cell=cell, pad=pad,
                    monster_name=monster, is_temp=False)
    await cmd.ensure_turn_in_quest(quest_id)
