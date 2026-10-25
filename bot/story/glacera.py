"""``GlaceraStory`` -- the frozen north, region by region.

Port of ``Story/Glacera.cs``, every region it lists: FrozenTower, FrozenRuins,
Glacera, Glacera1, FrozenRuins2, Northstar, FrostRuins, IceWindPass, IceDungeon.

Map names are the lowercase ids the engine joins on; the source writes a few of
them capitalised (``IceWindPass``, ``IceDungeon``, ``Glacera``), which is the same
map, not a different one.
"""
from bot.core_bots import equip_class
from bot.core_story import CustomError, kill_quest, map_item_quest, quest_progression
from core.command import Command
from templates.hunt import hunt_item

FROZEN_TOWER = "frozentower"
FROZEN_RUINS = "frozenruins"
GLACERA = "glacera"
NORTHSTAR = "northstar"
ICEWINDPASS = "icewindpass"
ICEWINDWAR = "icewindwar"
ICEDUNGEON = "icedungeon"


async def _quest(cmd: Command, quest_id: int, body) -> None:
    """``if (!Story.QuestProgression(q)) { accept; body; complete; }``."""
    if await quest_progression(cmd, quest_id):
        return
    if await cmd.ensure_accept_quest(quest_id) is False:
        raise CustomError(f"quest {quest_id} could not be accepted")
    await body()
    if await cmd.ensure_turn_in_quest(quest_id) is False:
        raise CustomError(f"quest {quest_id} could not be turned in")


