"""Temple Delve storyline -- port of ``Seasonal/StaffBirthdays/Nulgath/TempleDelve.cs``.

A seasonal chain: ``/templedelve`` quests **9080-9089**, then the
``/siegefortress`` half **9134-9143**, opened by
``TempleSiege.CompleteTempleSiege()``.

The reference gates on ``Core.isSeasonalMapActive("templedelve")``, which asks
the client's event calendar.  This engine has no calendar, so the gate is the
join itself: if the map does not load, the event is not running and the chain
says so instead of hunting a map that is not there.
"""
from bot.core_bots import equip_class
from bot.core_story import kill_quest, map_item_quest, quest_progression
from bot.story.nation.temple_siege import complete_temple_siege
from core.command import Command
from templates.hunt import hunt_item

MAP = "templedelve"
SIEGE_MAP = "siegefortress"


async def seasonal_active(cmd: Command, map_name: str) -> bool:
    """The engine's answer to ``Core.isSeasonalMapActive``: can we join it?"""
    if not cmd.is_in_map(map_name):
        await cmd.join_map(map_name)
    if cmd.is_in_map(map_name):
        return True
    cmd.bot.log(f"[{map_name}] the seasonal map is not active right now.")
    return False


async def _step(cmd: Command, quest_id: int, map_items, hunts,
                map_name: str = MAP) -> None:
    if await quest_progression(cmd, quest_id):
        return
    await cmd.ensure_accept_quest(quest_id)
    for item_id, qty in map_items:
        await cmd.get_map_item(item_id, qty)
    for item, monster, qty in hunts:
        await hunt_item(cmd, item, qty, map_name, monster_name=monster,
                        is_temp=True)
    await cmd.ensure_turn_in_quest(quest_id)


async def temple_delve_storyline(cmd: Command) -> bool:
    """``TempleDelve.Storyline``; False when the event is not running."""
    if not await seasonal_active(cmd, MAP):
        return False

    await complete_temple_siege(cmd)
    cmd.bot.log("[templedelve] walking the Temple Delve storyline")

    await kill_quest(cmd, 9080, MAP, "Overdriven Paladin")

    await _step(cmd, 9081, ((11160, 2), (11161, 2)),
                (("Infested Troll Hide", "Doomed Troll", 7),))

    await _step(cmd, 9082, ((11162, 4),),
                (("Beasts Freed", "Doomed Beast", 6),))

    if not await quest_progression(cmd, 9083):
        await cmd.ensure_accept_quest(9083)
        await hunt_item(cmd, "Fractured Light Shard", 4, MAP,
                        monster_name="Delirious Elemental", is_temp=True)
        await hunt_item(cmd, "Nation Eliminated", 4, MAP,
                        monster_name="Infested Nation", is_temp=True)
        await map_item_quest(cmd, 9083, MAP, 11163)

    await kill_quest(cmd, 9084, MAP, "Infested Nation")
    await kill_quest(cmd, 9085, MAP, "Delirious Elemental")
    await map_item_quest(cmd, 9086, MAP, ((11164, 3), 11165))

    await _step(cmd, 9087, ((11166, 1), (11167, 1)),
                (("Elemental Vanquished", "Delirious Elemental", 6),))

    await _step(cmd, 9088, (),
                (("Frenzied Essence", "Delirious Elemental", 6),
                 ("Nation Essence", "Infested Nation", 6)))

    await equip_class(cmd, solo=True)
    await kill_quest(cmd, 9089, MAP, "Doomed Fiend")

    # ``/siegefortress`` half.
    await kill_quest(cmd, 9134, SIEGE_MAP, "Legion Dreadmarch")
    await kill_quest(cmd, 9135, SIEGE_MAP, "Legion Dread Knight")
    await map_item_quest(cmd, 9136, SIEGE_MAP, ((11312, 4), 11313))

    await _step(cmd, 9137, (),
                (("Knight Demolished", "Legion Dread Knight", 6),
                 ("Dreadmarch Demolished", "Legion Dreadmarch", 6)),
                map_name=SIEGE_MAP)

    await kill_quest(cmd, 9138, SIEGE_MAP, "Shadow Traitor")

    await _step(cmd, 9139, ((11314, 4),),
                (("Traitor Subdued", "Shadow Traitor", 6),),
                map_name=SIEGE_MAP)

    await _step(cmd, 9140, ((11315, 1),),
                (("Light Rune", "Enslaved Elemental", 8),),
                map_name=SIEGE_MAP)

    await _step(cmd, 9141, ((11316, 2),),
                (("Traitor Interrogated", "Shadow Traitor", 5),
                 ("Light Strangled", "Enslaved Elemental", 5)),
                map_name=SIEGE_MAP)

    await kill_quest(cmd, 9142, SIEGE_MAP, "Enslaved Astero")
    await kill_quest(cmd, 9143, SIEGE_MAP, "Dage the Evil")
    return True


async def main(cmd: Command) -> None:
    """Standalone entry (``python -m bot.story.nation.temple_delve``)."""
    await temple_delve_storyline(cmd)
