"""``GlaceraStory`` -- the frozen north, region by region.

Port of ``Story/Glacera.cs``.  ``FrozenTower`` (quests 3907-3937) is ported: it is
the whole ``Cryomancer`` path, since the reference's ``DoAll(Cryomancer: true)``
returns right after it.  The regions after it -- FrozenRuins, Glacera, Glacera1,
FrozenRuins2, Northstar, FrostRuins, IceWindPass, IceDungeon -- are **not** ported
yet; ``do_all`` names them instead of skipping them quietly.
"""
from bot.core_bots import chain_complete
from bot.core_story import CustomError, kill_quest, map_item_quest, quest_progression
from core.command import Command
from templates.hunt import hunt_item

FROZEN_TOWER = "frozentower"
FROZEN_TOWER_LAST = 3937


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
    if await cmd.is_completed_before(FROZEN_TOWER_LAST):
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


async def do_all(cmd: Command, cryomancer: bool = False) -> None:
    """``GlaceraStory.DoAll``: every region, in the source's order.

    Only ``FrozenTower`` is ported; the rest are reported by name.  A Cryomancer
    run stops after the tower, exactly as the reference's own flag does.
    """
    await frozen_tower(cmd, cryomancer)
    if cryomancer:
        return
    cmd.bot.log("[glacera] the regions after FrozenTower (FrozenRuins, Glacera, "
                "Glacera1, FrozenRuins2, Northstar, FrostRuins, IceWindPass, "
                "IceDungeon) are not ported yet.")


async def main(cmd: Command):
    await do_all(cmd)