async def frozen_tower(cmd: Command, cryomancer: bool = False) -> None:
    """``GlaceraStory.FrozenTower``: the tower's 31 quests.

    Args:
        cmd (Command): Facade to act through.
        cryomancer (bool): The reference's own flag -- when true this is the whole
            Cryomancer path and the caller stops here.
    """
    if await cmd.is_completed_before(3937):
        return

    await map_item_quest(cmd, 3907, FROZEN_TOWER, 3022)
    await kill_quest(cmd, 3908, FROZEN_TOWER, "Polar Elemental")
    await map_item_quest(cmd, 3909, FROZEN_TOWER, 3019)
    await map_item_quest(cmd, 3910, FROZEN_TOWER, 3004, 13)

    async def q3911() -> None:
        await hunt_item(cmd, "Refugee Saved", 7, FROZEN_TOWER,
                        monster_name="Frostwyrm")

    await _quest(cmd, 3911, q3911)
    await kill_quest(cmd, 3912, FROZEN_TOWER, "FrostDeep Dweller")
    await map_item_quest(cmd, 3913, FROZEN_TOWER, 3005, 13)
    await kill_quest(cmd, 3914, FROZEN_TOWER, "Twisted Ice")
    await map_item_quest(cmd, 3915, FROZEN_TOWER, 3006)
    await kill_quest(cmd, 3916, FROZEN_TOWER, "Polar Elemental")
    await map_item_quest(cmd, 3917, FROZEN_TOWER, 3007, 6)
    await map_item_quest(cmd, 3918, FROZEN_TOWER, 3013)

    async def q3919() -> None:
        await cmd.get_map_item(3008, 6)
        await hunt_item(cmd, "Ice Sample", 6, FROZEN_TOWER,
                        monster_name="Polar Elemental")

    await _quest(cmd, 3919, q3919)

    async def q3920() -> None:
        await cmd.get_map_item(3020, 1)
        await hunt_item(cmd, "Polar Elemental Guard Defeated", 4, FROZEN_TOWER,
                        monster_name="Polar Elemental")
        await hunt_item(cmd, "Ice Wolf Guard Defeated", 5, FROZEN_TOWER,
                        monster_name="Ice Wolf")

    await _quest(cmd, 3920, q3920)

    async def q3921() -> None:
        await cmd.get_map_item(3017, 6)
        await hunt_item(cmd, "FrostDeep Venom", 1, FROZEN_TOWER,
                        monster_name="FrostDeep Dweller")

    await _quest(cmd, 3921, q3921)
    await kill_quest(cmd, 3922, FROZEN_TOWER, "Polar Elemental")
    await kill_quest(cmd, 3923, FROZEN_TOWER, "Frostwyrm")
    await map_item_quest(cmd, 3924, FROZEN_TOWER, 3009, 6)

    async def q3925() -> None:
        # The source calls ``Story.MapItemQuest(3925, ...)`` inside its own hand
        # block; that only fetches the items here, because the quest is already
        # in progress and the turn-in comes at the end of the block.
        await cmd.get_map_item(3012, 4)
        await cmd.get_map_item(3011, 4)
        await hunt_item(cmd, "Frozen Tail", 5, FROZEN_TOWER,
                        monster_name="Frostwyrm")
        await hunt_item(cmd, "Frozen Scale", 5, FROZEN_TOWER,
                        monster_name="Arctic Eel")

    await _quest(cmd, 3925, q3925)
    await map_item_quest(cmd, 3926, FROZEN_TOWER, 3021)
    await map_item_quest(cmd, 3927, FROZEN_TOWER, 3014, 7)
    await kill_quest(cmd, 3928, FROZEN_TOWER, "Arctic Eel")
    await kill_quest(cmd, 3929, FROZEN_TOWER, "Polar Elemental")
    await kill_quest(cmd, 3930, FROZEN_TOWER, "Twisted Ice")
    await kill_quest(cmd, 3931, FROZEN_TOWER, "Frostwyrm")
    await map_item_quest(cmd, 3932, FROZEN_TOWER, 3016, 13)
    await kill_quest(cmd, 3933, FROZEN_TOWER, "Ice Wolf")
    await kill_quest(cmd, 3934, FROZEN_TOWER, "Rotten Ice")

    async def q3935() -> None:
        await cmd.get_map_item(3018, 13)
        await hunt_item(cmd, "Blood of the Ice Wolf", 1, FROZEN_TOWER,
                        monster_name="Ice Wolf")

    await _quest(cmd, 3935, q3935)

    async def q3936() -> None:
        await hunt_item(cmd, "FrostSpawn Invader defeated", 10, FROZEN_TOWER,
                        monster_name="Frost Invader")

    await _quest(cmd, 3936, q3936)

    async def q3937() -> None:
        await hunt_item(cmd, "Fangbeasts defeated", 15, FROZEN_TOWER,
                        monster_name="Frost Fangbeast")

    await _quest(cmd, 3937, q3937)


async def frozen_ruins(cmd: Command) -> None:
    """``GlaceraStory.FrozenRuins``: quests 3941-3946."""
    if await cmd.is_completed_before(3946):
        return

    await frozen_tower(cmd)

    await kill_quest(cmd, 3941, FROZEN_RUINS, "Frost Fangbeast")
    await kill_quest(cmd, 3942, FROZEN_RUINS, "Frost Reaper")
    await kill_quest(cmd, 3943, FROZEN_RUINS, "Frost Reaper")
    await kill_quest(cmd, 3944, FROZEN_RUINS, "Frost Reaper")

    async def q3945() -> None:
        await cmd.get_map_item(3050, 10)
        await hunt_item(cmd, "Frostbreath Weed", 5, FROZEN_RUINS,
                        monster_name="Frozen Moglinster")

    await _quest(cmd, 3945, q3945)

    async def q3946() -> None:
        if not await cmd.has_item_id(27357):
            await hunt_item(cmd, "Mercury", 1, FROZEN_RUINS,
                            monster_name="Frost Reaper")

    await _quest(cmd, 3946, q3946)


