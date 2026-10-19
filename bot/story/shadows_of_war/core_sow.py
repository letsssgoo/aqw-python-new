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
