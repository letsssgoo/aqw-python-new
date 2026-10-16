"""``Core13LoC`` -- the thirteen Lords of Chaos, only Escherion so far.

Port of ``Story/LordsofChaos/Core13LoC.cs``.  The forge enhancement unlocks need
``Escherion()``, so that is the method ported; the rest of the file waits for a
caller.  Note that this is *not* ``CoreNation.KillEscherion`` -- same target,
different class, different job: this one is the whole /mobius story.

``Story.PreLoad`` has no counterpart here; the guards do its work.
"""
from typing import Sequence, Tuple, Union

from bot.core_story import kill_quest, map_item_quest
from core.command import Command
from bot.nation.core_nation import kill_escherion
from templates.hunt import hunt_item

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
