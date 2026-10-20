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
from bot.core_advanced import buy_item
from bot.core_bots import equip_class
from bot.core_story import kill_quest, map_item_quest
from bot.story.shadows_of_war.core_sow import mana_cradle
from templates.hunt import hunt_item

TERMINA_TEMPLE_MAP = "terminatemple"

#: The gate quest depends on the option flags, exactly as the source writes it.
TERMINA_TEMPLE_LAST_DEFAULT = 10438
TERMINA_TEMPLE_LAST_SEAVOICE = 9351
TERMINA_TEMPLE_LAST_COLDTHUNDER = 9851
#: The last quest the default branch actually turns in.  10438 is the
#: reference's sentinel but it is not one of the quests this function completes,
#: so on an account that only finished 9213/9214 the region would be walked
#: again on every run; either id means "region done".
TERMINA_TEMPLE_DONE_DEFAULT = 9214

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
    if not sea_voice and not cold_thunder and \
            await cmd.is_completed_before(TERMINA_TEMPLE_DONE_DEFAULT):
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


SUNLIGHT_LAST = 9251
SUNLIGHT_MAP = "sunlightzone"

#: ``SunlightZone``'s hand-written quests: ``(quest, [(map item, qty)], hunts)``.
SUNLIGHT_HANDS = (
    (9244, ((11705, 1), (11706, 1)), (("Mopped Water", "Blighted Water", 6),)),
    (9245, ((11707, 3),), (("Jelly Filling", "Spectral Jellyfish", 6),)),
    (9246, (), (("Stinging Tentacles", "Spectral Jellyfish", 6),
                ("Grainy Water", "Blighted Water", 6))),
    (9248, ((11711, 1),), (("Astravian Dispelled", "Astravian Illusion", 10),)),
    (9249, ((11712, 5),), (("Infernal Dispelled", "Infernal Illusion", 10),)),
    (9250, ((11713, 1),), (("Seraph Dispelled", "Seraphic Illusion", 10),)),
)


async def sunlight_zone(cmd: Command, sea_voice: bool = False,
                        cold_thunder: bool = False) -> None:
    """``CoreAOR.SunlightZone``: quests 9242-9251 in /sunlightzone."""
    if await cmd.is_completed_before(SUNLIGHT_LAST):
        return

    await ashray_village(cmd, sea_voice, cold_thunder)

    await kill_quest(cmd, 9242, SUNLIGHT_MAP, "Blighted Water")
    await kill_quest(cmd, 9243, SUNLIGHT_MAP, "Spectral Jellyfish")

    for quest_id, map_items, hunts in SUNLIGHT_HANDS:
        if await cmd.is_completed_before(quest_id):
            continue
        await cmd.ensure_accept_quest(quest_id)
        await cmd.join_map(SUNLIGHT_MAP)
        for item_id, qty in map_items:
            await cmd.get_map_item(item_id, qty)
        for item, monster, qty in hunts:
            await hunt_item(cmd, item, qty, SUNLIGHT_MAP, monster_name=monster)
        await cmd.ensure_turn_in_quest(quest_id)

    await map_item_quest(cmd, 9247, SUNLIGHT_MAP, (11708, 11709, 11710), 1)
    await kill_quest(cmd, SUNLIGHT_LAST, SUNLIGHT_MAP, "Marine Snow")


TWILIGHT_LAST = 9268
TWILIGHT_MAP = "twilightzone"

#: ``TwilightZone``'s hand-written quests.
TWILIGHT_HANDS = (
    (9261, (), (("Louse Antennae", "Whale Louse", 6),
                ("Lamprey Tooth", "Polymelia Lamprey", 6))),
    (9266, (), (("Spirit Restrained", "Decay Spirit", 7),
                ("Guardian Restrained", "Ice Guardian", 7))),
    (9267, (), (("Leviathan Fought", "Leviathan", 1),)),
)


