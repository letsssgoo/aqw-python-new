"""``CoreSoW`` -- Shadows of War, starting with RuinedCrown.

Port of ``Story/ShadowsOfWar/CoreSoW.cs``.  ``AOR.TerminaTemple`` needs
``SoW.ManaCradle``, whose chain runs RuinedCrown -> Timekeep -> TimestreamWar ->
DeadLines -> ShadowFlame -> ManaCradle; the regions are ported from the base of
that chain outwards, so this file starts at ``RuinedCrown``.

``Story.PreLoad`` has no counterpart here (the guards do its work), and
``Adv.GearStore`` is skipped, as everywhere else in this port.
"""
from typing import Sequence, Tuple, Union

from bot.core_bots import equip_class
from bot.core_story import kill_quest, map_item_quest
from core.command import Command
from templates.hunt import hunt_item

RUINED_CROWN_LAST = 8787

#: The quests ``RuinedCrown`` writes out by hand: ``(quest, [(item, monster, qty)])``.
RUINED_CROWN_HANDS = (
    (8779, (("Busted Helmet", "Mana-Burdened Knight", 7),
            ("Brittle Bone", "Mana-Burdened Minion", 7))),
    (8782, (("Swordhaven Crest", "Mana-Burdened Knight", 7),
            ("Shadowscythe Crest", "Mana-Burdened Minion", 7))),
    (8786, (("Frienzied Mana Cleared", "Frenzied Mana", 6),)),
)
RUINED_CROWN_8786_MAP_ITEM = 10386

#: Quest 8788, the merge-shop quest the source runs *after* the gate quest.
RUINED_CROWN_MERGE_QUEST = 8788
RUINED_CROWN_MERGE_FARM = (("Mana Residue", "Frenzied Mana", 8),
                           ("Mage's Blood Sample", "Mana-Burdened Mage", 8))
RUINED_CROWN_MERGE_SOLO = ("Warlic's Favor", "Calamitous Warlic")


async def ruined_crown(cmd: Command) -> None:
    """``CoreSoW.RuinedCrown``: quests 8778-8788 in /ruinedcrown.

    Two source quirks are kept as they are:

    * 8784 runs *before* 8783 (the comment says so too);
    * 8788 sits after the 8787 gate, so it only runs on the pass that finishes
      8787 -- a call on an account that already has 8787 returns at the top and
      never reaches it.
    """
    if await cmd.is_completed_before(RUINED_CROWN_LAST):
        return

    await map_item_quest(cmd, 8778, "ruinedcrown", (10380, 10382, 10383), 1)

    for quest_id, hunts in RUINED_CROWN_HANDS:
        if await cmd.is_completed_before(quest_id):
            continue
        await cmd.ensure_accept_quest(quest_id)
        if quest_id == 8786:
            await cmd.join_map("ruinedcrown")
            await cmd.get_map_item(RUINED_CROWN_8786_MAP_ITEM)
        for item, monster, qty in hunts:
            await hunt_item(cmd, item, qty, "ruinedcrown", monster_name=monster)
        await cmd.ensure_turn_in_quest(quest_id)

    await map_item_quest(cmd, 8780, "ruinedcrown", 10384, 6)
    await kill_quest(cmd, 8781, "ruinedcrown", "Mana-Burdened Mage")
    await map_item_quest(cmd, 8784, "ruinedcrown", 10385, 6)   # before 8783
    await kill_quest(cmd, 8783, "ruinedcrown", "Frenzied Mana")
    await kill_quest(cmd, 8785, "ruinedcrown", "Mana-Burdened Mage")
    await kill_quest(cmd, RUINED_CROWN_LAST, "ruinedcrown", "Calamitous Warlic")

    # Em-pathetic Connection (Merge Shop Quest) 8788
    await cmd.ensure_accept_quest(RUINED_CROWN_MERGE_QUEST)
    await equip_class(cmd)
    for item, monster, qty in RUINED_CROWN_MERGE_FARM:
        await hunt_item(cmd, item, qty, "ruinedcrown", monster_name=monster)
    await equip_class(cmd, solo=True)
    await hunt_item(cmd, RUINED_CROWN_MERGE_SOLO[0], 1, "ruinedcrown",
                    monster_name=RUINED_CROWN_MERGE_SOLO[1])
    await cmd.ensure_turn_in_quest(RUINED_CROWN_MERGE_QUEST)