async def glacera(cmd: Command) -> None:
    """``GlaceraStory.Glacera``: quests 3947-3948."""
    if await cmd.is_completed_before(3950):
        return

    await frozen_ruins(cmd)

    async def q3947() -> None:
        await cmd.join_map(GLACERA)
        await cmd.get_map_item(3048, 1)

    await _quest(cmd, 3947, q3947)
    # the reference jumps out of the cutscene cell right after this quest
    await cmd.jump_cell("Enter", "Spawn")

    await kill_quest(cmd, 3948, GLACERA, "Frost Invader")


async def glacera1(cmd: Command) -> None:
    """``GlaceraStory.Glacera1``: quests 3949-3950."""
    if await cmd.is_completed_before(3950):
        return

    await glacera(cmd)
    await map_item_quest(cmd, 3949, GLACERA, 3049, 6)
    await map_item_quest(cmd, 3950, GLACERA, 3047)


async def frozen_ruins2(cmd: Command) -> None:
    """``GlaceraStory.FrozenRuins2``: quests 3951-3954."""
    if await cmd.is_completed_before(3954):
        return

    await glacera1(cmd)

    async def q3951() -> None:
        await hunt_item(cmd, "Ice Beast Destroyed", 10, FROZEN_RUINS,
                        monster_name="Frost Invader")

    await _quest(cmd, 3951, q3951)
    await kill_quest(cmd, 3952, FROZEN_RUINS, "Frost Fangbeast")
    await kill_quest(cmd, 3953, FROZEN_RUINS, "Frost Reaper")
    await kill_quest(cmd, 3954, FROZEN_RUINS, "Frost General")


async def northstar(cmd: Command) -> None:
    """``GlaceraStory.Northstar``: quests 3958-3974."""
    if await cmd.is_completed_before(3971):
        return

    await frozen_ruins2(cmd)

    async def q3958() -> None:
        await hunt_item(cmd, "Monstrous Refugee defeated", 3, NORTHSTAR,
                        monster_name="Monstrous Refugee")
        await hunt_item(cmd, "Frost Invader defeated", 5, NORTHSTAR,
                        monster_name="Frost Invader")

    await _quest(cmd, 3958, q3958)

    async def q3959() -> None:
        await hunt_item(cmd, "FrostSpawn defeated", 7, NORTHSTAR,
                        monster_name="Frost Fangbeast")

    await _quest(cmd, 3959, q3959)
    await kill_quest(cmd, 3960, NORTHSTAR, "Frost Reaper")

    async def q3961() -> None:
        await cmd.get_map_item(3060, 5)
        await cmd.get_map_item(3061, 7)
        await cmd.get_map_item(3073, 5)
        await hunt_item(cmd, "Lodestone Piece", 10, NORTHSTAR,
                        monster_name="Frost Reaper")

    await _quest(cmd, 3961, q3961)
    await map_item_quest(cmd, 3972, NORTHSTAR, 3063, 10)

    async def q3973() -> None:
        await hunt_item(cmd, "Frozen Dinners", 10, NORTHSTAR,
                        monster_name="Frost Fangbeast")

    await _quest(cmd, 3973, q3973)

    async def q3974() -> None:
        await hunt_item(cmd, "FrostSpawn Spine", 10, NORTHSTAR,
                        monster_name="Frost Fangbeast")
        await hunt_item(cmd, "FrostSpawn Scale", 10, NORTHSTAR,
                        monster_name="Frost Fangbeast")

    await _quest(cmd, 3974, q3974)
    await kill_quest(cmd, 3970, NORTHSTAR, "The Queen's Gift")
    await kill_quest(cmd, 3971, NORTHSTAR, "Karok The Fallen")


async def frost_ruins(cmd: Command) -> None:
    """``GlaceraStory.FrostRuins``: the four quests again, as plain kills.

    Its own guard is 3954, the same one ``FrozenRuins2`` uses, so on a completed
    account this returns before anything runs -- which is what the source does.
    """
    if await cmd.is_completed_before(3954):
        return

    await glacera1(cmd)
    await kill_quest(cmd, 3951, FROZEN_RUINS, "Frost Invader")
    await kill_quest(cmd, 3952, FROZEN_RUINS, "Frost Fangbeast")
    await kill_quest(cmd, 3953, FROZEN_RUINS, "Frost Reaper")
    await kill_quest(cmd, 3954, FROZEN_RUINS, "Frost General")