async def twilight_zone(cmd: Command, sea_voice: bool = False,
                        cold_thunder: bool = False) -> None:
    """``CoreAOR.TwilightZone``: quests 9258-9268 in /twilightzone.

    This is the region the ``TwilightZoneMerge`` shop calls, and the map its
    ``/twilightzone`` merge lives in.  9260 is two map-item calls for one quest,
    as the source has it; 9267 is fought in the solo class.
    """
    if await cmd.is_completed_before(TWILIGHT_LAST):
        return

    await sunlight_zone(cmd, sea_voice, cold_thunder)

    await kill_quest(cmd, 9258, TWILIGHT_MAP, "Whale Louse")
    await kill_quest(cmd, 9259, TWILIGHT_MAP, "Polymelia Lamprey")
    await map_item_quest(cmd, 9260, TWILIGHT_MAP, 11749, 1)
    await map_item_quest(cmd, 9260, TWILIGHT_MAP, 11750, 4)

    for quest_id, map_items, hunts in TWILIGHT_HANDS:
        if await cmd.is_completed_before(quest_id):
            continue
        await cmd.ensure_accept_quest(quest_id)
        if quest_id == 9267:
            await equip_class(cmd, solo=True)
        await cmd.join_map(TWILIGHT_MAP)
        for item_id, qty in map_items:
            await cmd.get_map_item(item_id, qty)
        for item, monster, qty in hunts:
            await hunt_item(cmd, item, qty, TWILIGHT_MAP, monster_name=monster)
        await cmd.ensure_turn_in_quest(quest_id)

    await map_item_quest(cmd, 9262, TWILIGHT_MAP, (11751, 11752), 1)
    await kill_quest(cmd, 9263, TWILIGHT_MAP, "Decay Spirit")
    await kill_quest(cmd, 9264, TWILIGHT_MAP, "Ice Guardian")
    await map_item_quest(cmd, 9265, TWILIGHT_MAP, (11753, 11754, 11755), 1)
    await map_item_quest(cmd, TWILIGHT_LAST, TWILIGHT_MAP, 11756, 1)


YULGAR_ARIA_LAST = 9274

#: ``YulgarAria``'s hand-written quests: ``(quest, map, hunts, solo)``.
YULGAR_HANDS = (
    (9272, "sunlightzone", (("Infernal Dispersed", "Infernal Illusion", 4),
                            ("Astravian Dispersed", "Astravian Illusion", 4)),
     False),
    (9274, "twilightzone", (("Leviathan's Tendril", "Leviathan", 3),), True),
)


async def yulgar_aria(cmd: Command, sea_voice: bool = False,
                      cold_thunder: bool = False) -> None:
    """``CoreAOR.YulgarAria``: quests 9270-9274 across two zones.

    Its quests hop between /twilightzone and /sunlightzone; the map is per step,
    as the source has it.  9274 is fought in the solo class, which the source
    sets *before* accepting the quest.
    """
    if await cmd.is_completed_before(YULGAR_ARIA_LAST):
        return

    await twilight_zone(cmd, sea_voice, cold_thunder)

    await kill_quest(cmd, 9270, "twilightzone", "Polymelia Lamprey")
    await kill_quest(cmd, 9271, "sunlightzone", "Blighted Water")

    for quest_id, map_name, hunts, solo in YULGAR_HANDS:
        if await cmd.is_completed_before(quest_id):
            continue
        if solo:
            await equip_class(cmd, solo=True)
        await cmd.ensure_accept_quest(quest_id)
        for item, monster, qty in hunts:
            await hunt_item(cmd, item, qty, map_name, monster_name=monster)
        await cmd.ensure_turn_in_quest(quest_id)

    await kill_quest(cmd, 9273, "sunlightzone", "Marine Snow")


MIDNIGHT_LAST = 9301
MIDNIGHT_MAP = "midnightzone"

#: ``MidnightZone``'s hand-written quests: ``(quest, [(map item, qty)], hunts)``.
MIDNIGHT_HANDS = (
    (9293, ((11845, 1),), (("Lamprey Limb", "Polymelia Lamprey", 8),)),
    (9294, (), (("Slayer Subdued", "Vowed Shadowslayer", 8),
                ("Key Card", "Vowed Shadowslayer", 1))),
    (9295, ((11846, 1),), (("Prisoner Subdued", "Undead Prisoner", 10),)),
    (9296, ((11847, 1),), (("Bone Sample", "Undead Prisoner", 6),
                           ("Slayer's Written Vow", "Vowed Shadowslayer", 6))),
    (9297, ((11848, 3),), (("Viscera Sample", "Shadow Viscera", 6),)),
    (9299, (), (("Shadow Captured", "Shadow Viscera", 7),
                ("Wraith Appeased", "Venerated Wraith", 7))),
)
#: The boss the source fights in its solo class.
MIDNIGHT_BOSS = ("Sparagmos A.I. Defeated", "Sparagmos")


