"""Void Refuge storyline -- port of ``Story/Nation/VoidRefuge.cs``.

Quests **9522-9531** in ``/voidrefuge``: kills for the early steps, then map
items plus the monsters the quests name, ending with Carnage.  The whole chain
is gated on 9531; a completed chain returns immediately, like the reference's
``isCompletedBefore``.
"""
from bot.core_bots import equip_class
from bot.core_story import kill_quest, map_item_quest, quest_progression
from core.command import Command
from templates.hunt import hunt_item

MAP = "voidrefuge"
GATE_QUEST = 9531


async def _step(cmd: Command, quest_id: int, map_items, hunts) -> None:
    """Accept, pick the map items up, hunt the drops, turn the quest in."""
    if await quest_progression(cmd, quest_id):
        return
    await cmd.ensure_accept_quest(quest_id)
    if map_items:
        for item_id, qty in map_items:
            await cmd.get_map_item(item_id, qty)
    for item, monster, qty in hunts:
        await hunt_item(cmd, item, qty, MAP, monster_name=monster,
                        is_temp=True)
    await cmd.ensure_turn_in_quest(quest_id)


async def void_refuge_storyline(cmd: Command) -> None:
    """``VoidRefuge.Storyline``."""
    if await cmd.is_completed_before(GATE_QUEST):
        return
    cmd.bot.log("[voidrefuge] walking the Void Refuge storyline")

    await kill_quest(cmd, 9522, MAP, "Lightguard Paladin")
    await kill_quest(cmd, 9523, MAP, "Paladin Ascendant")

    await _step(cmd, 9524, ((12572, 1),),
                (("Void Engraving", "Nation Caster", 5),))

    await kill_quest(cmd, 9525, MAP, "Nation Outrider")

    await _step(cmd, 9526, ((12573, 1),),
                (("Paladin's Iudex Oath", "Lightguard Paladin", 6),
                 ("Ascendant's Iudex Oath", "Paladin Ascendant", 3)))

    await _step(cmd, 9527, ((12574, 5),),
                (("Void Tattoo", "Nation Caster", 3),))

    await kill_quest(cmd, 9528, MAP, "Nation Outrider")
    await map_item_quest(cmd, 9529, MAP, (12575, 12576, 12577))

    await equip_class(cmd, solo=True)
    await _step(cmd, 9530, (),
                (("Shimmering Blood", "Paladin Ascendant", 4),
                 ("Caustic Blood", "Nation Outrider", 8)))

    await kill_quest(cmd, 9531, MAP, "Carnage")


async def main(cmd: Command) -> None:
    """Standalone entry (``python -m bot.story.nation.void_refuge``)."""
    await void_refuge_storyline(cmd)