#: The four war quests ``IceWindPass`` and ``GlaceraREP`` both use.
ICEWIND_WAR_QUESTS = (5597, 5598, 5599, 5600)


async def icewind_pass(cmd: Command) -> None:
    """``GlaceraStory.IceWindPass``: quests 5587-5601."""
    if await cmd.is_completed_before(5601):
        return

    await frost_ruins(cmd)

    await map_item_quest(cmd, 5587, ICEWINDPASS, 5074, 5)
    await kill_quest(cmd, 5588, ICEWINDPASS, "Glacial Elemental")

    async def q5589() -> None:
        await cmd.get_map_item(5075, 5)
        await hunt_item(cmd, "Iced Mana", 9, ICEWINDPASS,
                        monster_name="Glacial Elemental")

    await _quest(cmd, 5589, q5589)
    await kill_quest(cmd, 5590, ICEWINDPASS, "Polar Golem")
    await kill_quest(cmd, 5591, ICEWINDPASS, "Frost Invader")
    await kill_quest(cmd, 5592, ICEWINDPASS, "Frostspawn Symbiote")
    await kill_quest(cmd, 5593, ICEWINDPASS, "Frost Invader")
    await kill_quest(cmd, 5594, ICEWINDPASS, "Frostspawn Horror")

    async def q5595() -> None:
        await hunt_item(cmd, "Frost Invader Slain", 5, ICEWINDPASS,
                        monster_name="Frost Invader")
        await hunt_item(cmd, "Frostspawn Troll Slain", 5, ICEWINDPASS,
                        monster_name="Frostspawn Troll")

    await _quest(cmd, 5595, q5595)

    async def q5596() -> None:
        await hunt_item(cmd, "Living Snow", 3, ICEWINDPASS,
                        monster_name="Polar Golem")
        await hunt_item(cmd, "Elemental Icicles", 3, ICEWINDPASS,
                        monster_name="Glacial Elemental")

    await _quest(cmd, 5596, q5596)

    # ``EnsureAcceptmultiple`` + four hunts + ``EnsureComplete`` on all four.
    for quest_id in ICEWIND_WAR_QUESTS:
        await cmd.ensure_accept_quest(quest_id)
    await equip_class(cmd)
    await hunt_item(cmd, "FrostSpawn Medal", 10, ICEWINDWAR,
                    monster_name="Glaceran Defender")
    await hunt_item(cmd, "Mega Frostspawn Medal", 5, ICEWINDWAR,
                    monster_name="Glaceran Defender")
    await hunt_item(cmd, "World Ender Medal", 10, ICEWINDWAR,
                    monster_name="Frost Invader")
    await hunt_item(cmd, "Mega World Ender Medal", 5, ICEWINDWAR,
                    monster_name="Frost Invader")
    for quest_id in ICEWIND_WAR_QUESTS:
        await cmd.ensure_turn_in_quest(quest_id)

    await kill_quest(cmd, 5601, ICEWINDWAR, "Soricomorpha")