async def midnight_zone(cmd: Command, sea_voice: bool = False,
                        cold_thunder: bool = False) -> None:
    """``CoreAOR.MidnightZone``: quests 9292-9301 in /midnightzone.

    The source's lead-in is ``TwilightZone`` -- not ``YulgarAria``, the region
    before it -- so that is what this calls too.
    """
    if await cmd.is_completed_before(MIDNIGHT_LAST):
        return

    await twilight_zone(cmd, sea_voice, cold_thunder)

    await map_item_quest(cmd, 9292, MIDNIGHT_MAP, (11842, 11843, 11844), 1)

    for quest_id, map_items, hunts in MIDNIGHT_HANDS:
        if await cmd.is_completed_before(quest_id):
            continue
        await cmd.ensure_accept_quest(quest_id)
        await cmd.join_map(MIDNIGHT_MAP)
        for item_id, qty in map_items:
            await cmd.get_map_item(item_id, qty)
        for item, monster, qty in hunts:
            await hunt_item(cmd, item, qty, MIDNIGHT_MAP, monster_name=monster)
        await cmd.ensure_turn_in_quest(quest_id)

    await kill_quest(cmd, 9298, MIDNIGHT_MAP, "Venerated Wraith")
    await map_item_quest(cmd, 9300, MIDNIGHT_MAP, 11849, 4)
    await map_item_quest(cmd, 9300, MIDNIGHT_MAP, 11850, 1)

    await equip_class(cmd, solo=True)
    await cmd.ensure_accept_quest(MIDNIGHT_LAST)
    await hunt_item(cmd, MIDNIGHT_BOSS[0], 1, MIDNIGHT_MAP,
                    monster_name=MIDNIGHT_BOSS[1])
    await cmd.ensure_turn_in_quest(MIDNIGHT_LAST)


ABYSSAL_LAST = 9315
ABYSSAL_MAP = "abyssalzone"

#: ``AbyssalZone``'s hand-written quests, by quest id: ``(map items, hunts,
#: solo)``.  They are *interleaved* with plain calls in the source, so the order
#: lives in :func:`abyssal_zone` rather than in this table.
ABYSSAL_HANDS = {
    9306: (((11914, 1),), (("Shark Fin", "Kitefin Shark Bait", 8),), False),
    9309: (((11895, 3),), (("Shadow Sample", "Shadow Viscera", 7),), False),
    9310: ((), (("Shadow Organs", "Shadow Viscera", 6),
                ("Decayed Elemental Gem", "Blighted Water", 6)), False),
    9311: (((11896, 1),), (("Foamy Residue", "Foam Scavenger", 10),), False),
    9314: (((11899, 1),), (("Necro Wax", "Necro Adipocere", 3),
                            ("Scavenger Tentacle", "Foam Scavenger", 7)), False),
    9315: ((), (("The Ashray Vanquished", "The Ashray", 1),), True),
}


async def abyssal_zone(cmd: Command, sea_voice: bool = False,
                       cold_thunder: bool = False) -> None:
    """``CoreAOR.AbyssalZone``: quests 9306-9315 in /abyssalzone.

    The hand-written quests are interleaved with plain ones in the source -- 9307
    and 9312 each take two ``MapItemQuest`` calls for one quest -- so this walks
    the order explicitly.  9315 is fought in the solo class.
    """
    if await cmd.is_completed_before(ABYSSAL_LAST):
        return

    await midnight_zone(cmd, sea_voice, cold_thunder)

    async def hand(quest_id: int) -> None:
        if await cmd.is_completed_before(quest_id):
            return
        map_items, hunts, solo = ABYSSAL_HANDS[quest_id]
        if solo:
            await equip_class(cmd, solo=True)
        await cmd.ensure_accept_quest(quest_id)
        await cmd.join_map(ABYSSAL_MAP)
        for item_id, qty in map_items:
            await cmd.get_map_item(item_id, qty)
        for item, monster, qty in hunts:
            await hunt_item(cmd, item, qty, ABYSSAL_MAP, monster_name=monster)
        await cmd.ensure_turn_in_quest(quest_id)

    await hand(9306)
    await map_item_quest(cmd, 9307, ABYSSAL_MAP, 11893, 6)
    await map_item_quest(cmd, 9307, ABYSSAL_MAP, 11894, 1)
    await kill_quest(cmd, 9308, ABYSSAL_MAP, "Blighted Water")
    await hand(9309)
    await hand(9310)
    await hand(9311)
    await map_item_quest(cmd, 9312, ABYSSAL_MAP, 11897, 6)
    await map_item_quest(cmd, 9312, ABYSSAL_MAP, 11898, 1)
    await kill_quest(cmd, 9313, ABYSSAL_MAP, "Necro Adipocere")
    await hand(9314)
    await hand(9315)


