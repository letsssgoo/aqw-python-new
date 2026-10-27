"""DragonFable Origins -- /firewar, /northmountain, /charredplains, /drakonnan.

Port of ``Story/DragonFableOrigins.cs``: the four chapters of the Drakonnan
story, which the Lord of Order daily's ``Strike of Order`` (quest 7160) needs.

One source bug is fixed and said out loud: the ``Perfect Pyritium`` step accepts
quest **6296** a second time instead of 6297, which leaves 6297 unaccepted and
its drop (gated on that quest) unreachable.  6297 is accepted here.
"""
from bot.core_bots import equip_class, kill_once
from bot.core_story import (chain_quest, kill_quest, map_item_quest,
                            quest_progression)
from bot.script_log import ScriptLog
from core.command import Command
from templates.hunt import hunt_item

TAG = "DragonFable Origins"

GREAT_FIRE_WAR_LAST = 6299
NORTH_MOUNTAIN_LAST = 6307
CHARRED_PLAINS_LAST = 6311
DRAKONNAN_LAST = 6325

#: ``while (!TempInv.Contains(43572)) { Attack("*"); }`` -- quest 6299's drop.
FIRE_WAR_DROP = 43572
FIRE_WAR_CELL = ("r10", "Left")


async def _quest(cmd: Command, quest_id: int, body) -> None:
    """``if (!QuestProgression(q)) { accept; body; complete; }``."""
    if await quest_progression(cmd, quest_id):
        return
    log = ScriptLog(cmd, TAG)
    if await cmd.ensure_accept_quest(quest_id) is False:
        log.warning(f"quest {quest_id} could not be accepted")
        return
    await body()
    if await cmd.ensure_turn_in_quest(quest_id) is False:
        log.warning(f"quest {quest_id} could not be turned in")


async def _attack_until_temp(cmd: Command, map_name: str, item_id: int,
                             cell: str, pad: str) -> None:
    guard = cmd.pass_guard(f"temp item {item_id} in {map_name}")
    while (cmd.is_still_connected()
           and cmd.bot.player.get_item_temp_inventory_by_id(item_id) is None):
        await kill_once(cmd, map_name, cell, pad, "*")
        if not await guard.tick():
            return


async def great_fire_war(cmd: Command) -> None:
    """``GreatFireWar``: quests 6294-6299."""
    if await cmd.is_completed_before(GREAT_FIRE_WAR_LAST):
        return

    await kill_quest(cmd, 6294, "firewar", "Fire Dragon")
    await kill_quest(cmd, 6295, "firewar", "Fire Dragon")

    async def q6296() -> None:
        await hunt_item(cmd, "Pyritium Shards", 5, "firewar", cell="r8",
                        pad="Right", monster_name="Inferno Dragon")

    async def q6297() -> None:
        # the source accepts 6296 here; 6297 is what owns this drop
        await hunt_item(cmd, "Perfect Pyritium", 1, "firewar", cell="r8",
                        pad="Right", monster_name="Inferno Dragon")

    await _quest(cmd, 6296, q6296)
    await _quest(cmd, 6297, q6297)

    await equip_class(cmd, solo=True)
    await kill_quest(cmd, 6298, "firewar", "Uriax")

    async def q6299() -> None:
        await equip_class(cmd, solo=True)
        await cmd.join_map("firewar")
        await cmd.jump_cell(*FIRE_WAR_CELL)
        await _attack_until_temp(cmd, "firewar", FIRE_WAR_DROP,
                                 FIRE_WAR_CELL[0], FIRE_WAR_CELL[1])

    await _quest(cmd, GREAT_FIRE_WAR_LAST, q6299)
    await cmd.jump_cell(cmd.bot.player.CELL, cmd.bot.player.PAD)


async def north_mountain(cmd: Command) -> None:
    """``NorthMountain``: quests 6301-6307."""
    if await cmd.is_completed_before(NORTH_MOUNTAIN_LAST):
        return

    async def q6301() -> None:
        await hunt_item(cmd, "Monsters Defeated", 8, "northmountain",
                        monster_name="Ice Elemental")
        await cmd.join_map("northmountain")
        await cmd.get_map_item(5812)

    await _quest(cmd, 6301, q6301)

    await kill_quest(cmd, 6302, "northmountain", "Ice Elemental")
    await kill_quest(cmd, 6303, "northmountain", "Ursice Savage")
    await kill_quest(cmd, 6304, "northmountain", "Ice Spitter")
    await kill_quest(cmd, 6305, "northmountain", "Ice Elemental")

    # Unlock the Cave 6306 -- two map-item groups under one quest
    async def q6306() -> None:
        await cmd.join_map("northmountain")
        await cmd.get_map_item(5813, 4)
        await cmd.get_map_item(5814)

    await _quest(cmd, 6306, q6306)

    await kill_quest(cmd, NORTH_MOUNTAIN_LAST, "northmountain", "Izotz")


async def charred_plains(cmd: Command) -> None:
    """``CharredPlains``: quests 6308-6311."""
    if await cmd.is_completed_before(CHARRED_PLAINS_LAST):
        return

    await kill_quest(cmd, 6308, "charredplains", "Fire Dragon")
    await map_item_quest(cmd, 6309, "charredplains", 5815)
    await kill_quest(cmd, 6310, "charredplains", "Akriloth")
    await kill_quest(cmd, CHARRED_PLAINS_LAST, "northmountain", "Izotz")


async def drakonnan(cmd: Command) -> None:
    """``Drakonnan``: quests 6312-6325."""
    if await cmd.is_completed_before(DRAKONNAN_LAST):
        return

    await map_item_quest(cmd, 6312, "drakonnan", 5827, 5)
    await kill_quest(cmd, 6313, "drakonnan", "Fire Dragon")
    await kill_quest(cmd, 6314, "drakonnan", "Living Lava")
    await kill_quest(cmd, 6315, "drakonnan", "Fire Dragon")
    await kill_quest(cmd, 6316, "northmountain", "Ice Elemental")
    await map_item_quest(cmd, 6317, "northmountain", 5826, 6)
    await kill_quest(cmd, 6318, "drakonnan", "Fire Elemental")
    await kill_quest(cmd, 6319, "drakonnan", "Living Fire")
    await kill_quest(cmd, 6320, "drakonnan", "Fire Dragon")
    await kill_quest(cmd, 6321, "drakonnan", "Living Lava")
    await kill_quest(cmd, 6322, "drakonnan", "Fire Elemental")
    await kill_quest(cmd, 6323, "drakonnan", "Fire Elemental")
    await kill_quest(cmd, 6324, "drakonnan", "Drakonnan")
    await kill_quest(cmd, DRAKONNAN_LAST, "drakonnan", "Ultra Drakonnan")


async def do_all(cmd: Command) -> None:
    """``DragonFableOriginsAll``: the four chapters in the source's order."""
    await great_fire_war(cmd)
    await north_mountain(cmd)
    await charred_plains(cmd)
    await drakonnan(cmd)


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the four DragonFable Origins chapters...")
    await do_all(cmd)
    log.success("DragonFable Origins done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
