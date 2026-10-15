"""Tainted Claymore -- quest 121, after Evil rank 8 and a /pines chain.

Port of ``Nation/Various/TaintedClaymore.cs``.

Quest 319 picks up a *map item* (id 56, seven times) rather than a drop, which is
``Command.get_map_item``; the rest of the chain is four kills.
"""
from core.command import Command
from bot.core_farms import farm_faction
from templates.hunt import hunt_item, kill_quest

#: The story chain's last quest -- the reference skips the whole chain if it is done.
PREREQ_LAST = 324

#: The map-item quest: quest id, its map, item id, and how many.
MAP_QUEST = 319
MAP_QUEST_MAP = "tavern"
MAP_ITEM = 56
MAP_ITEM_QTY = 7

#: The four kill quests after it, as ``(quest, monster)`` -- all in /pines.
KILL_QUESTS = (
    (320, "Pine Grizzly"),
    (321, "Red Shell Turtle"),
    (322, "Twistedtooth"),
    (324, "Red Shell Turtle"),
)

#: The weapon's own quest and drop.
QUEST_ID = 121
ITEM = "Tainted Claymore"
BLADE = "Warrior Claymore Blade"
BLADE_MAP = "battleundera"
BLADE_MONSTER = "Undead Berserker"

#: Evil rank the reference farms before the quest.
EVIL_RANK = 8


async def main(cmd: Command):
    await pre_req(cmd)
    await get_wep(cmd)


async def pre_req(cmd: Command) -> None:
    """The /tavern and /pines chain, skipped once quest 324 is done."""
    if await cmd.is_completed_before(PREREQ_LAST):
        return

    await cmd.ensure_accept_quest(MAP_QUEST)
    while cmd.is_still_connected() and cmd.is_not_in_map(MAP_QUEST_MAP):
        await cmd.join_map(MAP_QUEST_MAP)
    for _ in range(MAP_ITEM_QTY):
        await cmd.get_map_item(MAP_ITEM)
    await cmd.ensure_turn_in_quest(MAP_QUEST)

    for quest_id, monster in KILL_QUESTS:
        await kill_quest(cmd, quest_id, "pines", monster)


async def get_wep(cmd: Command) -> None:
    """Quest 121 itself."""
    if await cmd.has_item(ITEM):
        return

    cmd.add_drop(ITEM)
    await farm_faction(cmd, "Evil", EVIL_RANK)
    await cmd.ensure_accept_quest(QUEST_ID)
    await hunt_item(cmd, BLADE, 1, BLADE_MAP, monster_name=BLADE_MONSTER,
                    is_temp=False)
    await cmd.ensure_turn_in_quest(QUEST_ID)