DEEPWATER_LAST = 9338
DEEPWATER_MAP = "trenchobserve"

#: ``DeepWater``'s hand-written quests, by quest id: ``(map items, hunts, solo)``.
#: Interleaved with plain calls, so the order lives in :func:`deep_water`.
DEEPWATER_HANDS = {
    9329: (((11975, 1),), (("Wraith I.D Card", "Venerated Wraith", 8),), False),
    9330: (((11976, 1),), (("Turret Screws", "Seabase Turret", 8),), False),
    9333: (((11978, 4),), (("Turret Disarmed", "Seabase Turret", 6),), False),
    9337: (((11982, 1),), (("Waxen Limb", "Necro Adipocere", 3),
                            ("Spirit Stinger", "Sea Spirit", 7)), False),
    9338: ((), (("Lady Noelle Defeated", "Lady Noelle", 1),), True),
}
#: The one step the source guards with its own flag: with ``panopticonMerge`` on,
#: the region stops after 9332.
DEEPWATER_EARLY_STOP = 9332


async def deep_water(cmd: Command, panopticon_merge: bool = False,
                     sea_voice: bool = False,
                     cold_thunder: bool = False) -> None:
    """``CoreAOR.DeepWater``: quests 9329-9338 in /trenchobserve.

    Args:
        cmd (Command): Facade to act through.
        panopticon_merge (bool): The reference's ``panopticonMerge`` option; on,
            the region returns after 9332.
        sea_voice (bool): Passed to :func:`abyssal_zone`.
        cold_thunder (bool): Passed to :func:`abyssal_zone`.
    """
    if await cmd.is_completed_before(DEEPWATER_LAST):
        return

    await abyssal_zone(cmd, sea_voice, cold_thunder)

    async def hand(quest_id: int) -> None:
        if await cmd.is_completed_before(quest_id):
            return
        map_items, hunts, solo = DEEPWATER_HANDS[quest_id]
        if solo:
            await equip_class(cmd, solo=True)
        await cmd.ensure_accept_quest(quest_id)
        await cmd.join_map(DEEPWATER_MAP)
        for item_id, qty in map_items:
            await cmd.get_map_item(item_id, qty)
        for item, monster, qty in hunts:
            await hunt_item(cmd, item, qty, DEEPWATER_MAP, monster_name=monster)
        await cmd.ensure_turn_in_quest(quest_id)

    await hand(9329)
    await hand(9330)
    await map_item_quest(cmd, 9331, DEEPWATER_MAP, 11977, 4)
    await kill_quest(cmd, DEEPWATER_EARLY_STOP, DEEPWATER_MAP, "Venerated Wraith")
    if panopticon_merge:
        return

    await hand(9333)
    await map_item_quest(cmd, 9334, DEEPWATER_MAP, (11979, 11981), 1)
    await map_item_quest(cmd, 9334, DEEPWATER_MAP, 11980, 2)
    await kill_quest(cmd, 9335, DEEPWATER_MAP, "Sea Spirit")
    await kill_quest(cmd, 9336, DEEPWATER_MAP, "Necro Adipocere")
    await hand(9337)
    await hand(DEEPWATER_LAST)


SEAVOICE_LAST = 9348
SEAVOICE_MAP = "seavoice"
#: The Vigil shop and item the fight needs, as ``KillThing`` hard-codes them.
VIGIL_SHOP = 2320
VIGIL_SHOP_ITEM_ID = 12023
VIGIL = "Vigil"
VIGIL_QTY = 1000
#: ``KillThing``'s fight parameters for this region.
KILL_THING_ITEM = "Voice in the Sea Defeated"
KILL_THING_CELL, KILL_THING_PAD = "r2", "Left"
#: The aura the boss applies, and the skill slot that cleanses it.
OXIDIZE = "Oxidize"
CLEANSE_SLOT = 5


