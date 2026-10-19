"""``Core13LoC`` -- the thirteen Lords of Chaos, only Escherion so far.

Port of ``Story/LordsofChaos/Core13LoC.cs``.  The forge enhancement unlocks need
``Escherion()``, so that is the method ported; the rest of the file waits for a
caller.  Note that this is *not* ``CoreNation.KillEscherion`` -- same target,
different class, different job: this one is the whole /mobius story.

``Story.PreLoad`` has no counterpart here; the guards do its work.
"""
from typing import Sequence, Tuple, Union

from bot.core_story import item_id_by_name, kill_quest, map_item_quest
from core.command import Command
from bot.nation.core_nation import kill_escherion
from templates.hunt import hunt_item, hunt_item_by_id

ESCHERION_LAST = 272

#: ``(quest, map, map item id or ids, how many, monster)``, in the source's order.
ESCHERION_STEPS: Tuple[Tuple[int, str, Union[int, Sequence[int], None], int,
                             Union[str, None]], ...] = (
    (245, "mobius", None, 0, "Chaos Sp-Eye"),
    (246, "mobius", 42, 5, None),
    (247, "mobius", None, 0, "Fire Imp"),
    (260, "mobius", 44, 1, None),
    (248, "mobius", None, 0, "Cyclops Raider"),
    (249, "mobius", None, 0, "Slugfit"),
    (250, "faerie", None, 0, "Chainsaw Sneevil"),
    (251, "faerie", 43, 7, None),
    (252, "faerie", None, 0, "Chainsaw Sneevil"),
    (255, "faerie", None, 0, "Cyclops Warlord"),
    (256, "faerie", None, 0, "Aracara"),
    (257, "cornelis", None, 0, "Gargoyle"),
    (261, "cornelis", 45, 1, None),
    (258, "cornelis", None, 0, "Gargoyle"),
    (262, "cornelis", 46, 1, None),
    (259, "cornelis", None, 0, "Stone Golem"),
    (263, "cornelis", 47, 1, None),
    (266, "mobius", 48, 1, None),
    (267, "mobius", 49, 1, None),
    (264, "mobius", None, 0, "Cyclops Raider"),
    (268, "relativity", None, 0, "Cyclops Raider"),
    (269, "relativity", None, 0, "Fire Imp"),
    (270, "relativity", None, 0, "Head Gargoyle"),
    (271, "hydra", (50, 51, 52), 1, None),
)


async def escherion(cmd: Command) -> None:
    """``Core13LoC.Escherion``: quests 245-272 across five maps.

    Two of the source's steps are written out by hand because it guards them with
    ``QuestProgression`` and farms items itself: 265's Cardboard Box, and 272's
    Escherion kill.
    """
    if await cmd.is_completed_before(ESCHERION_LAST):
        return

    for quest_id, map_name, map_items, qty, monster in ESCHERION_STEPS:
        if map_items is not None:
            await map_item_quest(cmd, quest_id, map_name, map_items, qty)
        if monster is not None:
            await kill_quest(cmd, quest_id, map_name, monster)

    if not await cmd.is_completed_before(265):
        await cmd.ensure_accept_quest(265)
        await hunt_item(cmd, "Cardboard Box", 4, "faerie",
                        monster_name="Chainsaw Sneevil")
        await cmd.ensure_turn_in_quest(265)

    if not await cmd.is_completed_before(ESCHERION_LAST):
        await cmd.ensure_accept_quest(ESCHERION_LAST)
        await kill_escherion(cmd, "Defeated Escherion", is_temp=True)
        await cmd.ensure_turn_in_quest(ESCHERION_LAST)


KITSUNE_LAST = 488

#: Quest 470's five monsters, by the map id the source names: ``(map id, item,
#: how many)``.  The item is named there, and this engine farms by id, so the id
#: comes from the quest's own payload -- see ``core_story.item_id_by_name``.
JUNKYARD_BY_ID = ((1, "Wild Kara-Kasa", 5),
                  (4, "Wild Bura-Bura", 4),
                  (3, "Wild Biwa-Bokuboku", 3),
                  (6, "Wild Koto-Furunushi", 2),
                  (2, "Wild Bakezouri", 1))

#: Quest 474's three Kappa Ninja drops plus the map item, in the source's order.
KAPPA_ITEMS = (("Dried Nori Leaf", 6),
               ("Sumeshi Bundle", 3),
               ("Fresh Cucumber", 1))
KAPPA_MAP_ITEM = 92