async def main(cmd: Command):
    await ruined_crown(cmd)


TIMEKEEP_LAST = 8813
TIMEKEEP_MAP = "timekeep"

#: ``Timekeep``'s hand-written quests: ``(quest, [(item, monster, qty)])``.
TIMEKEEP_HANDS = (
    (8810, (("Imp Bones", "Distorted Imp", 7),
            ("Mage Quelled", "Mana-Burdened Mage", 7))),
    (8811, (("Mumbler Crushed", "Mumbler", 7),
            ("Locust Smashed", "Decaying Locust", 7))),
    (8813, (("Gar's Resignation Letter", "Mal-formed Gar", 1),
            ("Mumbler Drool", "Mumbler", 8),
            ("Locust Wings", "Decaying Locust", 8))),
)


async def timekeep(cmd: Command) -> None:
    """``CoreSoW.Timekeep``: quests 8803-8813 in /timekeep.

    The source writes the map as ``"Timekeep"`` in the plain quest calls and
    ``"timekeep"`` in the hand-written ones; this engine compares map names
    without case, so one spelling is used throughout.
    """
    if await cmd.is_completed_before(TIMEKEEP_LAST):
        return

    await ruined_crown(cmd)

    await map_item_quest(cmd, 8803, TIMEKEEP_MAP, (10455, 10456, 10457), 1)
    await kill_quest(cmd, 8804, TIMEKEEP_MAP, "Decaying Locust")
    await kill_quest(cmd, 8805, TIMEKEEP_MAP, "Distorted Imp")
    await map_item_quest(cmd, 8806, TIMEKEEP_MAP, 10458, 6)
    await kill_quest(cmd, 8807, TIMEKEEP_MAP, "Mana-Burdened Mage")
    await map_item_quest(cmd, 8808, TIMEKEEP_MAP, (10459, 10460), 1)
    await kill_quest(cmd, 8809, TIMEKEEP_MAP, "Mumbler")

    for quest_id, hunts in TIMEKEEP_HANDS:
        if await cmd.is_completed_before(quest_id):
            continue
        await cmd.ensure_accept_quest(quest_id)
        for item, monster, qty in hunts:
            await hunt_item(cmd, item, qty, TIMEKEEP_MAP, monster_name=monster)
        await cmd.ensure_turn_in_quest(quest_id)

    await kill_quest(cmd, 8812, TIMEKEEP_MAP, "Mal-formed Gar")


TIMESTREAM_WAR_LAST = 8819
TIMESTREAM_WAR_MAP = "streamwar"
TIMESTREAM_MEDAL_QUEST = 8814
TIMESTREAM_MEDAL = ("Timestream Medal", "Decaying Locust", 5)


async def timestream_war(cmd: Command) -> None:
    """``CoreSoW.TimestreamWar``: quests 8814-8819 in /streamwar.

    The source guards 8814 with ``Bot.Quests.IsUnlocked(8816)`` -- a client-side
    slot value this engine has no way to read.  The same question is asked the
    server's way instead: if 8816 is already done, 8814's medals are not needed.
    """
    if await cmd.is_completed_before(TIMESTREAM_WAR_LAST):
        return

    await timekeep(cmd)

    if not await cmd.is_completed_before(8816):
        await cmd.ensure_accept_quest(TIMESTREAM_MEDAL_QUEST)
        await hunt_item(cmd, TIMESTREAM_MEDAL[0], TIMESTREAM_MEDAL[2],
                        TIMESTREAM_WAR_MAP, monster_name=TIMESTREAM_MEDAL[1])
        await cmd.ensure_turn_in_quest(TIMESTREAM_MEDAL_QUEST)

    await kill_quest(cmd, 8816, TIMESTREAM_WAR_MAP, "Mumbler")
    await kill_quest(cmd, 8817, TIMESTREAM_WAR_MAP, "Decaying Locust")
    await kill_quest(cmd, 8818, TIMESTREAM_WAR_MAP, "False Wyvern")
    await kill_quest(cmd, TIMESTREAM_WAR_LAST, TIMESTREAM_WAR_MAP, "Second Speaker")


