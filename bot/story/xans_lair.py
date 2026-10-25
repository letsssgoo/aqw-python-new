"""``XansLair`` -- Volcano, XanTown, Xan's Cave.

Port of ``Story/XansLair.cs``: the volcano's 20 levels, Andesi's line, Scoria's
quest, and Warlic's cave line.  The source jumps to ``r12/Left`` after the
XanTown quests because that map is aggro; the same jump is kept.
"""
from bot.core_story import kill_quest, map_item_quest, quest_progression, CustomError
from core.command import Command
from templates.hunt import hunt_item

XANTOWN_SAFE_CELL = "r12"


async def _quest(cmd: Command, quest_id: int, body) -> None:
    """``if (!Story.QuestProgression(q)) { accept; body; complete; }``."""
    if await quest_progression(cmd, quest_id):
        return
    if await cmd.ensure_accept_quest(quest_id) is False:
        raise CustomError(f"quest {quest_id} could not be accepted")
    await body()
    if await cmd.ensure_turn_in_quest(quest_id) is False:
        raise CustomError(f"quest {quest_id} could not be turned in")


async def volcano(cmd: Command) -> None:
    """``XansLair.Volcano``: levels 1-20, quests 1242-1261."""
    if await cmd.is_completed_before(1261):
        return

    await kill_quest(cmd, 1242, "volcano", "Lava Golem")

    async def q1243() -> None:
        await cmd.get_map_item(526, 3)
        await hunt_item(cmd, "Broiled Clue", 7, "volcano",
                        monster_name="Fire Imp")

    await _quest(cmd, 1243, q1243)
    await kill_quest(cmd, 1244, "volcano", "Fire Imp")

    async def q1245() -> None:
        await cmd.get_map_item(527, 8)
        await hunt_item(cmd, "Blazing Clue", 10, "volcano",
                        monster_name="Lava Golem")

    await _quest(cmd, 1245, q1245)
    await kill_quest(cmd, 1246, "volcano", "Fire Imp")
    await kill_quest(cmd, 1247, "volcano", "Fire Imp")
    await map_item_quest(cmd, 1248, "volcano", 528, 12)
    await kill_quest(cmd, 1249, "volcano", "Flamethrower Dwakel")

    async def q1250() -> None:
        await cmd.get_map_item(529, 8)
        await hunt_item(cmd, "Torched Clue", 10, "volcano",
                        monster_name="Fire Imp")

    await _quest(cmd, 1250, q1250)
    await kill_quest(cmd, 1251, "volcano", "Flamethrower Dwakel")

    async def q1252() -> None:
        await cmd.get_map_item(530, 10)
        await hunt_item(cmd, "Melted Clue", 10, "volcano",
                        monster_name="Fire Imp")

    await _quest(cmd, 1252, q1252)
    await kill_quest(cmd, 1253, "volcano", "Flame Elemental")
    await map_item_quest(cmd, 1254, "volcano", 531, 12)
    await kill_quest(cmd, 1255, "volcano", "Fire Imp")
    await kill_quest(cmd, 1256, "volcano", "Fire Imp")
    await map_item_quest(cmd, 1257, "volcano", 532, 10)
    await kill_quest(cmd, 1258, "volcano", "Flamethrower Dwakel")

    async def q1259() -> None:
        await hunt_item(cmd, "Singed Clue", 15, "volcano",
                        monster_name="Fire Imp")

    await _quest(cmd, 1259, q1259)

    async def q1260() -> None:
        await cmd.get_map_item(533, 6)
        await hunt_item(cmd, "Smoking Clue", 13, "volcano",
                        monster_name="Fire Imp")

    await _quest(cmd, 1260, q1260)
    await kill_quest(cmd, 1261, "volcano", "Magman")


async def andesis_quests(cmd: Command) -> None:
    """``XansLair.AndesisQuests``: quests 1733-1739 in /xantown."""
    if await cmd.is_completed_before(1739):
        return

    await map_item_quest(cmd, 1733, "xantown", 922)
    await kill_quest(cmd, 1734, "xantown", "Fire Imp")
    await kill_quest(cmd, 1735, "xantown", "Fire Imp")
    await kill_quest(cmd, 1736, "xantown", "Fire Imp")
    await map_item_quest(cmd, 1737, "xantown", 923, 4)
    await map_item_quest(cmd, 1738, "xantown", 924)
    await map_item_quest(cmd, 1739, "xantown", 925)
    await cmd.jump_cell(XANTOWN_SAFE_CELL, "Left")


async def scorias_quests(cmd: Command) -> None:
    """``XansLair.ScoriasQuestsQuests``: quest 1740."""
    if await cmd.is_completed_before(1740):
        return
    await kill_quest(cmd, 1740, "xantown", "Xan")
    await cmd.jump_cell(XANTOWN_SAFE_CELL, "Left")


async def warlics_quests(cmd: Command) -> None:
    """``XansLair.WarlicsQuests``: quests 2151-2157 in /xancave."""
    if await cmd.is_completed_before(2157):
        return

    await map_item_quest(cmd, 2151, "xancave", 1220)
    await kill_quest(cmd, 2152, "xancave", "Lava Goblin")
    await map_item_quest(cmd, 2153, "xancave", 1221)
    await kill_quest(cmd, 2154, "xancave", "Lava Goblin")

    async def q2155() -> None:
        await cmd.get_map_item(1223, 8)
        await hunt_item(cmd, "Fire Salts", 10, "xancave",
                        monster_name="Lava Goblin")
        await hunt_item(cmd, "Fire Wire", 10, "xancave",
                        monster_name="Lava Goblin")

    await _quest(cmd, 2155, q2155)
    await kill_quest(cmd, 2156, "xancave", "Shurpu Ring Guardian")
    await map_item_quest(cmd, 2157, "xancave", 1222)


async def do_all(cmd: Command) -> None:
    """``XansLair.DoAll``: Volcano, Andesi, Scoria, Warlic."""
    await volcano(cmd)
    await andesis_quests(cmd)
    await scorias_quests(cmd)
    await warlics_quests(cmd)


async def main(cmd: Command):
    await do_all(cmd)
