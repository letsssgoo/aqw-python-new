"""The Void Refuge storyline -- quests 9522-9531 in /voidrefuge.

Port of ``Story/Nation/VoidRefuge.cs``.

Ten quests in order, three of which also want a map item (one of them five times,
and one three different items), and two that name more than one monster -- which
the reference resolves by matching its requirement list to the monsters by
position.
"""
from typing import Optional, Sequence, Tuple, Union

from core.command import Command
from bot.core_story import kill_quest, map_item_quest

#: The map everything happens in, and the quest that gates the chain.
MAP_NAME = "voidrefuge"
LAST_QUEST = 9531

#: ``(quest, map item id or ids, how many, monster or monsters)``, in the
#: reference's own order; ``None`` means that quest has no such step.
STEPS: Tuple[Tuple[int, Optional[Union[int, Sequence[int]]], int,
                   Optional[Union[str, Sequence[str]]]], ...] = (
    (9522, None, 0, "Lightguard Paladin"),
    (9523, None, 0, "Paladin Ascendant"),
    (9524, 12572, 1, "Nation Caster"),
    (9525, None, 0, "Nation Outrider"),
    (9526, 12573, 1, ("Lightguard Paladin", "Paladin Ascendant")),
    (9527, 12574, 5, "Nation Caster"),
    (9528, None, 0, "Nation Outrider"),
    (9529, (12575, 12576, 12577), 1, None),
    (9530, None, 0, ("Paladin Ascendant", "Nation Outrider")),
    (LAST_QUEST, None, 0, "Carnage"),
)


async def main(cmd: Command):
    if await cmd.is_completed_before(LAST_QUEST):
        return

    for quest_id, item_ids, qty, monsters in STEPS:
        if item_ids is not None:
            await map_item_quest(cmd, quest_id, MAP_NAME, item_ids, qty)
        if monsters is not None:
            await kill_quest(cmd, quest_id, MAP_NAME, monsters)