DEADLINES_LAST = 8868
DEADLINES_MAP = "deadlines"

#: ``DeadLines``' hand-written quests: ``(quest, map items, hunts)``.  Seven of
#: the eight want map items *and* a drop before they can be turned in.
DEADLINES_HANDS = (
    (8860, (10602,), (("Mana Dispelled", "Frenzied Mana", 6),)),
    (8861, (10603, 10604), (("Shadowfall Helm", "Shadowfall Warrior", 7),)),
    (8862, (10605, 10606), (("Knight's Crest", "Swordhaven Knight", 7),)),
    (8863, (10607, 10608), (("Shadowfall Bones", "Shadowfall Warrior", 7),)),
    (8864, (10609, 10610), (("Knight's Armaments", "Swordhaven Knight", 7),)),
    (8865, (10611, 10612), (("Mana Dissipated", "Frenzied Mana", 6),)),
    (8866, (10613,), (("Mage Hoods", "Chaos Mage", 6),)),
    (8867, (10614,), (("Mana Cleared", "Frenzied Mana", 6),)),
)


async def dead_lines(cmd: Command) -> None:
    """``CoreSoW.DeadLines``: quests 8859-8868 in /deadlines.

    The last quest is fought in the solo class, which the source sets just before
    it; the map name is written ``"DeadLines"`` there and ``"deadlines"`` in the
    hand-written blocks, and one spelling is used here throughout.
    """
    if await cmd.is_completed_before(DEADLINES_LAST):
        return

    await timestream_war(cmd)

    await map_item_quest(cmd, 8859, DEADLINES_MAP, 10601, 6)

    for quest_id, map_items, hunts in DEADLINES_HANDS:
        if await cmd.is_completed_before(quest_id):
            continue
        await cmd.ensure_accept_quest(quest_id)
        await cmd.join_map(DEADLINES_MAP)
        for item_id in map_items:
            await cmd.get_map_item(item_id)
        for item, monster, qty in hunts:
            await hunt_item(cmd, item, qty, DEADLINES_MAP, monster_name=monster)
        await cmd.ensure_turn_in_quest(quest_id)

    await equip_class(cmd, solo=True)
    await kill_quest(cmd, DEADLINES_LAST, DEADLINES_MAP, "Eternal Dragon")


SHADOWFLAME_LAST = 8965
SHADOWFLAME_MAP = "worldscore"

#: ``ShadowFlame``'s hand-written quests: ``(quest, [(map item, qty)], hunts)``.
SHADOWFLAME_HANDS = (
    (8957, ((10878, 5),), (("Pulsating Mana Residue", "Elemental Attempt", 12),)),
    (8958, ((10879, 1),), (("Waxen Horns", "Infernal Mockery", 12),)),
    (8959, ((10880, 4),), (("Infernal Shoved", "Infernal Mockery", 10),)),
    (8960, ((10881, 1),), (("Vanquished Elemental", "Elemental Attempt", 14),)),
    (8963, ((10883, 1),), (("Rubbery Wings", "Infernal Mockery", 14),)),
    (8964, ((10884, 1),), (("Sterile Mana", "Elemental Attempt", 16),)),
)


async def shadow_flame(cmd: Command) -> None:
    """``CoreSoW.ShadowFlame``: quests 8956-8965 in /worldscore."""
    if await cmd.is_completed_before(SHADOWFLAME_LAST):
        return

    await dead_lines(cmd)
    await equip_class(cmd, solo=True)

    # Lies in Peace 8956 -- one quest, a map item and a kill.
    await map_item_quest(cmd, 8956, SHADOWFLAME_MAP, 10877, 1)
    await kill_quest(cmd, 8956, SHADOWFLAME_MAP, "False Wyvern")

    for quest_id, map_items, hunts in SHADOWFLAME_HANDS:
        if await cmd.is_completed_before(quest_id):
            continue
        await cmd.ensure_accept_quest(quest_id)
        await cmd.join_map(SHADOWFLAME_MAP)
        for item_id, qty in map_items:
            await cmd.get_map_item(item_id, qty)
        for item, monster, qty in hunts:
            await hunt_item(cmd, item, qty, SHADOWFLAME_MAP, monster_name=monster)
        await cmd.ensure_turn_in_quest(quest_id)

    await map_item_quest(cmd, 8961, SHADOWFLAME_MAP, 10882, 4)
    await kill_quest(cmd, 8962, SHADOWFLAME_MAP, "Crystalized Mana")
    await kill_quest(cmd, SHADOWFLAME_LAST, SHADOWFLAME_MAP, "Mask of Tranquility")


