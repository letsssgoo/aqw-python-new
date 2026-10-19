"""``CoreAOR`` -- Age of Ruin, starting with TerminaTemple.

Port of ``Story/AgeOfRuin/CoreAOR.cs``.  The regions are ported from the base of
the chain outwards: ``TerminaTemple`` is what ``KathoolAdeptPrerequisite`` needs
(via the merge shops' ``AOR`` calls), and ``TwilightZone`` -- the merge shop whose
port already exists -- sits three links up from it.

``CoreSoW.ManaCradle`` is the story lead-in, and it is ported.  Two things are
not, and are reported rather than skipped quietly: the ``seaVoice`` and
``coldThunder`` branches (each needs another AOR region that is not ported yet),
and ``Story.PreLoad`` (the guards do its work).
"""
from core.command import Command
from bot.core_bots import equip_class
from bot.core_story import kill_quest, map_item_quest
from bot.story.shadows_of_war.core_sow import mana_cradle
from templates.hunt import hunt_item

TERMINA_TEMPLE_MAP = "terminatemple"

#: The gate quest depends on the option flags, exactly as the source writes it.
TERMINA_TEMPLE_LAST_DEFAULT = 10438
TERMINA_TEMPLE_LAST_SEAVOICE = 9351
TERMINA_TEMPLE_LAST_COLDTHUNDER = 9851

#: ``(quest, [(map item id, qty)], (item, monster, qty))`` for the two quests the
#: source writes out by hand.
TERMINA_TEMPLE_HANDS = (
    (9213, ((11625, 1), (11626, 1), (11627, 1)),
     ("Defender Trained", "Termina Defender", 7)),
    (9214, ((11628, 1), (11629, 1), (11630, 1)),
     ("Guard Fought", "Clandestine Guard", 7)),
)

#: The rest of the region, as plain map-item quests.
TERMINA_TEMPLE_STEPS = (
    (9351, (12050, 12051), 1),
    (9851, (13541, 13542), 1),
)
SEAVOICE_GATE = 9348


def termina_temple_last(sea_voice: bool = False,
                        cold_thunder: bool = False) -> int:
    """The quest that closes this region for the given option flags."""
    if cold_thunder:
        return TERMINA_TEMPLE_LAST_COLDTHUNDER
    if sea_voice:
        return TERMINA_TEMPLE_LAST_SEAVOICE
    return TERMINA_TEMPLE_LAST_DEFAULT


