"""The Terces Invasion questline -- quests 10572-10581 in /tercesinvasion.

Port of ``Story/Nation/TercesInvasion.cs``, which runs the Terces Archive
questline first and then its own ten quests.

Three of them name more than one monster (10580 names two), which
``bot.core_story.kill_quest`` maps onto them by position, and two mix a map item
with a solo kill.
"""
from core.command import Command
from bot.core_bots import equip_class
from bot.core_story import kill_quest, map_item_quest
from bot.story.nation.terces_archive import main as terces_archive

#: The map, and the quest that gates the chain.
MAP_NAME = "tercesinvasion"
LAST_QUEST = 10581

#: The reference's own monster list.
BLOODTHIRSTY_VOID = "Bloodthirsty Void"
VAMPIRIC_DEVOURER = "Vampiric Devourer"
VOID_CULTIST = "Void Cultist"
ARCHFIEND_CASIMIR = "Archfiend Casimir"
ARCHFIEND_VIGNERON = "Archfiend Vigneron"
RODELEROS_SOLDIER = "Rodeleros Soldier"
ELEMENTAL_FIEND = "Elemental Fiend"
ARCHFIEND_RODELEROS = "Archfiend Rodeleros"

#: The plain farm hunts, as ``(quest, monster or monsters)``.
HUNTS = (
    (10572, BLOODTHIRSTY_VOID),
    (10573, VAMPIRIC_DEVOURER),
    (10574, VOID_CULTIST),
    (10577, RODELEROS_SOLDIER),
    (10579, ELEMENTAL_FIEND),
    (10580, (RODELEROS_SOLDIER, ELEMENTAL_FIEND)),
)

#: The two map-item steps that are alone, as ``(quest, item id or ids)``.
MAP_ITEM_ONLY = (
    (10578, (15434, 15435, 15436)),
)

#: The two that mix an item with a solo kill, as ``(quest, item id, monster)``.
MIXED = (
    (10575, 15432, ARCHFIEND_CASIMIR),
    (10576, 15433, ARCHFIEND_VIGNERON),
)

#: The one solo hunt.
SOLO_HUNT = (LAST_QUEST, ARCHFIEND_RODELEROS)


async def main(cmd: Command):
    if await cmd.is_completed_before(LAST_QUEST):
        return

    await terces_archive(cmd)

    for quest_id, monsters in HUNTS:
        await kill_quest(cmd, quest_id, MAP_NAME, monsters)

    for quest_id, item_ids in MAP_ITEM_ONLY:
        await map_item_quest(cmd, quest_id, MAP_NAME, item_ids)

    for quest_id, item_id, monster in MIXED:
        await map_item_quest(cmd, quest_id, MAP_NAME, item_id)
        await equip_class(cmd, solo=True)
        await kill_quest(cmd, quest_id, MAP_NAME, monster)

    await equip_class(cmd, solo=True)
    await kill_quest(cmd, SOLO_HUNT[0], MAP_NAME, SOLO_HUNT[1])