async def kitsune(cmd: Command) -> None:
    """``Core13LoC.Kitsune``: quests 380-488 across seven maps.

    The seven quests the source writes out by hand (380, 381, 402, 403, 405, 470,
    474) keep their own blocks, in place; the rest go through the same two
    helpers ``escherion`` uses.
    """
    if await cmd.is_completed_before(KITSUNE_LAST):
        return

    # Turtle Power 380
    if not await cmd.is_completed_before(380):
        await map_item_quest(cmd, 380, "yokaiboat", 64, 1)
        await cmd.ensure_accept_quest(380)
        await hunt_item(cmd, "Kappa Ninja Slain", 7, "yokaiboat",
                        monster_name="Kappa Ninja")
        await cmd.ensure_turn_in_quest(380)

    # Setting Sail to Yokai 381
    if not await cmd.is_completed_before(381):
        await cmd.ensure_accept_quest(381)
        await hunt_item(cmd, "Sail Permit", 1, "yokaiboat", cell="r4",
                        pad="Spawn", monster_name="*")
        await cmd.ensure_turn_in_quest(381)

    await kill_quest(cmd, 382, "dragonkoi", "Ryoku")

    # Dog Days 402
    if not await cmd.is_completed_before(402):
        await cmd.ensure_accept_quest(402)
        await hunt_item(cmd, "Samurai Questioned", 5, "hachiko",
                        monster_name="Samurai Nopperabo")
        await hunt_item(cmd, "Ninja Questioned", 5, "hachiko",
                        monster_name="Ninja Nopperabo")
        await cmd.ensure_turn_in_quest(402)

    # Faceless Threat 403
    if not await cmd.is_completed_before(403):
        await cmd.ensure_accept_quest(403)
        await hunt_item(cmd, "Note from DT", 1, "hachiko", cell="Ox",
                        pad="Center", monster_name="Samurai Nopperabo")
        await cmd.ensure_turn_in_quest(403)

    # Zodiac Puzzle Key 405
    if not await cmd.is_completed_before(405):
        await cmd.ensure_accept_quest(405)
        for cell, monster, piece in (
                ("Tiger", "Samurai Nopperabo", "Rat-Ox-Tiger Piece"),
                ("Snake", "Ninja Nopperabo", "Rabbit-Dragon-Snake piece"),
                ("Horse", "Samurai Nopperabo", "Horse-Sheep-Monkey piece"),
                ("Pig", "Ninja Nopperabo", "Rooster-Dog-Pig Piece")):
            await hunt_item(cmd, piece, 1, "hachiko", cell=cell, pad="Center",
                            monster_name=monster)
        await cmd.ensure_turn_in_quest(405)

    await kill_quest(cmd, 406, "hachiko", "Dai Tengu")
    await map_item_quest(cmd, 466, "bamboo", 90, 1)
    await kill_quest(cmd, 467, "bamboo", ["Tanuki", "Tanuki"])
    await kill_quest(cmd, 468, "bamboo", "SoulTaker")
    await map_item_quest(cmd, 469, "junkyard", 91, 1)

    # Reduce, Respawn, Recycle 470 -- five monsters, each by its own map id
    if not await cmd.is_completed_before(470):
        await cmd.ensure_accept_quest(470)
        for monster_map_id, item, qty in JUNKYARD_BY_ID:
            item_id = item_id_by_name(cmd, 470, item)
            if item_id is None:
                cmd.bot.log(f"[story] quest 470 does not name {item!r}; the "
                            f"/junkyard pass stops here.")
                return
            await hunt_item_by_id(cmd, item_id, qty, "junkyard",
                                  monster_map_id=monster_map_id)
        await cmd.ensure_turn_in_quest(470)

    await kill_quest(cmd, 471, "junkyard", "Onibaba")
    await kill_quest(cmd, 473, "yokairiver",
                     ["Funa-Yurei", "Funa-Yurei", "Funa-Yurei"])

    # Kappa Cuisine 474
    if not await cmd.is_completed_before(474):
        await cmd.ensure_accept_quest(474)
        for item, qty in KAPPA_ITEMS:
            await hunt_item(cmd, item, qty, "yokairiver", cell="r4", pad="Left",
                            monster_name="Kappa Ninja")
        if cmd.is_not_in_map("yokairiver"):
            await cmd.join_map("yokairiver")
        await cmd.get_map_item(KAPPA_MAP_ITEM)
        await cmd.ensure_turn_in_quest(474)

    await kill_quest(cmd, 476, "yokairiver", "Nure Onna")
    await kill_quest(cmd, 477, "yokaigrave", "Skello Kitty")
    await kill_quest(cmd, 478, "yokaigrave",
                     ["Ninja Nopperabo", "Samurai Nopperabo"])
    await kill_quest(cmd, 479, "yokaigrave", "Neko Mata")
    await kill_quest(cmd, 481, "odokuro", "O-dokuro")
    await kill_quest(cmd, 484, "yokaiwar", "O-Dokuro's Head")
    await kill_quest(cmd, 488, "kitsune", "kitsune")