async def ice_dungeon(cmd: Command) -> None:
    """``GlaceraStory.IceDungeon``: quests 7832-7841."""
    if await cmd.is_completed_before(7841):
        return

    await icewind_pass(cmd)

    async def q7832() -> None:
        await hunt_item(cmd, "Ice Symbiote Shattered", 5, ICEDUNGEON,
                        monster_name="Ice Symbiote")
        await hunt_item(cmd, "Frosted Banshee Cloth Scrap", 5, ICEDUNGEON,
                        monster_name="Frosted Banshee")
        await hunt_item(cmd, "Frozen Undead Laid to Rest", 5, ICEDUNGEON,
                        monster_name="Frozen Undead")

    await _quest(cmd, 7832, q7832)

    async def q7833() -> None:
        await hunt_item(cmd, "Spirit of Ice Captured", 5, ICEDUNGEON,
                        monster_name="Spirit of Ice")
        await hunt_item(cmd, "Ice Crystal Collected", 5, ICEDUNGEON,
                        monster_name="Ice Crystal")
        await hunt_item(cmd, "Frigid Spirit Banished", 3, ICEDUNGEON,
                        monster_name="Frigid Spirit")

    await _quest(cmd, 7833, q7833)

    async def q7834() -> None:
        await hunt_item(cmd, "Living Ice Shattered", 5, ICEDUNGEON,
                        monster_name="Living Ice")
        await hunt_item(cmd, "Crystalized Elemental Defeated", 5, ICEDUNGEON,
                        monster_name="Crystallized Elemental")
        await hunt_item(cmd, "Frozen Demon Banished", 3, ICEDUNGEON,
                        monster_name="Frozen Demon")

    await _quest(cmd, 7834, q7834)
    await kill_quest(cmd, 7835, ICEDUNGEON, "Image of Glace")
    await kill_quest(cmd, 7836, ICEDUNGEON, "Abel")
    await kill_quest(cmd, 7837, ICEDUNGEON, "Shade of Kyanos")

    async def q7838() -> None:
        await hunt_item(cmd, "Frosted Banshee Defeated", 10, ICEDUNGEON,
                        monster_name="Frosted Banshee")
        await hunt_item(cmd, "Frozen Undead Defeated", 10, ICEDUNGEON,
                        monster_name="Frozen Undead")
        await hunt_item(cmd, "Ice Symbiote Defeated", 10, ICEDUNGEON,
                        monster_name="Ice Symbiote")

    await _quest(cmd, 7838, q7838)

    async def q7839() -> None:
        await hunt_item(cmd, "Spirit of Ice Defeated", 10, ICEDUNGEON,
                        monster_name="Spirit of Ice")
        await hunt_item(cmd, "Ice Crystal Defeated", 10, ICEDUNGEON,
                        monster_name="Ice Crystal")
        await hunt_item(cmd, "Frigid Spirit Defeated", 10, ICEDUNGEON,
                        monster_name="Frigid Spirit")

    await _quest(cmd, 7839, q7839)

    async def q7840() -> None:
        await hunt_item(cmd, "Living Ice Defeated", 5, ICEDUNGEON,
                        monster_name="Living Ice")
        await hunt_item(cmd, "Crystallized Elemental Defeated", 5, ICEDUNGEON,
                        monster_name="Crystallized Elemental")
        await hunt_item(cmd, "Frozen Demon Defeated", 5, ICEDUNGEON,
                        monster_name="Frozen Demon")

    await _quest(cmd, 7840, q7840)

    async def q7841() -> None:
        await hunt_item(cmd, "Glace's Approval", 1, ICEDUNGEON,
                        monster_name="Image of Glace")
        await hunt_item(cmd, "Abel's Approval", 1, ICEDUNGEON,
                        monster_name="Abel")
        await hunt_item(cmd, "Kyanos' Approval", 1, ICEDUNGEON,
                        monster_name="Shade of Kyanos")

    await _quest(cmd, 7841, q7841)


async def do_all(cmd: Command, cryomancer: bool = False) -> None:
    """``GlaceraStory.DoAll``: every region, in the source's order.

    A Cryomancer run stops after ``FrozenTower``, exactly as the reference's own
    flag does.
    """
    await frozen_tower(cmd, cryomancer)
    if cryomancer:
        return
    await frozen_ruins(cmd)
    await glacera(cmd)
    await glacera1(cmd)
    await frozen_ruins2(cmd)
    await northstar(cmd)
    await frost_ruins(cmd)
    await icewind_pass(cmd)
    await ice_dungeon(cmd)


async def main(cmd: Command):
    await do_all(cmd)
