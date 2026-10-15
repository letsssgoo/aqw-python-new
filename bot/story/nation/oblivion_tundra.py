"""The Oblivion Tundra questline -- quests 10036-10045 in /obliviontundra.

Port of ``Story/Nation/OblivionTundra.cs``, which runs the Deleuze Tundra
questline first and then its own ten quests.

Note:
    Two of the monsters come straight out of the reference's own list, trailing
    space included: its array spells ``"Oblivion Magus "`` with one.  That is kept
    as written, so if the hunt never finds the monster, this is the line to look
    at -- say the word and the space goes.
"""
from core.command import Command
from bot.core_bots import equip_class
from bot.core_story import kill_quest, map_item_quest
from bot.story.nation.deleuze_tundra import main as deleuze_tundra

#: The map, and the quest that gates the chain.
MAP_NAME = "obliviontundra"
LAST_QUEST = 10045

#: The reference's own monster list, spelled as it spells them.
EMPTY_CREATURE = "Empty Creature"
HUSHED = "Hushed"
WITHERED_ARCHFIEND = "Withered Archfiend"
OBLIVION_MAGUS = "Oblivion Magus "          # its trailing space is the reference's
ETTIN_FIEND = "Ettin Fiend"
ARCHFIEND_OBLIVION = "Archfiend Oblivion"

#: The plain hunts, as ``(quest, monster or monsters)``.
HUNTS = (
    (10038, HUSHED),
    (10039, (HUSHED, EMPTY_CREATURE)),
    (10042, OBLIVION_MAGUS),
    (10043, ETTIN_FIEND),
    (10044, (OBLIVION_MAGUS, ETTIN_FIEND)),
)

#: The two solo hunts.
SOLO_HUNTS = (
    (10040, WITHERED_ARCHFIEND),
    (LAST_QUEST, ARCHFIEND_OBLIVION),
)

#: The three map-item steps, as ``(quest, ((item id, qty), ...))``.
MAP_ITEM_STEPS = (
    (10037, ((14065, 5), (14066, 1))),
    (10041, ((14067, 3), (14068, 1))),
)

#: Quest 10036 does both, in the reference's order.
MIXED_QUEST = 10036
MIXED_ITEM = 14064


async def main(cmd: Command):
    if await cmd.is_completed_before(LAST_QUEST):
        return

    await deleuze_tundra(cmd)

    await map_item_quest(cmd, MIXED_QUEST, MAP_NAME, MIXED_ITEM)
    await kill_quest(cmd, MIXED_QUEST, MAP_NAME, EMPTY_CREATURE)

    for quest_id, items in MAP_ITEM_STEPS:
        await map_item_quest(cmd, quest_id, MAP_NAME, items)

    for quest_id, monster in HUNTS:
        await kill_quest(cmd, quest_id, MAP_NAME, monster)

    for quest_id, monster in SOLO_HUNTS:
        await equip_class(cmd, solo=True)
        await kill_quest(cmd, quest_id, MAP_NAME, monster)
