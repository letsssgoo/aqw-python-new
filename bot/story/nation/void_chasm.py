"""The Void Chasm storyline -- quests 9543-9552 in /voidchasm.

Port of ``Story/Nation/VoidChasm.cs``, which runs the Void Refuge storyline
first and then its own ten quests.

Five of the ten also want map items -- one of them six times, three of them
several items -- and three name more than one monster, which
``bot.core_story.kill_quest`` resolves by position.
"""
from core.command import Command
from bot.core_bots import equip_class
from bot.core_story import kill_quest, map_item_quest
from bot.story.nation.void_refuge import main as void_refuge

#: The map, and the quest that gates the chain.
MAP_NAME = "voidchasm"
LAST_QUEST = 9552

#: ``(quest, map item id or ids, how many, monster or monsters)``, in the
#: reference's own order; ``None`` means that quest has no such step.
STEPS = (
    (9543, None, 0, "Paladin Ascendant"),
    (9544, None, 0, "Nation Outrider"),
    (9545, 12619, 6, "Paladin Ascendant"),
    (9546, (12620, 12621), 1, None),
    (9547, 12622, 1, "Nation Outrider"),
    (9548, None, 0, "Void Fang"),
    (9549, (12623, 12627, 12628), 1, "The Hushed"),
    (9550, 12624, 4, ("The Hushed", "Void Fang")),
    (9551, (12625, 12626), 1, "Carnage"),
    (LAST_QUEST, None, 0, "Carcano"),
)

#: The one step the reference fights solo.
SOLO_QUEST = 9551


async def main(cmd: Command):
    if await cmd.is_completed_before(LAST_QUEST):
        return

    await void_refuge(cmd)

    for quest_id, item_ids, qty, monsters in STEPS:
        if quest_id == SOLO_QUEST:
            await equip_class(cmd, solo=True)
        if item_ids is not None:
            await map_item_quest(cmd, quest_id, MAP_NAME, item_ids, qty)
        if monsters is not None:
            await kill_quest(cmd, quest_id, MAP_NAME, monsters)
