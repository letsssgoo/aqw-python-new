"""``CoreToD`` -- Throne of Darkness, the ShatterGlass Maze and Tower of Mirrors.

Port of ``Story/ThroneofDarkness/CoreToD.cs``, only the two regions the Scarlet
Sorceress class needs.  The rest of that file (``CastleofBones``, ``DeathPit``,
``ShiftingPyramid``, ``AntiqueShop``, ...) is not ported.

The map-id hunts -- ``Core.HuntMonsterMapID(map, id, itemName)`` -- resolve the
item **id** from the accepted quest's own payload and let ``hunt_item_by_id``
walk to the monster, which is how the reference's helper hunts.
"""
from bot.core_bots import equip_class
from bot.core_story import (CustomError, item_id_by_name, kill_quest,
                            map_item_quest, quest_progression)
from core.command import Command
from templates.hunt import hunt_item, hunt_item_by_id

HEDGEMAZE = "hedgemaze"
TOWER = "towerofmirrors"

#: ``Bot.Wait.ForCellChange("Cut4")`` then back to ``Enter``, bounded: a cutscene
#: cell this engine never reports must not hang the run.
CUTSCENE_CELL = "Cut4"
CUTSCENE_TRIES = 40
ENTER_TRIES = 20


async def _quest(cmd: Command, quest_id: int, body) -> None:
    """``if (!Story.QuestProgression(q)) { accept; body; complete; }``."""
    if await quest_progression(cmd, quest_id):
        return
    if await cmd.ensure_accept_quest(quest_id) is False:
        raise CustomError(f"quest {quest_id} could not be accepted")
    await body()
    if await cmd.ensure_turn_in_quest(quest_id) is False:
        raise CustomError(f"quest {quest_id} could not be turned in")


async def _hunt_map_id(cmd: Command, quest_id: int, monster_map_id: int,
                       item_name: str) -> None:
    """``Core.HuntMonsterMapID``: kill that monster until the named item drops."""
    item_id = item_id_by_name(cmd, quest_id, item_name)
    if item_id is None:
        cmd.bot.log(f"[tod] quest {quest_id} names no item {item_name!r}; "
                    f"monster {monster_map_id} is not hunted.")
        return
    await hunt_item_by_id(cmd, item_id, 1, TOWER, monster_map_id=monster_map_id,
                          hunt=True)


async def _cutscene_to_enter(cmd: Command) -> None:
    """The reference's ``Cut4`` cell wait, then jumps back to ``Enter``."""
    for _ in range(CUTSCENE_TRIES):
        if str(getattr(cmd.bot.player, "CELL", "")).lower() == CUTSCENE_CELL.lower():
            break
        await cmd.sleep(500)
    else:
        cmd.bot.log(f"[tod] the {CUTSCENE_CELL} cutscene cell never showed up; "
                    f"carrying on.")
    for _ in range(ENTER_TRIES):
        if str(getattr(cmd.bot.player, "CELL", "")).lower() == "enter":
            return
        await cmd.jump_cell("Enter")
        await cmd.sleep(500)


async def shatter_glass_maze(cmd: Command) -> None:
    """``CoreToD.ShatterGlassMaze``: quests 5298-5313 in /hedgemaze."""
    if await cmd.is_completed_before(5313):
        return

    async def q5298() -> None:
        await cmd.get_map_item(4678, 1)
        await hunt_item(cmd, "Knight's Reflection Dispersed", 1, HEDGEMAZE,
                        monster_name="Knight's Reflection")

    await _quest(cmd, 5298, q5298)
    await equip_class(cmd, solo=True)

    async def q5299() -> None:
        await hunt_item(cmd, "Mirror Shard Slain", 4, HEDGEMAZE,
                        monster_name="Mirrored Shard")
        await _hunt_map_id(cmd, 5299, 48, "Hedge Goblin Slain")
        await _hunt_map_id(cmd, 5299, 20, "Minotaur Slain")
        await map_item_quest(cmd, 5299, HEDGEMAZE, 4679)

    await _quest(cmd, 5299, q5299)
    await kill_quest(cmd, 5300, HEDGEMAZE, "Knight's Reflection")
    await map_item_quest(cmd, 5301, HEDGEMAZE, 4680)
    await kill_quest(cmd, 5302, HEDGEMAZE, "Hedge Goblin")
    await map_item_quest(cmd, 5303, HEDGEMAZE, 4681, 12)
    await kill_quest(cmd, 5304, HEDGEMAZE, "Mirrored Shard")
    await map_item_quest(cmd, 5305, HEDGEMAZE, 4682)
    await equip_class(cmd, solo=True)
    await kill_quest(cmd, 5306, HEDGEMAZE, "Minotaur Prime")
    await map_item_quest(cmd, 5307, HEDGEMAZE, 4683)
    await map_item_quest(cmd, 5308, HEDGEMAZE, 4684)
    await map_item_quest(cmd, 5309, HEDGEMAZE, 4685, 5)

    async def q5310() -> None:
        await hunt_item(cmd, "Maze Monster Killed", 8, HEDGEMAZE, cell="r21",
                        pad="Right", monster_name="*")

    await _quest(cmd, 5310, q5310)
    await map_item_quest(cmd, 5311, HEDGEMAZE, 4686)
    await equip_class(cmd, solo=True)
    await kill_quest(cmd, 5312, HEDGEMAZE, "Shattered Knight")
    await kill_quest(cmd, 5313, HEDGEMAZE, "Resurrected Minotaur")


