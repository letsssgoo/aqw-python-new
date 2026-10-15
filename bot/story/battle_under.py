"""The Battle Under story -- battleundera through battleundere.

Port of ``Story/BattleUnder.cs``.

Five chains, each gated on the last quest of the one before it: 374-377 in
``/battleundera``, 689-692 and 935 in ``/battleunderb``, 936-939 in
``/battleunderc``, the member-only 2211-2215 in ``/battleunderd``, and 5927-5928
in ``/battleundere``.

Note:
    ``/battleunderd``'s monsters spawn randomly per room, which is why that
    chain kills them by cell rather than by hunting them.
    ``Bot.Quests.UpdateQuest(935)`` in ``Understone`` is a client-side quest-slot
    write with no counterpart here; the quest is accepted directly instead.
"""
from core.command import Command
from bot.core_bots import equip_class
from bot.core_story import kill_quest, map_item_quest
from templates.hunt import hunt_item

#: The last quest of each chain, which decides whether that chain runs.
QUEST_A_LAST = 377
QUEST_B_LAST = 935
QUEST_C_LAST = 939
QUEST_D_LAST = 2215
QUEST_E_LAST = 5928

#: The three souls quest 939 wants, as ``(item, map, monster)``.
SOULS = (
    ("Bone Terror Soul", "battleundera", "Bone Terror"),
    ("Undead Champion Soul", "battleunderb", "Undead Champion"),
    ("Jellyfish Soul", "battleunderc", "Crystalized Jellyfish"),
)

#: ``/battleunderd``'s four cell-bound steps, as ``(quest, cell, pad, monster,
#: item, qty)``.
BATTLE_UNDER_D_STEPS = (
    (2211, "Enter", "Spawn", "Shivering Bones", "Shivering Bone", 10),
    (2212, "r2", "Left", "Icy Banshee", "Banshee Slain", 7),
    (2213, "r5", "Left", "Skeletal Warrior", "Icy Pickaxe Found", 1),
    (2214, "r5", "Left", "Glacial Horror", "Glacial Horror Slain", 1),
)

#: The Battle Pickaxe the D chain picks up, and the map item the 2212 step needs.
BATTLE_PICKAXE = "Battle Pickaxe"
D_2212_MAP_ITEM = (2212, "battleunderd", 1286, 8)
D_2214_MAP_ITEM = (1287, 4)
D_2215_MAP_ITEM = (2215, "battleunderd", 1288, 1)

#: ``Understone``'s quest and what it needs.
UNDERSTONE = "Understone"
UNDERSTONE_QUEST = 7289
UNDERSTONE_SHARD = ("Fluorite Shard", 10)


async def battle_under_a(cmd: Command) -> None:
    """Quests 374-377 in ``/battleundera``."""
    if await cmd.is_completed_before(QUEST_A_LAST):
        return

    await equip_class(cmd)
    await kill_quest(cmd, 374, "battleundera", "Skeletal Warrior")

    if not await cmd.is_completed_before(375):
        await cmd.ensure_accept_quest(375)
        await hunt_item(cmd, "Skeletal Claymore", 6, "battleundera",
                        monster_name="Skeletal Warrior", is_temp=False)
        await hunt_item(cmd, "Bony Chestplate", 3, "battleundera",
                        monster_name="Skeletal Warrior", is_temp=False)
        await cmd.ensure_turn_in_quest(375)

    await equip_class(cmd, solo=True)
    await kill_quest(cmd, 376, "battleundera", "Bone Terror")
    await equip_class(cmd)
    await kill_quest(cmd, 377, "battleundera", "Skeletal Warrior")


async def battle_under_b(cmd: Command) -> None:
    """Quests 689-692 and 935 in ``/battleunderb``."""
    if await cmd.is_completed_before(QUEST_B_LAST):
        return

    await battle_under_a(cmd)
    await equip_class(cmd)
    await kill_quest(cmd, 689, "battleunderb", "Skeleton Warrior")
    await kill_quest(cmd, 690, "battleunderb", "Skeleton Warrior")
    await kill_quest(cmd, 691, "battleunderb", "Skeleton Warrior")
    await equip_class(cmd, solo=True)
    await kill_quest(cmd, 692, "battleunderb", "Undead Champion")
    await map_item_quest(cmd, QUEST_B_LAST, "battleunderb", 253)


async def battle_under_c(cmd: Command) -> None:
    """Quests 936-939 in ``/battleunderc``."""
    if await cmd.is_completed_before(QUEST_C_LAST):
        return

    await battle_under_b(cmd)
    await kill_quest(cmd, 936, "battleunderc", "Blue Crystalized Undead")
    await kill_quest(cmd, 937, "battleunderc", "Blue Crystalized Undead")
    await kill_quest(cmd, 938, "battleunderc", "Crystalized Jellyfish")

    if not await cmd.is_completed_before(939):
        await cmd.ensure_accept_quest(939)
        for item, map_name, monster in SOULS:
            await hunt_item(cmd, item, 1, map_name, monster_name=monster,
                            is_temp=False)
        await cmd.ensure_turn_in_quest(939)


async def battle_under_d(cmd: Command) -> None:
    """Quests 2211-2215 in ``/battleunderd`` -- members only."""
    if not cmd.get_player().is_member or await cmd.is_completed_before(
            QUEST_D_LAST):
        return

    cmd.add_drop(BATTLE_PICKAXE)
    await battle_under_c(cmd)

    for quest_id, cell, pad, monster, item, qty in BATTLE_UNDER_D_STEPS:
        if await cmd.is_completed_before(quest_id):
            continue
        await cmd.ensure_accept_quest(quest_id)
        await hunt_item(cmd, item, qty, "battleunderd", cell=cell, pad=pad,
                        monster_name=monster, is_temp=False)
        if quest_id == 2212:
            await map_item_quest(cmd, *D_2212_MAP_ITEM)
        elif quest_id == 2214:
            await cmd.get_map_item(D_2214_MAP_ITEM[0], D_2214_MAP_ITEM[1])
            await cmd.ensure_turn_in_quest(quest_id)
        else:
            await cmd.ensure_turn_in_quest(quest_id)

    await map_item_quest(cmd, *D_2215_MAP_ITEM)


async def battle_under_e(cmd: Command) -> None:
    """Quests 5927-5928 in ``/battleundere``."""
    if await cmd.is_completed_before(QUEST_E_LAST):
        return

    await map_item_quest(cmd, 5927, "battleundere", 5362)
    await kill_quest(cmd, 5927, "battleundere", "Lava Guard")
    await kill_quest(cmd, QUEST_E_LAST, "battleundere", "Hot Mama")


async def battle_under_all(cmd: Command) -> None:
    """The whole story, in order."""
    await battle_under_a(cmd)
    await battle_under_b(cmd)
    await battle_under_c(cmd)
    await battle_under_d(cmd)
    await battle_under_e(cmd)


async def understone(cmd: Command) -> None:
    """Quest 7289, for the Understone."""
    if await cmd.has_item(UNDERSTONE):
        return

    cmd.add_drop(UNDERSTONE)
    await cmd.ensure_accept_quest(UNDERSTONE_QUEST)
    await hunt_item(cmd, UNDERSTONE_SHARD[0], UNDERSTONE_SHARD[1],
                    "battleunderc", cell="Enter", pad="Spawn", monster_name="*",
                    is_temp=False)
    await cmd.ensure_turn_in_quest(UNDERSTONE_QUEST)


async def main(cmd: Command):
    await battle_under_all(cmd)
