"""Void Chasm storyline -- port of ``Story/Nation/VoidChasm.cs``.

Quests **9543-9552** in ``/voidchasm``, after the Void Refuge chain it opens
with (``VR.Storyline()``).  Early steps are plain kills, the middle ones pair a
map item with the drops the quest names, and 9551 is fought on the solo class
with ``Carnage`` as the last elite before 9552.
"""
from bot.core_bots import equip_class
from bot.core_story import kill_quest, map_item_quest, quest_progression
from bot.story.nation.void_refuge import void_refuge_storyline
from core.command import Command
from templates.hunt import hunt_item

MAP = "voidchasm"
GATE_QUEST = 9552


async def _step(cmd: Command, quest_id: int, map_items, hunts,
                solo: bool = False) -> None:
    if await quest_progression(cmd, quest_id):
        return
    if solo:
        await equip_class(cmd, solo=True)
    await cmd.ensure_accept_quest(quest_id)
    if map_items:
        for item_id, qty in map_items:
            await cmd.get_map_item(item_id, qty)
    for item, monster, qty in hunts:
        await hunt_item(cmd, item, qty, MAP, monster_name=monster,
                        is_temp=False)
    await cmd.ensure_turn_in_quest(quest_id)


async def void_chasm_storyline(cmd: Command) -> None:
    """``VoidChasm.Storyline``."""
    if await cmd.is_completed_before(GATE_QUEST):
        return

    await void_refuge_storyline(cmd)
    cmd.bot.log("[voidchasm] walking the Void Chasm storyline")

    await kill_quest(cmd, 9543, MAP, "Paladin Ascendant")
    await kill_quest(cmd, 9544, MAP, "Nation Outrider")

    await _step(cmd, 9545, ((12619, 6),),
                (("Alberic Seal", "Paladin Ascendant", 3),))

    await map_item_quest(cmd, 9546, MAP, (12620, 12621))

    await _step(cmd, 9547, ((12622, 1),),
                (("Outrider's Keepsake", "Nation Outrider", 4),))

    await kill_quest(cmd, 9548, MAP, "Void Fang")

    await _step(cmd, 9549, ((12623, 1), (12627, 1), (12628, 1)),
                (("Phantom's Sigh", "The Hushed", 5),))

    await _step(cmd, 9550, ((12624, 4),),
                (("Blank Contract", "The Hushed", 3),
                 ("Fiendish Sinew", "Void Fang", 6)))

    await _step(cmd, 9551, ((12625, 1), (12626, 1)),
                (("Voided Blood Sample", "Carnage", 1)), solo=True)

    await kill_quest(cmd, 9552, MAP, "Carcano")


async def main(cmd: Command) -> None:
    """Standalone entry (``python -m bot.story.nation.void_chasm``)."""
    await void_chasm_storyline(cmd)