LIONFANG_LAST = 2814

#: Quest 2615's own block: the map item, then the two drops it wants.
LIONFANG_2615 = (("Scrap Of Cloth", "Restless Undead", 3),
                 ("Gas Bladder", "Tomb Spider", 3))
LIONFANG_2615_MAP_ITEM = 1616
#: Quest 2668's two drops.
LIONFANG_2668 = (("Chaonslaught Shield", "Chaonslaught Warrior", 2),
                 ("Chaonslaught Sword", "Chaonslaught Cavalry", 3))
#: Quest 2731's three drops, one per monster.
LIONFANG_2731 = (("Primarch Mace", "Sundered Darkblood", 1),
                 ("Primarch Trident", "Rotting Darkblood", 1),
                 ("Primarch Spear", "Ghastly Darkblood", 1))
#: Quest 2740: the map item and the boss drop.
LIONFANG_2740_MAP_ITEM = 1695
LIONFANG_2740 = ("Vestis Defeated", "Wrathful Vestis")
#: Quest 2805/2806 in /stormtemple: the map item, then one kill in r1.
LIONFANG_2805_MAP_ITEM = 1729
LIONFANG_2805_QTY = 4
LIONFANG_2806 = ("Lightning Boots", "r1", "Left")


async def lionfang(cmd: Command) -> None:
    """``Core13LoC.Lionfang``: quests 2612-2814 across six maps.

    The seven quests the source writes out by hand (2615, 2668, 2731, 2740, 2798
    together with its 2797, 2805, 2806) keep their own blocks, in place; the rest
    go through the same two helpers as ``escherion``.

    This is also the story the ``UpdateQuest(2621/2804/2814)`` calls stand in
    for: a socket client cannot write the client-side quest value, so the way
    through those gates is to work the chain that owns them.
    """
    if await cmd.is_completed_before(LIONFANG_LAST):
        return

    # blackhorn
    await kill_quest(cmd, 2612, "blackhorn", "Restless Undead")
    await map_item_quest(cmd, 2613, "blackhorn", 1615, 10)
    await kill_quest(cmd, 2614, "blackhorn", "Tomb Spider")

    # Fire Is The Thing 2615
    if not await cmd.is_completed_before(2615):
        await cmd.ensure_accept_quest(2615)
        await cmd.join_map("blackhorn")
        await cmd.get_map_item(LIONFANG_2615_MAP_ITEM)
        for item, monster, qty in LIONFANG_2615:
            await hunt_item(cmd, item, qty, "blackhorn", monster_name=monster)
        await cmd.ensure_turn_in_quest(2615)

    await map_item_quest(cmd, 2616, "blackhorn", 1617, 1)
    await kill_quest(cmd, 2617, "blackhorn", "Bonefeeder Spider")
    await map_item_quest(cmd, 2618, "blackhorn", 1618, 1)
    await kill_quest(cmd, 2619, "blackhorn", "Tomb Spider")
    await kill_quest(cmd, 2620, "blackhorn", "Restless Undead")
    await map_item_quest(cmd, 2621, "blackhorn", 1619, 1)

    # onslaughttower
    await map_item_quest(cmd, 2622, "onslaughttower", (1620, 1621, 1622, 1623), 1)
    await kill_quest(cmd, 2623, "onslaughttower", "Golden Caster")
    await kill_quest(cmd, 2624, "onslaughttower", "Golden Caster")
    await map_item_quest(cmd, 2625, "onslaughttower", 1624, 8)
    await map_item_quest(cmd, 2626, "onslaughttower", 1625, 1)
    await map_item_quest(cmd, 2627, "onslaughttower", 1626, 4)
    await kill_quest(cmd, 2628, "onslaughttower", "Golden Caster")
    await map_item_quest(cmd, 2629, "onslaughttower", 1627, 1)
    await kill_quest(cmd, 2630, "onslaughttower", "Maximillian Lionfang")

    # falguard
    await kill_quest(cmd, 2666, "falguard", "Chaonslaught Caster")
    await map_item_quest(cmd, 2667, "falguard", 1628, 6)

    # Feeding On The Fallen 2668
    if not await cmd.is_completed_before(2668):
        await cmd.ensure_accept_quest(2668)
        for item, monster, qty in LIONFANG_2668:
            await hunt_item(cmd, item, qty, "falguard", monster_name=monster)
        await cmd.ensure_turn_in_quest(2668)

    await map_item_quest(cmd, 2669, "falguard", 1629, 1)
    await kill_quest(cmd, 2670, "falguard", "Chaonslaught Warrior")
    await map_item_quest(cmd, 2671, "falguard", 1630, 1)
    await map_item_quest(cmd, 2672, "falguard", 1631, 1)
    await kill_quest(cmd, 2673, "falguard", "Chaonslaught Caster")
    await map_item_quest(cmd, 2674, "falguard", 1632, 1)
    await kill_quest(cmd, 2675, "falguard", "Primarch")

    # deathpits
    await kill_quest(cmd, 2720, "deathpits", "Rotting Darkblood")
    await map_item_quest(cmd, 2721, "deathpits", 1691, 5)
    await kill_quest(cmd, 2722, "deathpits", "Rotting Darkblood")
    await kill_quest(cmd, 2723, "deathpits", "Rotting Darkblood")
    await kill_quest(cmd, 2724, "deathpits", "Ghastly Darkblood")
    await kill_quest(cmd, 2725, "deathpits", "Ghastly Darkblood")
    await map_item_quest(cmd, 2726, "deathpits", 1692, 6)
    await kill_quest(cmd, 2727, "deathpits", "Rotting Darkblood")
    await kill_quest(cmd, 2728, "deathpits", "Ghastly Darkblood")
    await kill_quest(cmd, 2729, "deathpits", "Sundered Darkblood")
    await map_item_quest(cmd, 2730, "deathpits", 1693, 9)

    # Honor The Dead 2731
    if not await cmd.is_completed_before(2731):
        await cmd.ensure_accept_quest(2731)
        for item, monster, qty in LIONFANG_2731:
            await hunt_item(cmd, item, qty, "deathpits", monster_name=monster)
        await cmd.ensure_turn_in_quest(2731)

    await map_item_quest(cmd, 2732, "deathpits", 1694, 12)

    # Destroy Wrathful Vestis and Secure The Tears 2740
    if not await cmd.is_completed_before(2740):
        await cmd.ensure_accept_quest(2740)
        await cmd.join_map("deathpits")
        await cmd.get_map_item(LIONFANG_2740_MAP_ITEM)
        await hunt_item(cmd, LIONFANG_2740[0], 1, "deathpits",
                        monster_name=LIONFANG_2740[1])
        await cmd.ensure_turn_in_quest(2740)

    # venomvaults
    await map_item_quest(cmd, 2792, "venomvaults", 1724, 1)
    await kill_quest(cmd, 2793, "venomvaults", "Chaonslaught Warrior")
    await map_item_quest(cmd, 2794, "venomvaults", 1725, 1)
    await map_item_quest(cmd, 2796, "venomvaults", 1726, 1)

    # You've Been Noticed 2798 -- the source guards 2797 and 2798 together
    if not await cmd.is_completed_before(2798):
        await kill_quest(cmd, 2797, "venomvaults", "Chaonslaught Caster")
        await map_item_quest(cmd, 2798, "venomvaults", 1727, 5)

    await kill_quest(cmd, 2799, "venomvaults", "Chaonslaught Caster")
    await kill_quest(cmd, 2800, "venomvaults", "Chaonslaught Warrior")
    await kill_quest(cmd, 2801, "venomvaults", "Chaonslaught Caster")
    await map_item_quest(cmd, 2802, "venomvaults", 1728, 3)
    await kill_quest(cmd, 2803, "venomvaults", "Chaonslaught Caster")
    await kill_quest(cmd, 2804, "venomvaults", "Manticore")

    # Shocking Footwear 2805
    if not await cmd.is_completed_before(2805):
        await cmd.ensure_accept_quest(2805)
        await cmd.join_map("stormtemple")
        await cmd.get_map_item(LIONFANG_2805_MAP_ITEM, LIONFANG_2805_QTY)
        await cmd.ensure_turn_in_quest(2805)

    # New Shoes 2806
    if not await cmd.is_completed_before(2806):
        await cmd.ensure_accept_quest(2806)
        await hunt_item(cmd, LIONFANG_2806[0], 1, "stormtemple",
                        cell=LIONFANG_2806[1], pad=LIONFANG_2806[2],
                        monster_name="*")
        await cmd.ensure_turn_in_quest(2806)

    # stormtemple
    await kill_quest(cmd, 2807, "stormtemple", "Chaonslaught Caster")
    await kill_quest(cmd, 2808, "stormtemple", "Chaonslaught Caster")
    await map_item_quest(cmd, 2809, "stormtemple", 1730, 3)
    await kill_quest(cmd, 2810, "stormtemple", "Chaonslaught Caster")
    await map_item_quest(cmd, 2811, "stormtemple", 1731, 1)
    await kill_quest(cmd, 2812, "stormtemple", "Chaonslaught Cavalry")
    await map_item_quest(cmd, 2813, "stormtemple", 1732, 1)
    await kill_quest(cmd, 2814, "stormtemple", "Chaos Lord Lionfang")
