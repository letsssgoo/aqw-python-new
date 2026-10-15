"""The Terces Archive questline -- quests 10549-10557 in /tercesarchive.

Port of ``Story/Nation/tercesarchive.cs``, which runs the Oblivion Tundra
questline first and then its own nine quests.

Three of them name more than one monster, which ``bot.core_story.kill_quest``
maps onto them by position, and two of the map-item steps are written as separate
calls exactly as the reference writes them.
"""
from core.command import Command
from bot.core_bots import equip_class
from bot.core_story import kill_quest, map_item_quest
from bot.story.nation.oblivion_tundra import main as oblivion_tundra

#: The map, and the quest that gates the chain.
MAP_NAME = "tercesarchive"
LAST_QUEST = 10557

#: The reference's own monster list.
OBLIVION_MAGUS = "Oblivion Magus"
FIENDISH_DEVOURER = "Fiendish Devourer"
NIGHTMARE_FIEND = "Nightmare Fiend"
WASTED_CLONE = "Wasted Clone"
FIEND_OF_VORACITY = "Fiend of Voracity"

#: The plain hunts, as ``(quest, monster or monsters)``.
HUNTS = (
    (10549, OBLIVION_MAGUS),
    (10550, FIENDISH_DEVOURER),
    (10551, (FIENDISH_DEVOURER, OBLIVION_MAGUS)),
    (10553, WASTED_CLONE),
    (10554, NIGHTMARE_FIEND),
    (10555, (WASTED_CLONE, NIGHTMARE_FIEND)),
)

#: The one solo hunt, and the quests of the two map-item steps.
SOLO_HUNT = (10556, FIEND_OF_VORACITY)
QUEST_10552 = (10552, (15393, 15394))
QUEST_10557 = (LAST_QUEST, 15395)


async def main(cmd: Command):
    if await cmd.is_completed_before(LAST_QUEST):
        return

    await oblivion_tundra(cmd)

    for quest_id, monsters in HUNTS:
        await kill_quest(cmd, quest_id, MAP_NAME, monsters)

    for item_id in QUEST_10552[1]:
        await map_item_quest(cmd, QUEST_10552[0], MAP_NAME, item_id)

    await equip_class(cmd, solo=True)
    await kill_quest(cmd, SOLO_HUNT[0], MAP_NAME, SOLO_HUNT[1])

    await map_item_quest(cmd, QUEST_10557[0], MAP_NAME, QUEST_10557[1])
