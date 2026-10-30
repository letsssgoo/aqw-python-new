"""Temple Siege storyline -- port of ``TempleSiege.CompleteTempleSiege``.

Quests **9058-9067** in ``/templesiege``: map items paired with the drops the
quest names, plain kills for the rest, and Doomed Oblivion last.  Gated on
9067, like the reference's ``isCompletedBefore``.
"""
from bot.core_bots import equip_class
from bot.core_story import kill_quest, map_item_quest, quest_progression
from core.command import Command
from templates.hunt import hunt_item

MAP = "templesiege"
GATE_QUEST = 9067


async def _step(cmd: Command, quest_id: int, map_items, hunts) -> None:
    if await quest_progression(cmd, quest_id):
        return
    await cmd.ensure_accept_quest(quest_id)
    for item_id, qty in map_items:
        await cmd.get_map_item(item_id, qty)
    for item, monster, qty in hunts:
        await hunt_item(cmd, item, qty, MAP, monster_name=monster,
                        is_temp=True)
    await cmd.ensure_turn_in_quest(quest_id)


async def complete_temple_siege(cmd: Command) -> None:
    """``TempleSiege.CompleteTempleSiege``."""
    if await cmd.is_completed_before(GATE_QUEST):
        return
    cmd.bot.log("[templesiege] walking the Temple Siege storyline")

    await _step(cmd, 9058, ((11129, 8),),
                (("Solidified Light", "Light Elemental", 8),))

    await kill_quest(cmd, 9059, MAP, "Overdriven Paladin")

    await kill_quest(cmd, 9060, MAP, ("Overdriven Paladin", "Light Elemental"))

    await map_item_quest(cmd, 9061, MAP, (11130, 11131, 11132))

    await _step(cmd, 9062, (),
                (("Engraved Vambrace", "Overdriven Paladin", 3),
                 ("Elemental Bracelet", "Light Elemental", 3)))

    await map_item_quest(cmd, 9063, MAP, ((11133, 6), 11134))

    await kill_quest(cmd, 9064, MAP, "Doomed Beast")
    await kill_quest(cmd, 9065, MAP, "Doomed Troll")

    await _step(cmd, 9066, (),
                (("Troll Tusks", "Doomed Troll", 6),
                 ("Beast Eyes", "Doomed Beast", 6)))

    await equip_class(cmd, solo=True)
    await kill_quest(cmd, 9067, MAP, "Doomed Oblivion")


async def main(cmd: Command) -> None:
    """Standalone entry (``python -m bot.story.nation.temple_siege``)."""
    await complete_temple_siege(cmd)