async def termina_temple(cmd: Command, sea_voice: bool = False,
                         cold_thunder: bool = False) -> None:
    """``CoreAOR.TerminaTemple``: quests 9213-9214, then 9351/9851 by option.

    Args:
        cmd (Command): Facade to act through.
        sea_voice (bool): The reference's ``seaVoice`` option; its branch needs
            the ``SeaVoice`` region, which is not ported.
        cold_thunder (bool): The reference's ``coldThunder`` option; likewise.

    The 9213 pass keeps the source's map reset (leave to ``whitemap-100000`` and
    come back) because, as its own log line says, the mobs there can bug out and
    become unattackable.
    """
    if await cmd.is_completed_before(termina_temple_last(sea_voice, cold_thunder)):
        return

    await mana_cradle(cmd)

    # Familiar Faces (9213)
    if not await cmd.is_completed_before(9213):
        await cmd.ensure_accept_quest(9213)
        await cmd.join_map(TERMINA_TEMPLE_MAP)
        for item_id, qty in TERMINA_TEMPLE_HANDS[0][1]:
            await cmd.get_map_item(item_id, qty)
        cmd.bot.log("resetting map data ( mobs can bug out and become "
                    "unattackable)")
        await cmd.join_map("whitemap", 100000)
        await cmd.join_map(TERMINA_TEMPLE_MAP)
        item, monster, qty = TERMINA_TEMPLE_HANDS[0][2]
        await hunt_item(cmd, item, qty, TERMINA_TEMPLE_MAP, monster_name=monster)
        await cmd.ensure_turn_in_quest(9213)

    # Loaded Resume (9214)
    if not await cmd.is_completed_before(9214):
        await cmd.ensure_accept_quest(9214)
        await cmd.join_map(TERMINA_TEMPLE_MAP)
        for item_id, qty in TERMINA_TEMPLE_HANDS[1][1]:
            await cmd.get_map_item(item_id, qty)
        item, monster, qty = TERMINA_TEMPLE_HANDS[1][2]
        await hunt_item(cmd, item, qty, TERMINA_TEMPLE_MAP, monster_name=monster)
        await cmd.ensure_turn_in_quest(9214)

    if not sea_voice and not cold_thunder:
        return

    # The source's own condition: SeaVoice when asked for, or when the quest it
    # gates is still unfinished.
    if sea_voice or (cold_thunder
                     and not await cmd.is_completed_before(SEAVOICE_GATE)):
        cmd.bot.log("[aor] the SeaVoice branch needs the SeaVoice region, which "
                    "is not ported yet; Termina Temple's own quests are done.")
        return

    # Mopping Up (9351)
    await map_item_quest(cmd, 9351, TERMINA_TEMPLE_MAP, (12050, 12051), 1)

    if sea_voice and not cold_thunder:
        return

    if cold_thunder:
        cmd.bot.log("[aor] the coldThunder branch needs the ColdThunder region, "
                    "which is not ported yet; stopping before 9851.")
        return

    # Tell-Tale Heart (9851)
    await map_item_quest(cmd, 9851, TERMINA_TEMPLE_MAP, (13541, 13542), 1)


async def main(cmd: Command):
    await termina_temple(cmd)


ASHRAY_LAST = 9234
ASHRAY_MAP = "ashray"

#: ``AshrayVillage``'s hand-written quests: ``(quest, [(map item, qty)], hunts)``.
ASHRAY_HANDS = (
    (9226, ((11663, 1), (11664, 1)),
     (("Fisherman's Trident", "Ashray Fisherman", 4),)),
    (9228, ((11665, 1),), (("Elemental Cleared", "Stagnant Water", 8),)),
    (9229, ((11666, 1),), (("Fisherman Repelled", "Ashray Fisherman", 8),)),
    (9231, ((11667, 1),), (("Excorsized Eel", "Ghostly Eel", 8),)),
    (9232, ((11668, 1),), (("Water Samples", "Stagnant Water", 3),)),
)


async def ashray_village(cmd: Command, sea_voice: bool = False,
                         cold_thunder: bool = False) -> None:
    """``CoreAOR.AshrayVillage``: quests 9225-9234 in /ashray."""
    if await cmd.is_completed_before(ASHRAY_LAST):
        return

    await termina_temple(cmd, sea_voice, cold_thunder)

    await kill_quest(cmd, 9225, ASHRAY_MAP, "Kitefin Shark Bait")

    for quest_id, map_items, hunts in ASHRAY_HANDS:
        if await cmd.is_completed_before(quest_id):
            continue
        await cmd.ensure_accept_quest(quest_id)
        await cmd.join_map(ASHRAY_MAP)
        for item_id, qty in map_items:
            await cmd.get_map_item(item_id, qty)
        for item, monster, qty in hunts:
            await hunt_item(cmd, item, qty, ASHRAY_MAP, monster_name=monster)
        await cmd.ensure_turn_in_quest(quest_id)

    await kill_quest(cmd, 9227, ASHRAY_MAP, "Ghostly Eel")
    await kill_quest(cmd, 9230, ASHRAY_MAP, "Kitefin Shark Bait")
    await map_item_quest(cmd, 9233, ASHRAY_MAP, (11669, 11670), 1)
    await kill_quest(cmd, ASHRAY_LAST, ASHRAY_MAP, "Seafoam Elemental")