async def tower_of_mirrors(cmd: Command) -> None:
    """``CoreToD.TowerofMirrors``: quests 5314-5332 in /towerofmirrors."""
    if await cmd.is_completed_before(5332):
        return

    await shatter_glass_maze(cmd)
    cmd.bot.log("Scarletta - The Sorceress: Tower of Mirrors")

    async def q5314() -> None:
        await hunt_item(cmd, "Glass Powder", 8, TOWER, monster_name="Glassgoyle")
        await hunt_item(cmd, "Reflective Venom", 4, TOWER,
                        monster_name="Glass Serpent")

    await _quest(cmd, 5314, q5314)

    async def q5315() -> None:
        await cmd.get_map_item(4691, 1)
        await cmd.get_map_item(4692, 1)
        await hunt_item(cmd, "Mirror Key", 1, TOWER,
                        monster_name="Silver Elemental")

    await _quest(cmd, 5315, q5315)

    async def q5316() -> None:
        await hunt_item(cmd, "Mosh Past the Phans", 8, TOWER,
                        monster_name="Phans")
        await hunt_item(cmd, "Backstage Pass", 1, TOWER,
                        monster_name="Phans")

    await _quest(cmd, 5316, q5316)

    async def q5317() -> None:
        await equip_class(cmd, solo=True)
        await _hunt_map_id(cmd, 5317, 36, "Lathannos the Reversed Defeated")

    await _quest(cmd, 5317, q5317)

    async def q5318() -> None:
        await cmd.get_map_item(4687, 1)
        await cmd.get_map_item(4693, 1)
        await hunt_item(cmd, "Andres' Mirror Key", 1, TOWER,
                        monster_name="Silver Elemental")

    await _quest(cmd, 5318, q5318)

    async def q5319() -> None:
        await hunt_item(cmd, "Runway Wraith Defeated", 6, TOWER,
                        monster_name="Runway Wraith")
        await hunt_item(cmd, "Avant-Garde Footwear", 1, TOWER,
                        monster_name="Runway Wraith")
        await hunt_item(cmd, "Retro Wig", 1, TOWER,
                        monster_name="Runway Wraith")
        await hunt_item(cmd, "Someone's Wearable Art Project", 1, TOWER,
                        monster_name="Runway Wraith")

    await _quest(cmd, 5319, q5319)

    async def q5320() -> None:
        await equip_class(cmd, solo=True)
        await _hunt_map_id(cmd, 5320, 40, "Lukrisio the Buffed Defeated")

    await _quest(cmd, 5320, q5320)

    async def q5321() -> None:
        await cmd.get_map_item(4688, 1)
        await cmd.get_map_item(4694, 1)
        await hunt_item(cmd, "Gisele's Mirror Key", 1, TOWER,
                        monster_name="Silver Elemental")

    await _quest(cmd, 5321, q5321)

    async def q5322() -> None:
        await hunt_item(cmd, "Pageant Mom Defeated", 8, TOWER,
                        monster_name="Pageant Mom")
        await hunt_item(cmd, "Pageant Sash", 1, TOWER,
                        monster_name="Pageant Mom")

    await _quest(cmd, 5322, q5322)

    async def q5323() -> None:
        await equip_class(cmd, solo=True)
        await _hunt_map_id(cmd, 5323, 45, "Mendeskar the Smudged Defeated")

    await _quest(cmd, 5323, q5323)

    async def q5324() -> None:
        await cmd.get_map_item(4689, 1)
        await cmd.get_map_item(4695, 1)
        await hunt_item(cmd, "Emilia's Mirror Key", 1, TOWER,
                        monster_name="Silver Elemental")

    await _quest(cmd, 5324, q5324)

    async def q5325() -> None:
        await hunt_item(cmd, "Stage Tech Defeated", 9, TOWER,
                        monster_name="Stage Tech")
        await hunt_item(cmd, "Rope Ladder", 1, TOWER,
                        monster_name="Stage Tech")

    await _quest(cmd, 5325, q5325)

    async def q5326() -> None:
        await equip_class(cmd, solo=True)
        await _hunt_map_id(cmd, 5326, 49, "Atticus the Warped Defeated")

    await _quest(cmd, 5326, q5326)

    async def q5327() -> None:
        await cmd.get_map_item(4690, 1)
        await cmd.get_map_item(4696, 1)
        await hunt_item(cmd, "Dora's Mirror Key", 1, TOWER,
                        monster_name="Silver Elemental")

    await _quest(cmd, 5327, q5327)

    async def q5328() -> None:
        await hunt_item(cmd, "Sasquatches Defeated", 10, TOWER,
                        monster_name="Sasquatch")
        await hunt_item(cmd, "Tracking Tag", 5, TOWER,
                        monster_name="Sasquatch")

    await _quest(cmd, 5328, q5328)

    async def q5329() -> None:
        await equip_class(cmd, solo=True)
        await _hunt_map_id(cmd, 5329, 52, "Leofire the Shattered Defeated")

    await _quest(cmd, 5329, q5329)

    await kill_quest(cmd, 5330, TOWER, "Fervent Suitor")
    await map_item_quest(cmd, 5331, TOWER, 4697)

    await _cutscene_to_enter(cmd)

    async def q5332() -> None:
        cmd.add_drop("Blood Sorceress")
        await equip_class(cmd, solo=True)
        await _hunt_map_id(cmd, 5332, 32, "Defeat the Groglurk")

    await _quest(cmd, 5332, q5332)


async def main(cmd: Command):
    await tower_of_mirrors(cmd)
