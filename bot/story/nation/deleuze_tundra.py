"""The Deleuze Tundra questline -- quests 10023-10031 in /deleuzetundra.

Port of ``Story/Nation/DeleuzeTundra.cs``, which runs the Void Chasm storyline
first and then its own nine quests.

Four of them mix a map item with a kill: the reference grabs the item and lets the
turn-in fail (the kill is still missing), then kills and turns the quest in --
which is why the two steps are two calls here as well.
"""
from core.command import Command
from bot.core_bots import equip_class
from bot.core_story import kill_quest, map_item_quest
from bot.story.nation.void_chasm import main as void_chasm

#: The map, and the quest that gates the chain.
MAP_NAME = "deleuzetundra"
LAST_QUEST = 10031

#: The five monsters the reference names, in its own order.
EMPTY_CREATURE = "Empty Creature"
NATION_OUTRIDER = "Nation Outrider"
OBLIVION_MAGUS = "Oblivion Magus"
OBLIVIONS_HERALD = "Oblivion's Herald"

#: The four plain hunts, as ``(quest, monster)``.
HUNTS = (
    (10023, EMPTY_CREATURE),
    (10024, NATION_OUTRIDER),
    (10026, OBLIVION_MAGUS),
)

#: Quest 10025: two map items, in two calls exactly as the reference writes them.
QUEST_10025 = 10025
MAP_ITEM_10025_A = (14048, 5)
MAP_ITEM_10025_B = (14049, 1)

#: The three steps that grab an item and then kill, as ``(quest, item, qty,
#: monster)``.
MIXED = (
    (10028, 14052, 1, EMPTY_CREATURE),
    (10029, 14053, 5, NATION_OUTRIDER),
    (10030, 14054, 1, OBLIVION_MAGUS),
)

#: The one map-item-only step.
QUEST_10027 = (10027, (14050, 14051))


async def main(cmd: Command):
    if await cmd.is_completed_before(LAST_QUEST):
        return

    await void_chasm(cmd)

    for quest_id, monster in HUNTS:
        await kill_quest(cmd, quest_id, MAP_NAME, monster)

    # the reference also calls EnsureAccept first; map_item_quest accepts itself
    await map_item_quest(cmd, QUEST_10025, MAP_NAME, *MAP_ITEM_10025_A)
    await map_item_quest(cmd, QUEST_10025, MAP_NAME, *MAP_ITEM_10025_B)

    await map_item_quest(cmd, QUEST_10027[0], MAP_NAME, QUEST_10027[1], 1)

    for quest_id, item, qty, monster in MIXED:
        await map_item_quest(cmd, quest_id, MAP_NAME, item, qty)
        await kill_quest(cmd, quest_id, MAP_NAME, monster)

    await equip_class(cmd, solo=True)
    await kill_quest(cmd, LAST_QUEST, MAP_NAME, OBLIVIONS_HERALD)
