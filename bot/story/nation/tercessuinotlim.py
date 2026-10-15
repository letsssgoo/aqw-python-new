"""The Tercessuinotlim questline -- quests 8469-8474.

Port of ``Story/Nation/Tercessuinotlim.cs``, whose method is named ``JadziaQuests``
after the character who hands them out.  Six quests, each a list of hunts the
reference writes out by hand because they name the drop as well as the monster.

Note:
    Two of these hunts name the monster by its *map* id rather than by name
    (8473's ``id.15``, which is the same Fiend Shard cell as 7898's), and one of
    them (8474) needs ``CoreBots.KillKitsune`` for the Sake.
"""
from core.command import Command
from bot.core_bots import equip_class, kill_kitsune
from bot.core_story import kill_quest
from templates.hunt import hunt_item

#: The quest that gates the chain.
LAST_QUEST = 8474

#: ``(quest, ((item, qty, map, cell, pad, monster), ...))`` -- the reference's own
#: hunts in its own order, with ``None`` for the cell when it hunts by monster.
QUESTS = (
    (8469, (
        ("Makai Captured", 15, "Tercessuinotlim", None, "Left", "Dark Makai"),
        ("Chaorrupted Mutation", 5, "ChaosLab", None, "Left",
         "Chaorrupted Moglin"),
        ("RedDeath Mutation", 5, "RedDeath", None, "Left", "RedDeath Moglin"),
        ("Wraith Mutation", 5, "RedDeath", None, "Left", "Swamp Wraith"),
    )),
    (8470, (
        ("Revontheus Reviewed", 1, "Underworld", None, "Left", "Revontheus"),
        ("Bloodfiend Browbeaten", 20, "Underworld", None, "Left", "Bloodfiend"),
        ("Dreadfiend Disciplined", 20, "Underworld", None, "Left",
         "Dreadfiend of Nulgath"),
        ("Dilligas Demoted", 1, "Underworld", None, "Left", "Dilligas"),
        ("Klunk Kriticized", 1, "Underworld", None, "Left", "Klunk"),
    )),
    (8471, (
        ("Insanely Pink Energy", 1, "Pastelia", None, "Left",
         "Chaos Queen Beleen"),
        ("Fluffy Pink Energy", 7, "Pastelia", None, "Left", "Happy Cloud"),
        ("Cutsey Pink Energy", 8, "Pastelia", None, "Left", "Cutie Makai"),
        ("Slimy Pink Energy", 5, "SewerPink", None, "Left", "Cutie Grumbley"),
    )),
    (8472, (
        ("Dirtlicker's Dignity Decimated", 1, "Fiendshard", None, "Left",
         "Dirtlicker"),
        ("Death's Head Demolished", 1, "citadel", None, "Left", "Death's Head"),
        ("Shadowblaster Shamed", 10, "ShadowBlast", None, "Left",
         "CaesarisTheDark"),
        ("Skew Straightened Out", 1, "QuibbleHunt", None, "Left", "Skew"),
        ("Crag and Bamboozle Cowering", 1, "ShadowBlast", None, "Left",
         "Crag and Bamboozle"),
        ("Grimlord Left Groveling", 1, "ShadowBlast", None, "Left",
         "Grimlord Boss"),
        ("Void Warrior Vanquished", 10, "tercessuinotlim", None, "Left",
         "Void Monk"),
    )),
)

#: 8473's three drops; the middle one names its monster by map id.
QUEST_8473 = (
    (8473, (
        ("Dirtlicker's Shard Shaving", 3, "fiendshard", "r8", "Left",
         "Fiend Shard"),
        ("Nulgath's Shard Shaving", 3, "fiendshard", "r9", "Left", "id.15"),
        ("Roguefiend Crystal Shaving", 5, "QuibbleHunt", None, "Left",
         "RogueFiend"),
    )),
)

#: 8474's Sake hunt, which is the Kitsune fight, and then its two plain ones.
SAKE = ("Private Reserve Sake", 1)
QUEST_8474_HUNTS = (
    ("101 Proof Blade Oil", 1, "hachiko", "Dai Tengu"),
    ("The Tale of Taro", 1, "Tercessuinotlim", "Taro Blademaster"),
)


async def main(cmd: Command):
    if await cmd.is_completed_before(LAST_QUEST):
        return

    for quest_id, hunts in QUESTS + QUEST_8473:
        if await cmd.is_completed_before(quest_id):
            continue
        await cmd.ensure_accept_quest(quest_id)
        for item, qty, map_name, cell, pad, monster in hunts:
            await hunt_item(cmd, item, qty, map_name, cell=cell, pad=pad,
                            monster_name=monster, is_temp=False)
        await cmd.ensure_turn_in_quest(quest_id)

    if await cmd.is_completed_before(LAST_QUEST):
        return
    await cmd.ensure_accept_quest(LAST_QUEST)
    await hunt_item(cmd, QUEST_8474_HUNTS[0][0], QUEST_8474_HUNTS[0][1],
                    QUEST_8474_HUNTS[0][2],
                    monster_name=QUEST_8474_HUNTS[0][3], is_temp=False)
    await kill_kitsune(cmd, SAKE[0], SAKE[1], is_temp=True)
    await equip_class(cmd, solo=True)
    await hunt_item(cmd, QUEST_8474_HUNTS[1][0], QUEST_8474_HUNTS[1][1],
                    QUEST_8474_HUNTS[1][2],
                    monster_name=QUEST_8474_HUNTS[1][3], is_temp=False)
    await cmd.ensure_turn_in_quest(LAST_QUEST)
