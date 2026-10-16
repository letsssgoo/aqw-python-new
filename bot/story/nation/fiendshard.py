"""The Fiendshard questline -- quests 7892-7898 in /Fiendshard.

Port of ``Story/Nation/Fiendshard.cs``.  It runs the Originul questline first,
then its own seven quests, each behind its own progression guard (the file has no
guard of its own).

Two of them the reference writes out by hand because they mix steps: 7892 and
7895 each kill a monster *and* pick a map item up, and 7894's turn-in waits on
its third kill.

Note:
    7898 has a kill by the monster's map id and the drop by *item* id (59059,
    which nothing in the tree names), so it uses the id overload of the hunt.
    The ``Core.Join("tercessuinotlim")`` before the chain is the reference's own
    detour and is kept.
"""
from core.command import Command
from bot.core_bots import equip_class
from bot.core_story import kill_quest, map_item_quest
from bot.story.nation.originul import main as originul
from templates.hunt import hunt_item, hunt_item_by_id

#: The map, and the quest that gates the chain.
MAP_NAME = "Fiendshard"
LAST_QUEST = 7898

#: The three hunts 7895 needs, as ``(item, qty, cell, pad, monster)``.
HUNTS_7895 = (
    ("Rogue Fiend Defeated", 5, "r2", "Left", "Rogue Fiend"),
    ("Paladin Fiend Defeated", 5, "r5", "Left", "Paladin Fiend"),
    ("Void Knight Defeated", 3, None, "Left", "Void Knight"),
)

#: The three one-monster quests that only kill, as ``(quest, item, qty, cell,
#: monster)``.
PLAIN = (
    (7893, "Fiends Interrogated", 3, "r2", "Rogue Fiend"),
    (7894, "Key Fragments Located", 4, "r2", "Rogue Fiend"),
)

#: 7892's kill, and the map item that completes it.
KILL_7892 = ("Rogue Fiends Defeated", 4, "r2", "Rogue Fiend")
MAP_ITEM_7892 = 7983
MAP_ITEM_7895 = 7984

#: 7898's two kills: the named one, then one by map id and item id.
KILL_7898 = ("Fiends Fended Off", 15, "r9", "Paladin Fiend")
ID_KILL_7898 = (59059, 1, "r9", 15)


async def main(cmd: Command):
    await originul(cmd)

    cmd.bot.log("[nation] making sure the portal quest is done; joining "
          "/tercessuinotlim first, as the reference does")
    while cmd.is_still_connected() and cmd.is_not_in_map("tercessuinotlim"):
        await cmd.join_map("tercessuinotlim")

    await equip_class(cmd)
    if not await cmd.is_completed_before(7892):
        await cmd.ensure_accept_quest(7892)
        await hunt_item(cmd, KILL_7892[0], KILL_7892[1], MAP_NAME,
                        cell=KILL_7892[2], pad="Left",
                        monster_name=KILL_7892[3], is_temp=False)
        await map_item_quest(cmd, 7892, MAP_NAME, MAP_ITEM_7892)

    for quest_id, item, qty, cell, monster in PLAIN:
        if await cmd.is_completed_before(quest_id):
            continue
        await cmd.ensure_accept_quest(quest_id)
        await hunt_item(cmd, item, qty, MAP_NAME, cell=cell, pad="Left",
                        monster_name=monster, is_temp=False)
        await cmd.ensure_turn_in_quest(quest_id)

    if not await cmd.is_completed_before(7895):
        await cmd.ensure_accept_quest(7895)
        for item, qty, cell, pad, monster in HUNTS_7895:
            await hunt_item(cmd, item, qty, MAP_NAME, cell=cell, pad=pad,
                            monster_name=monster, is_temp=False)
        await map_item_quest(cmd, 7895, MAP_NAME, MAP_ITEM_7895)

    await kill_quest(cmd, 7896, MAP_NAME, "Paladin Fiend")

    if not await cmd.is_completed_before(7897):
        await equip_class(cmd, solo=True)
        await kill_quest(cmd, 7897, MAP_NAME, ("Dirtlicker", "Fiend Shard"))
        await cmd.jump_cell("Enter", "Spawn")

    if not await cmd.is_completed_before(LAST_QUEST):
        await equip_class(cmd, solo=True)
        await cmd.ensure_accept_quest(LAST_QUEST)
        await hunt_item(cmd, KILL_7898[0], KILL_7898[1], MAP_NAME,
                        cell=KILL_7898[2], pad="Left",
                        monster_name=KILL_7898[3], is_temp=False)
        await hunt_item_by_id(cmd, ID_KILL_7898[0], ID_KILL_7898[1], MAP_NAME,
                              cell=ID_KILL_7898[2],
                              monster_map_id=ID_KILL_7898[3])
        await cmd.jump_cell("Enter", "Spawn")
        await cmd.ensure_turn_in_quest(LAST_QUEST)