def _has_aura(cmd: Command, name: str) -> bool:
    """Whether the player carries an aura called ``name``.

    ``player.AURAS`` is what the dashboard reads, so the field is there; its
    entries are model objects (with ``name``) in some builds and plain dicts in
    others, and both shapes are accepted rather than guessing.
    """
    for aura in getattr(cmd.bot.player, "AURAS", []) or []:
        if isinstance(aura, dict):
            if str(aura.get("name", "")).lower() == name.lower():
                return True
        elif str(getattr(aura, "name", "")).lower() == name.lower():
            return True
    return False


async def kill_thing(cmd: Command, map_name: str, item: str, item_used: int,
                     quant: int = 1, is_temp: bool = False) -> None:
    """``CoreAOR.KillThing``: the Vigil fight that a boss mechanic needs.

    This is not a plain hunt.  The boss applies the ``Oxidize`` aura and only the
    equipped Vigil cleanses it, through skill slot 5; that is why the reference
    buys a thousand Vigils, equips one, holds cell ``r2/Left`` and drives the
    skills itself instead of using its usual combat loop.

    Where this engine cannot follow, it says so: ``SetSpawnPoint()`` is not
    ported (a stopped decision -- it only changes where you come back after a
    death), and there is no ``Skills.Stop()/Resume()`` pair because the skills
    here are cast by this loop alone.

    Args:
        cmd (Command): Facade to act through.
        map_name (str): Map the fight is in.
        item (str): What the fight drops (a temp item, hence ``is_temp``).
        item_used (int): Item id to equip -- the Vigil.
        quant (int): How many of ``item``.
        is_temp (bool): Whether ``item`` lands in the temp bag.
    """
    await cmd.join_map(map_name)
    await buy_item(cmd, VIGIL_SHOP, VIGIL, VIGIL_QTY, map_name=map_name,
                   shop_item_id=VIGIL_SHOP_ITEM_ID)

    held = cmd.bot.player.get_item_inventory_by_id(item_used)
    if held is not None and getattr(held, "item_name", ""):
        await cmd.equip_item(held.item_name)
        cmd.bot.log(f"{item_used} [Vigil] equipped")
    else:
        cmd.bot.log(f"[aor] item id {item_used} (the Vigil) is not in the "
                    f"inventory; the fight will go badly without it.")

    while cmd.is_still_connected() and cmd.is_not_in_cell(KILL_THING_CELL):
        await cmd.jump_cell(KILL_THING_CELL, KILL_THING_PAD)
        await cmd.sleep(500)

    while cmd.is_still_connected() and not await cmd.has_item(item, quant,
                                                              isTemp=is_temp):
        if not cmd.is_player_alive():
            while cmd.is_still_connected() and not cmd.is_player_alive():
                await cmd.sleep(500)
            continue
        if cmd.is_not_in_cell(KILL_THING_CELL):
            await cmd.jump_cell(KILL_THING_CELL, KILL_THING_PAD)
        if _has_aura(cmd, OXIDIZE) and not _has_aura(cmd, VIGIL):
            await cmd.use_skill(CLEANSE_SLOT, "*")
        await cmd.use_next_skill([0, 1, 2, 3, 4], "*")
        await cmd.sleep(200)

    cmd.bot.log(f"KillThing completed for {item} ({quant}).")


async def sea_voice(cmd: Command) -> None:
    """``CoreAOR.SeaVoice``: quest 9348 in /seavoice, the Vigil fight.

    The last region the seven Kathool merge shops wait on.  Its lead-in is
    ``SoW.ManaCradle`` + ``DeepWater``, both ported.
    """
    if await cmd.is_completed_before(SEAVOICE_LAST):
        return

    await mana_cradle(cmd)
    await deep_water(cmd)

    await cmd.ensure_accept_quest(SEAVOICE_LAST)
    await kill_thing(cmd, SEAVOICE_MAP, KILL_THING_ITEM, VIGIL, is_temp=True)
    await cmd.ensure_turn_in_quest(SEAVOICE_LAST)
    await cmd.sell_item(VIGIL, VIGIL_QTY)
