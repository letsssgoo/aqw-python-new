"""Willpower Extraction -- Unidentified 34 through quest 5258.

Port of ``AFDL/WillpowerExtraction.cs``.

Eight steps per pass: two shop purchases, up to three reagent top-ups, a sub-quest
for the Facebreakers (quest 3046), and three Nation farms -- then the turn-in.

Note:
    The reference puts a shop *item id* (18768) in its drop list and checks it by
    id; the name and the id are both used here, each where it means the right
    thing.
"""
from core.command import Command
from bot.core_bots import buy_item
from bot.nation.core_nation import (approval_and_favor, equip_class,
                                    farm_dark_crystal_shard,
                                    farm_diamond_of_nulgath,
                                    farm_tainted_gem, farm_totem_of_nulgath,
                                    farm_uni13_quest, supplies, uni)
from templates.hunt import hunt_item

#: Unidentified 34 to farm, and the quest that hands them over.
QUEST_ID = 5258
QUANT = 300
REWARD = "Unidentified 34"

#: The Facebreakers sub-quest, its item id, and what that quest needs.
FACE_QUEST = 3046
FACE_ID = 18768
FACE_NAME = "Facebreakers of Nulgath"
FACE_SHARDS = 5
FACE_TAINTED = 5
FACE_DIAMONDS = 1

#: Runs to buy every pass, as ``(shop_id, name, qty, map)`` -- each shop only
#: loads in its own map.
RUNS = (
    (89, "Shadow Lich", 1, "shadowfall"),
    (214, "Mystic Tribal Sword", 1, "arcangrove"),
)

#: Reagents topped up from the Tercessuinotlim shop when short.
REAGENTS = (
    ("Necrot", 10),
    ("Chaoroot", 10),
    ("Doomatter", 10),
)

#: What the farm picks up along the way.
DROPS = (REWARD, uni(19), "Necrot", "Chaoroot", "Doomatter", FACE_NAME,
         "Mystic Tribal Sword", "Golden Shadow Breaker", "Shadow Terror Axe")


async def main(cmd: Command):
    if await cmd.has_item(REWARD, QUANT):
        return

    cmd.add_drop(list(DROPS))
    cmd.farming_logger(REWARD, QUANT)

    while cmd.is_still_connected() and not await cmd.has_item(REWARD, QUANT):
        await cmd.ensure_accept_quest(QUEST_ID)

        for shop_id, name, qty, map_name in RUNS:
            await buy_item(cmd, shop_id, name, qty, map_name=map_name)

        if not await cmd.has_item(uni(19)):
            if cmd.get_player().is_member:
                await buy_item(cmd, 1951, uni(19),
                                map_name="tercessuinotlim")
            else:
                await supplies(cmd, uni(19))

        for name, qty in REAGENTS:
            if not await cmd.has_item(name, 5):
                await buy_item(cmd, 1951, name, qty,
                                map_name="tercessuinotlim")

        if not await cmd.has_item_id(FACE_ID):
            await _facebreakers(cmd)

        await approval_and_favor(cmd, 50, 0)
        await farm_totem_of_nulgath(cmd, 1)
        await cmd.ensure_turn_in_quest(QUEST_ID)


async def _facebreakers(cmd: Command) -> None:
    """Quest 3046, which hands over the Facebreakers of Nulgath."""
    await cmd.ensure_accept_quest(FACE_QUEST)
    await farm_uni13_quest(cmd, 1)
    await equip_class(cmd, solo=True)
    await hunt_item(cmd, "Golden Shadow Breaker", 1, "citadel",
                    monster_name="Grand Inquisitor", is_temp=False)
    await hunt_item(cmd, "Shadow Terror Axe", 1, "battleundera",
                    monster_name="Bone Terror", is_temp=False)
    await equip_class(cmd)
    await farm_dark_crystal_shard(cmd, FACE_SHARDS)
    await farm_tainted_gem(cmd, FACE_TAINTED)
    await farm_diamond_of_nulgath(cmd, FACE_DIAMONDS)
    await cmd.ensure_turn_in_quest(FACE_QUEST, FACE_ID)