#: ``CoreSoW.MainyuDrops`` -- the Mainyu's drops, banked after the fight.
MAINYU_DROPS = ("Mainyu Rune", "Mainyu Tail", "Mainyu Wings")

#: ``CoreSoW.MalgorDrops`` -- Malgor's drops, banked with them.
MALGOR_DROPS = ("Shadow DragonMaster",
                "Shadow DragonMaster's Helm",
                "Shadow DragonMaster's Tail + Blades",
                "Shadow Dragonscale Blade",
                "Shadowflame Devastation",
                "ShadowFlame Dragon Blade",
                "Shadowflame Shroud",
                "Shadowflame Vanguard Armet",
                "Shadowflame Vanguard Armet Locks",
                "Shadowflame Vanguard Spear")

MANACRADLE_LAST = 9126
MANACRADLE_MAP = "manacradle"

#: ``ManaCradle``'s hand-written quests, same shape as above.
MANACRADLE_HANDS = (
    (9119, (), (("Crystal Shard", "Crystalized Mana", 8),
                ("Elemental Drops", "Elemental Attempt", 8))),
    (9123, ((11271, 1),), (("Dark Shard", "Darkness Elemental", 10),
                           ("Dark Residue", "Dark Tainted Mana", 10))),
)
#: Malgor and The Mainyu, the two the source fights in its dodge class.
MANACRADLE_BOSSES = ((9124, "Malgor"), (9125, "The Mainyu"))


async def mana_cradle(cmd: Command) -> None:
    """``CoreSoW.ManaCradle``: quests 9116-9125 in /manacradle.

    This is the last link of the chain ``AOR.TerminaTemple`` needs.

    Where this engine cannot follow, it says so instead of guessing:
    ``Core.EquipClass(ClassType.Dodge)`` has no ``Dodge`` case here, so the solo
    class is equipped for the two bosses, and ``Adv.GearStore`` is skipped, as
    everywhere else in this port.  ``Core.ToBank(MainyuDrops + MalgorDrops)`` is
    here: those are plain name lists in the source, ported as
    :data:`MAINYU_DROPS` and :data:`MALGOR_DROPS`.  The last two quests
    (9126/9127) are commented out in the source and stay out.
    """
    if await cmd.is_completed_before(MANACRADLE_LAST):
        return

    await shadow_flame(cmd)
    await equip_class(cmd, solo=True)

    await kill_quest(cmd, 9116, MANACRADLE_MAP, "Elemental Attempt")
    await kill_quest(cmd, 9117, MANACRADLE_MAP, "Crystalized Mana")
    await map_item_quest(cmd, 9118, MANACRADLE_MAP, 11268, 3)
    await map_item_quest(cmd, 9118, MANACRADLE_MAP, 11269, 3)

    for quest_id, map_items, hunts in MANACRADLE_HANDS:
        if await cmd.is_completed_before(quest_id):
            continue
        await cmd.ensure_accept_quest(quest_id)
        await cmd.join_map(MANACRADLE_MAP)
        for item_id, qty in map_items:
            await cmd.get_map_item(item_id, qty)
        for item, monster, qty in hunts:
            await hunt_item(cmd, item, qty, MANACRADLE_MAP, monster_name=monster)
        await cmd.ensure_turn_in_quest(quest_id)

    await kill_quest(cmd, 9120, MANACRADLE_MAP, "Dark Tainted Mana")
    await kill_quest(cmd, 9121, MANACRADLE_MAP, "Darkness Elemental")
    await map_item_quest(cmd, 9122, MANACRADLE_MAP, 11270, 5)

    # The reference swaps to its dodge class here; this engine has no Dodge case.
    await equip_class(cmd, solo=True)
    for quest_id, monster in MANACRADLE_BOSSES:
        await kill_quest(cmd, quest_id, MANACRADLE_MAP, monster)

    await cmd.inv_to_bank(MALGOR_DROPS + MAINYU_DROPS)
