"""``Core13LoC`` -- the thirteen Lords of Chaos, five of them so far.

Port of ``Story/LordsofChaos/Core13LoC.cs``.  The forge enhancement unlocks need
``Escherion()``, the Farmer Joe kit needs the whole chain, so the file is being
filled in segment by segment: ``Prologue``, ``Escherion``, ``Kitsune`` and
``Lionfang`` are here, and :func:`complete13loc` walks the source's order and
stops -- by name -- at the first segment that is not ported yet.

Note that this is *not* ``CoreNation.KillEscherion`` -- same target, different
class, different job: this one is the whole /mobius story.

``Story.PreLoad`` has no counterpart here; the guards do its work.
"""
from typing import Optional, Sequence, Tuple, Union

from bot.core_advanced import buy_item as adv_buy_item
from bot.core_bots import (Alignment, buy_item, chain_complete,
                           change_alignment, equip_class, kill_once,
                           parse_message, wait_for_item)
from bot.core_story import (chain_quest, item_id_by_name, kill_quest,
                            map_item_quest, quest_progression)
from core.command import Command
from bot.nation.core_nation import kill_escherion
from templates.hunt import hunt_item, hunt_item_by_id

# ---------------------------------------------------------------------------
# Prologue -- quests 183-6219, from /battleundera to /forestchaos
# ---------------------------------------------------------------------------
PROLOGUE_LAST = 6219
#: ``CoreBots.HeroAlignment``'s default -- ``Alignment.Evil`` (2).  The source
#: then sends ``HeroAlignment > 1 ? 1 : HeroAlignment``, which is **1**, so its
#: alignment packet declares Good.  Kept as it stands.
HERO_ALIGNMENT = 2
#: The two cutscene packets the source sends by hand before quest 195.
DRAKATH_PACKET = "%xt%zm%updateQuest%73922%43%1%"
CLASS_QUEST = 41
DRAKATH_QUEST_PACKET = "%xt%zm%updateQuest%188220%41%{value}%"
PROLOGUE_HERO_CELL = ("King2", "Center")
#: ``Story.MapItemQuest(179, "castleundead", 38, 5)``, and 6216's five map items.
KNIGHTS_MAP_ITEM = 38
KNIGHTS_MAP_ITEM_QTY = 5
UNLIFE_MAP_ITEM = 39
UNLIFE_MAP_ITEM_QTY = 5
UNLIFE_SHOP = 1559
UNLIFE_ITEM = 42993
#: ``Story.MapItemQuest(6217, "chaoscrypt", 5662)``.
CRYPT_MAP_ITEM = 5662


async def prologue(cmd: Command) -> None:
    """``Core13LoC.Prologue``: quests 183-6219.

    Three steps the source writes out by hand keep their own blocks (176, 6216,
    6219), and so does the Drakath cutscene: a socket client cannot watch a
    cutscene, so the source's own ``updateQuest`` packets are sent instead and
    ``ChainQuest(195)`` plays the part of "the scene finished".
    """
    if await cmd.is_completed_before(PROLOGUE_LAST):
        return

    # Enter the gates
    await kill_quest(cmd, 183, "battleundera", "Skeletal Fire Mage")

    # Undead Assault 176
    if not await cmd.is_completed_before(176):
        if await cmd.ensure_accept_quest(176) is False:
            cmd.bot.log("[13loc] quest 176 could not be accepted; the prologue "
                        "stops here.")
            return
        await hunt_item(cmd, "Slain Skeletal Soldier", 5, "swordhavenundead",
                        monster_name="Skeletal Soldier")
        await cmd.ensure_turn_in_quest(176)

    await kill_quest(cmd, 177, "swordhavenundead", "Skeletal Ice Mage")
    await kill_quest(cmd, 178, "swordhavenundead", "Undead Giant")
    await map_item_quest(cmd, 179, "castleundead", KNIGHTS_MAP_ITEM,
                         KNIGHTS_MAP_ITEM_QTY)
    await kill_quest(cmd, 180, "castleundead", "Skeletal Viking")

    # The Arrival of Drakath cutscene.  ``Bot.Quests.IsUnlocked(196)`` has no
    # client to ask here, so "not completed yet" stands in for it -- the same
    # substitution ``bot/enhancements/lacerate.py`` documents.
    if not await cmd.is_completed_before(196):
        await cmd.join_map("castleundead")
        await cmd.jump_cell(*PROLOGUE_HERO_CELL)
        await cmd.join_map("shadowfall")
        await cmd.send_packet(DRAKATH_PACKET)
        await cmd.send_packet(DRAKATH_QUEST_PACKET.format(
            value=1 if HERO_ALIGNMENT > 1 else HERO_ALIGNMENT))
        await cmd.sleep(2000)
        await cmd.join_map("shadowfall")
        await cmd.sleep(2000)
        # ShadowFall Quest1 195
        await chain_quest(cmd, 195)

    # Recover Sepulchure's Cursed Armor! 196
    await kill_quest(cmd, 196, "chaoscrypt", "Chaorrupted Armor")

    # Unlife Insurance 6216
    if not await cmd.is_completed_before(6216):
        if await cmd.ensure_accept_quest(6216) is False:
            cmd.bot.log("[13loc] quest 6216 could not be accepted; the prologue "
                        "stops here.")
            return
        await cmd.join_map("prison")
        await cmd.get_map_item(UNLIFE_MAP_ITEM, UNLIFE_MAP_ITEM_QTY)
        await buy_item(cmd, UNLIFE_SHOP, UNLIFE_ITEM, map_name="prison")
        await cmd.ensure_turn_in_quest(6216)

    # Enter the Crypt 6217
    await map_item_quest(cmd, 6217, "chaoscrypt", CRYPT_MAP_ITEM)

    # Rescue the Knights 6218
    await kill_quest(cmd, 6218, "chaoscrypt", "Chaorrupted Knight")

    # Forest of Chaos 6219
    if not await cmd.is_completed_before(PROLOGUE_LAST):
        if await cmd.ensure_accept_quest(PROLOGUE_LAST) is False:
            cmd.bot.log(f"[13loc] quest {PROLOGUE_LAST} could not be accepted; "
                        f"the prologue stops here.")
            return
        await hunt_item(cmd, "Chaorrupted Bear Defeated", 1, "forestchaos",
                        monster_name="Chaorrupted Bear")
        await hunt_item(cmd, "Chaorrupted Wolf Defeated", 7, "forestchaos",
                        monster_name="Chaorrupted Wolf")
        await cmd.ensure_turn_in_quest(PROLOGUE_LAST)


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


VATH_LAST = 363
#: The /dwarfhold key hunt: quest 340 grants the temp key the next step needs.
VATH_KEY_QUEST = 340
VATH_KEY = "Upper City Key"
VATH_KEY_ITEM = "Block of Talc"
#: Quest 353's three drops, in the order the source re-farms them.
VATH_THERMITE = "Thermite"
VATH_353 = (("Balboa Core", "Balboa", 4),
            ("Magnesium Flare", "Chaos Drow", 1),
            ("Rusted Claw", "Albino Bat", 3))
#: Quest 356's three drops.
VATH_356 = (("Nitrate Elements", "Albino Bat", 3),
            ("Drow Shoelaces", "Chaos Drow", 3),
            ("Flint Stone", "Balboa", 2))


async def _wait_temp(cmd: Command, name: str,
                     timeout_ms: int = 20000) -> bool:
    """``Bot.Wait.ForTrue(() => Bot.TempInv.Contains(name), 20)``."""
    waited = 0
    while cmd.is_still_connected() and waited < timeout_ms:
        if cmd.is_in_inventory(name, 1, ">=", True):
            return True
        await cmd.sleep(500)
        waited += 500
    return cmd.is_in_inventory(name, 1, ">=", True)


async def _vath_353(cmd: Command) -> None:
    """Quest 353, which both ``Mock the Lock`` and ``Like Butter`` re-farm."""
    if await cmd.ensure_accept_quest(353) is False:
        cmd.bot.log("[13loc] quest 353 could not be accepted; Vath stops here.")
        return
    for item, monster, qty in VATH_353:
        await hunt_item(cmd, item, qty, "dwarfprison", monster_name=monster)
    await cmd.ensure_turn_in_quest(353)


async def _vath_356(cmd: Command) -> None:
    """Quest 356's three drops, shared by ``Explosives 101`` and ``Big Bada-Boom``."""
    if await cmd.ensure_accept_quest(356) is False:
        cmd.bot.log("[13loc] quest 356 could not be accepted; Vath stops here.")
        return
    for item, monster, qty in VATH_356:
        await hunt_item(cmd, item, qty, "dwarfprison", monster_name=monster)
    await cmd.ensure_turn_in_quest(356)


async def vath(cmd: Command) -> None:
    """``Core13LoC.Vath``: quests 319-363, from /pines to /stalagbite.

    Two source structures are kept as they are: the ``Getkey`` label is a loop
    that re-runs quest 340 until the temporary ``Upper City Key`` exists, and
    quest 353/356 are farmed twice (once for themselves, once as the ingredient
    the next quest's ``CheckInventory`` looks for).

    ``Bot.Quests.UpdateQuest`` has no counterpart -- it writes the *client's* quest
    slot, and this engine has no client.  The two places the source uses it (354
    and 357) are the cutscene gates; the work around them -- the kills, the joins
    and the turn-ins -- is what actually moves the chain, so that is what runs.
    """
    if await cmd.is_completed_before(VATH_LAST):
        return

    cmd.add_drop("Snowbeard's Gold")

    # Adorable Sisters 319
    await map_item_quest(cmd, 319, "tavern", 56, 7)
    # Warm and Furry 320 .. Leather Feathers 326
    await kill_quest(cmd, 320, "pines", "Pine Grizzly")
    await kill_quest(cmd, 321, "pines", "Red Shell Turtle")
    await kill_quest(cmd, 322, "pines", "Twistedtooth")
    await kill_quest(cmd, 324, "pines", "Red Shell Turtle")
    await kill_quest(cmd, 325, "pines", "Pine Grizzly")
    await kill_quest(cmd, 326, "pines", "LeatherWing")

    # Follow your Nose! 327, then Give Snowbeard His Gold 323
    if (not await quest_progression(cmd, 327)
            or not await cmd.is_completed_before(323)):
        if await cmd.ensure_accept_quest(327) is False:
            cmd.bot.log("[13loc] quest 327 could not be accepted; Vath stops "
                        "here.")
            return
        await hunt_item(cmd, "Pine Air Freshener", 1, "pines",
                        monster_name="Pine Troll")
        await cmd.ensure_turn_in_quest(327)
        await wait_for_item(cmd, "Snowbeard's Gold")
        await chain_complete(cmd, 323)

    # Bad Memory 344
    await map_item_quest(cmd, 344, "dwarfhold", 60)
    # Squeeze Water from Stone 331 .. Gemeralds 339
    await kill_quest(cmd, 331, "mountainpath", "Ore Balboa")
    await kill_quest(cmd, 332, "mountainpath", "Vultragon")
    await kill_quest(cmd, 333, "dwarfhold", "Chaos Drow")
    await kill_quest(cmd, 334, "dwarfhold", "Glow Worm")
    await kill_quest(cmd, 335, "dwarfhold", "Albino Bat")
    await kill_quest(cmd, 336, "dwarfhold", "Chaotic Draconian")
    await map_item_quest(cmd, 337, "dwarfhold", 59, 7)
    await kill_quest(cmd, 338, "dwarfhold", "Chaos Drow")
    await kill_quest(cmd, 339, "dwarfhold", "Chaotic Draconian")

    # Talc to Me 340 -- the source's ``Getkey`` label: loop until the key exists
    guard = cmd.pass_guard(f'"{VATH_KEY}" (quest {VATH_KEY_QUEST})')
    while (cmd.is_still_connected()
           and not cmd.is_in_inventory(VATH_KEY, 1, ">=", True)):
        cmd.add_drop(VATH_KEY)
        if await cmd.ensure_accept_quest(VATH_KEY_QUEST) is False:
            cmd.bot.log(f"[13loc] quest {VATH_KEY_QUEST} could not be accepted; "
                        f"Vath stops here.")
            return
        await hunt_item(cmd, VATH_KEY_ITEM, 1, "dwarfhold",
                        monster_name="Albino Bat")
        await cmd.ensure_turn_in_quest(VATH_KEY_QUEST)
        if not await _wait_temp(cmd, VATH_KEY):
            if not await guard.tick():
                break

    # Upper City Gates 343, then Rock me Amadeus 341
    await chain_complete(cmd, 343)
    if await cmd.ensure_accept_quest(341) is False:
        cmd.bot.log("[13loc] quest 341 could not be accepted; Vath stops here.")
        return
    await hunt_item(cmd, "Key Mold", 1, "dwarfhold", monster_name="Amadeus")
    await cmd.ensure_turn_in_quest(341)

    # Disapoofed 346 .. Lizard Gizzard 352
    await map_item_quest(cmd, 346, "uppercity", 61)
    await kill_quest(cmd, 347, "uppercity", "Drow Assassin")
    await kill_quest(cmd, 348, "uppercity", "Chaotic Draconian")
    await kill_quest(cmd, 349, "uppercity", "Chaos Egg")
    await kill_quest(cmd, 350, "uppercity", "Terradactyl")
    await kill_quest(cmd, 351, "uppercity", "Rhino Beetle")
    await kill_quest(cmd, 352, "uppercity", "Cave Lizard")

    # Mock the Lock 353 -- ``if (!Bot.Quests.IsUnlocked(354))``
    if not await cmd.is_completed_before(354):
        cmd.add_drop(VATH_THERMITE)
        await _vath_353(cmd)

    # Like Butter 354
    if not await quest_progression(cmd, 354):
        cmd.add_drop(VATH_THERMITE)
        await cmd.join_map("vath")
        await cmd.jump_cell("CutCap", "Left")
        await cmd.sleep(2500)
        if not await cmd.has_item(VATH_THERMITE):
            await _vath_353(cmd)
        await cmd.join_map("dwarfprison")
        await cmd.jump_cell("Enter", "Right")
        await cmd.ensure_turn_in_quest(354)

    # Jailhouse Rock 355
    await kill_quest(cmd, 355, "dwarfprison", "Warden Elfis")

    # Explosives 101 356
    if not await quest_progression(cmd, 356):
        await _vath_356(cmd)

    # Big Bada-Boom 357
    if not await quest_progression(cmd, 357):
        if not await cmd.has_item("Tee-En-Tee"):
            await _vath_356(cmd)
        await cmd.join_map("dwarfprison")
        await chain_quest(cmd, 357)

    # Defeat Rock Roc 362, Facing Vath 363
    await map_item_quest(cmd, 362, "roc", 62)
    await map_item_quest(cmd, 363, "stalagbite", 63)


KITSUNE_LAST = 488

#: Quest 470's five monsters, by the map id the source names: ``(map id, item,
#: how many)``.  The item is named there, and this engine farms by id, so the id
#: comes from the quest's own payload -- see ``core_story.item_id_by_name``.
JUNKYARD_BY_ID = ((1, "Wild Kara-Kasa", 5),
                  (4, "Wild Bura-Bura", 4),
                  (3, "Wild Biwa-Bokuboku", 3),
                  (6, "Wild Koto-Furunushi", 2),
                  (2, "Wild Bakezouri", 1))

#: Quest 474's three Kappa Ninja drops plus the map item, in the source's order.
KAPPA_ITEMS = (("Dried Nori Leaf", 6),
               ("Sumeshi Bundle", 3),
               ("Fresh Cucumber", 1))
KAPPA_MAP_ITEM = 92


async def kitsune(cmd: Command) -> None:
    """``Core13LoC.Kitsune``: quests 380-488 across seven maps.

    The seven quests the source writes out by hand (380, 381, 402, 403, 405, 470,
    474) keep their own blocks, in place; the rest go through the same two
    helpers ``escherion`` uses.
    """
    if await cmd.is_completed_before(KITSUNE_LAST):
        return

    # Turtle Power 380
    if not await cmd.is_completed_before(380):
        await map_item_quest(cmd, 380, "yokaiboat", 64, 1)
        await cmd.ensure_accept_quest(380)
        await hunt_item(cmd, "Kappa Ninja Slain", 7, "yokaiboat",
                        monster_name="Kappa Ninja")
        await cmd.ensure_turn_in_quest(380)

    # Setting Sail to Yokai 381
    if not await cmd.is_completed_before(381):
        await cmd.ensure_accept_quest(381)
        await hunt_item(cmd, "Sail Permit", 1, "yokaiboat", cell="r4",
                        pad="Spawn", monster_name="*")
        await cmd.ensure_turn_in_quest(381)

    await kill_quest(cmd, 382, "dragonkoi", "Ryoku")

    # Dog Days 402
    if not await cmd.is_completed_before(402):
        await cmd.ensure_accept_quest(402)
        await hunt_item(cmd, "Samurai Questioned", 5, "hachiko",
                        monster_name="Samurai Nopperabo")
        await hunt_item(cmd, "Ninja Questioned", 5, "hachiko",
                        monster_name="Ninja Nopperabo")
        await cmd.ensure_turn_in_quest(402)

    # Faceless Threat 403
    if not await cmd.is_completed_before(403):
        await cmd.ensure_accept_quest(403)
        await hunt_item(cmd, "Note from DT", 1, "hachiko", cell="Ox",
                        pad="Center", monster_name="Samurai Nopperabo")
        await cmd.ensure_turn_in_quest(403)

    # Zodiac Puzzle Key 405
    if not await cmd.is_completed_before(405):
        await cmd.ensure_accept_quest(405)
        for cell, monster, piece in (
                ("Tiger", "Samurai Nopperabo", "Rat-Ox-Tiger Piece"),
                ("Snake", "Ninja Nopperabo", "Rabbit-Dragon-Snake piece"),
                ("Horse", "Samurai Nopperabo", "Horse-Sheep-Monkey piece"),
                ("Pig", "Ninja Nopperabo", "Rooster-Dog-Pig Piece")):
            await hunt_item(cmd, piece, 1, "hachiko", cell=cell, pad="Center",
                            monster_name=monster)
        await cmd.ensure_turn_in_quest(405)

    await kill_quest(cmd, 406, "hachiko", "Dai Tengu")
    await map_item_quest(cmd, 466, "bamboo", 90, 1)
    await kill_quest(cmd, 467, "bamboo", ["Tanuki", "Tanuki"])
    await kill_quest(cmd, 468, "bamboo", "SoulTaker")
    await map_item_quest(cmd, 469, "junkyard", 91, 1)

    # Reduce, Respawn, Recycle 470 -- five monsters, each by its own map id
    if not await cmd.is_completed_before(470):
        await cmd.ensure_accept_quest(470)
        for monster_map_id, item, qty in JUNKYARD_BY_ID:
            item_id = item_id_by_name(cmd, 470, item)
            if item_id is None:
                cmd.bot.log(f"[story] quest 470 does not name {item!r}; the "
                            f"/junkyard pass stops here.")
                return
            await hunt_item_by_id(cmd, item_id, qty, "junkyard",
                                  monster_map_id=monster_map_id)
        await cmd.ensure_turn_in_quest(470)

    await kill_quest(cmd, 471, "junkyard", "Onibaba")
    await kill_quest(cmd, 473, "yokairiver",
                     ["Funa-Yurei", "Funa-Yurei", "Funa-Yurei"])

    # Kappa Cuisine 474
    if not await cmd.is_completed_before(474):
        await cmd.ensure_accept_quest(474)
        for item, qty in KAPPA_ITEMS:
            await hunt_item(cmd, item, qty, "yokairiver", cell="r4", pad="Left",
                            monster_name="Kappa Ninja")
        if cmd.is_not_in_map("yokairiver"):
            await cmd.join_map("yokairiver")
        await cmd.get_map_item(KAPPA_MAP_ITEM)
        await cmd.ensure_turn_in_quest(474)

    await kill_quest(cmd, 476, "yokairiver", "Nure Onna")
    await kill_quest(cmd, 477, "yokaigrave", "Skello Kitty")
    await kill_quest(cmd, 478, "yokaigrave",
                     ["Ninja Nopperabo", "Samurai Nopperabo"])
    await kill_quest(cmd, 479, "yokaigrave", "Neko Mata")
    await kill_quest(cmd, 481, "odokuro", "O-dokuro")
    await kill_quest(cmd, 484, "yokaiwar", "O-Dokuro's Head")
    await kill_quest(cmd, 488, "kitsune", "kitsune")


WOLFWING_LAST = 597
#: ``Red's Big Wolf Slaying Axe`` -- quest 515's reward, and what 514 turns in.
WOLFWING_AXE = "Red's Big Wolf Slaying Axe"
#: Quests 514/515's five documents, in the source's order.
WOLFWING_DOCS = (("Spider Documentation", "greenguardeast", "Spider", None),
                 ("Wolf Documentation", "greenguardeast", "Wolf", None),
                 ("Slime Documentation", "greenguardwest", "Slime", None),
                 ("Frogzard Documentation", "greenguardwest", "Frogzard", None),
                 ("Wereboar Documentation", "greenguardwest", "Big Bad Boar",
                  ("West12", "Up")))


async def wolfwing(cmd: Command) -> None:
    """``Core13LoC.Wolfwing``: quests 308-597, from /darkoviagrave to /chaoscave.

    The two ``Bot.Quests.UpdateQuest`` calls have no counterpart (they write the
    client's quest slot); the kills and turn-ins around them are what the chain
    actually needs, so those run.  The last step declares Good before chaining
    597, as the source does when ``HeroAlignment != 1``.
    """
    if (await cmd.is_completed_before(WOLFWING_LAST)
            or await cmd.is_completed_before(598)):
        return

    cmd.add_drop(WOLFWING_AXE)

    # Grave Mission 494 .. His Bark is worse than his Blight 498
    await map_item_quest(cmd, 494, "darkoviagrave", 97)
    await kill_quest(cmd, 495, "darkoviagrave", "Skeletal Fire Mage")
    await kill_quest(cmd, 496, "darkoviagrave", "Rattlebones")
    await kill_quest(cmd, 497, "darkoviagrave", "Albino Bat")
    await kill_quest(cmd, 498, "darkoviagrave", "Blightfang")
    # Vicious Wolves 308 .. Overgrown Spiders 311
    await kill_quest(cmd, 308, "greenguardeast", "Wolf")
    await kill_quest(cmd, 309, "greenguardwest", "Slime")
    await kill_quest(cmd, 310, "greenguardwest", "Frogzard")
    await kill_quest(cmd, 311, "greenguardeast", "Spider")

    # Lil' Red 514 + Can I axe you something? 515
    if not await cmd.is_completed_before(516):
        cmd.add_drop(WOLFWING_AXE)
        if await cmd.ensure_accept_quest(514) is False:
            cmd.bot.log("[13loc] quest 514 could not be accepted; Wolfwing "
                        "stops here.")
            return
        if await cmd.ensure_accept_quest(515) is False:
            cmd.bot.log("[13loc] quest 515 could not be accepted; Wolfwing "
                        "stops here.")
            return
        for item, map_name, monster, cell in WOLFWING_DOCS:
            if cell is None:
                await hunt_item(cmd, item, 1, map_name, monster_name=monster)
            else:
                await hunt_item(cmd, item, 1, map_name, cell=cell[0],
                                pad=cell[1], monster_name=monster)
        await cmd.ensure_turn_in_quest(515)
        await wait_for_item(cmd, WOLFWING_AXE)
        await cmd.ensure_turn_in_quest(514)

    # A Dire Situation 516 .. Twisted Paw 522
    await kill_quest(cmd, 516, "darkoviaforest", "Dire Wolf")

    # Blood, Sweat, and Tears 517
    if not await quest_progression(cmd, 517):
        if await cmd.ensure_accept_quest(517) is False:
            cmd.bot.log("[13loc] quest 517 could not be accepted; Wolfwing "
                        "stops here.")
            return
        await hunt_item(cmd, "Vial of Blood", 3, "darkoviaforest",
                        monster_name="Blood Maggot")
        await hunt_item(cmd, "Vial of Sweat", 2, "darkoviaforest",
                        monster_name="Blood Maggot")
        await hunt_item(cmd, "Vial of Tears", 1, "darkoviaforest",
                        monster_name="Blood Maggot")
        await cmd.ensure_turn_in_quest(517)

    await kill_quest(cmd, 518, "darkoviaforest", "Lich of the Stone")
    await kill_quest(cmd, 519, "safiria", "Blood Maggot")
    await kill_quest(cmd, 520, "safiria", "Albino Bat")
    await kill_quest(cmd, 521, "safiria", "Chaos Lycan")
    await kill_quest(cmd, 522, "safiria", "Twisted Paw")

    # A Gift Of Meat 534
    await kill_quest(cmd, 534, "lycan", "Dire Wolf")

    # No Respect 535
    if not await quest_progression(cmd, 535):
        if await cmd.ensure_accept_quest(535) is False:
            cmd.bot.log("[13loc] quest 535 could not be accepted; Wolfwing "
                        "stops here.")
            return
        await hunt_item(cmd, "Lycan Knight Defeated", 2, "lycan",
                        monster_name="Lycan Knight")
        await hunt_item(cmd, "Lycan Defeated", 5, "lycan", monster_name="Lycan")
        await cmd.ensure_turn_in_quest(535)

    # Vampire Knights 536, Sanguine 537
    await kill_quest(cmd, 536, "lycan", "Chaos Vampire Knight")

    if not await quest_progression(cmd, 537):
        if await cmd.ensure_accept_quest(537) is False:
            cmd.bot.log("[13loc] quest 537 could not be accepted; Wolfwing "
                        "stops here.")
            return
        await hunt_item(cmd, "Sanguine Mask", 1, "lycan",
                        monster_name="Sanguine")
        await cmd.ensure_turn_in_quest(537)

    # War Boss Fight 552
    await chain_quest(cmd, 552)

    # Search and Report 564
    if not await quest_progression(cmd, 564):
        if await cmd.ensure_accept_quest(564) is False:
            cmd.bot.log("[13loc] quest 564 could not be accepted; Wolfwing "
                        "stops here.")
            return
        await kill_once(cmd, "lycanwar", "Boss", "Left", "Edvard")
        await cmd.sleep(5000)
        await map_item_quest(cmd, 564, "chaoscave", 107)

    # The Key is the Key 565
    await kill_quest(cmd, 565, "chaoscave", "Werepyre")

    # Secret Words 566
    if not await quest_progression(cmd, 566):
        if await cmd.ensure_accept_quest(566) is False:
            cmd.bot.log("[13loc] quest 566 could not be accepted; Wolfwing "
                        "stops here.")
            return
        await hunt_item(cmd, "Secret Words", 1, "chaoscave", cell="r3",
                        pad="Left", monster_name="Werepyre")
        await cmd.ensure_turn_in_quest(566)

    # DracoWerePyre 567
    if not await quest_progression(cmd, 567):
        if await cmd.ensure_accept_quest(567) is False:
            cmd.bot.log("[13loc] quest 567 could not be accepted; Wolfwing "
                        "stops here.")
            return
        await hunt_item(cmd, "DracoWerePyre Defeated", 1, "chaoscave",
                        cell="r5", pad="Left", monster_name="DracoWerePyre")
        await cmd.ensure_turn_in_quest(567)

    # Wolfwing 597
    if not await quest_progression(cmd, WOLFWING_LAST):
        if HERO_ALIGNMENT != Alignment.GOOD.value:
            await change_alignment(cmd, Alignment.GOOD)
        await chain_quest(cmd, WOLFWING_LAST)


KIMBERLY_LAST = 710
#: Quest 660's drop: a cell-wide kill in /beehive, no monster filter.
KIMBERLY_NO_SHOES = ("beehive", "r6", "Right", "*")
#: Quest 676's monster really is spelled with a trailing space in the source.
KIMBERLY_CANNON = "Pachelbel's Cannon "


async def kimberly(cmd: Command) -> None:
    """``Core13LoC.Kimberly``: quests 648-710, from /stairway to /palooza."""
    if await cmd.is_completed_before(KIMBERLY_LAST):
        return

    # Stairway to Heaven 648
    if not await quest_progression(cmd, 648):
        if await cmd.ensure_accept_quest(648) is False:
            cmd.bot.log("[13loc] quest 648 could not be accepted; Kimberly "
                        "stops here.")
            return
        await hunt_item(cmd, "Grateful Undead Shirt", 4, "stairway",
                        monster_name="Grateful Undead")
        await hunt_item(cmd, "Rock Lobster Tail", 4, "stairway",
                        monster_name="Rock Lobster")
        await cmd.ensure_turn_in_quest(648)

    # Rolling Stones 649, Light My Fire 650
    await kill_quest(cmd, 649, "stairway", "Rock Lobster")
    await kill_quest(cmd, 650, "stairway", "Grateful Undead")

    # Knockin' on Haven's Door 651
    if not await quest_progression(cmd, 651):
        if await cmd.ensure_accept_quest(651) is False:
            cmd.bot.log("[13loc] quest 651 could not be accepted; Kimberly "
                        "stops here.")
            return
        await hunt_item(cmd, "Defeated Elwood", 1, "stairway",
                        monster_name="Elwood Bruise")
        await hunt_item(cmd, "Defeated Jake", 1, "stairway",
                        monster_name="Jake Bruise")
        await cmd.ensure_turn_in_quest(651)

    # Staying Alive 658, Killer Queen 659
    await kill_quest(cmd, 658, "beehive", "Stinger")
    await kill_quest(cmd, 659, "beehive", "Killer Queen Bee")

    # Satisfaction 660
    if not await quest_progression(cmd, 660):
        if await cmd.ensure_accept_quest(660) is False:
            cmd.bot.log("[13loc] quest 660 could not be accepted; Kimberly "
                        "stops here.")
            return
        map_name, cell, pad, monster = KIMBERLY_NO_SHOES
        await hunt_item(cmd, "No Shoes!", 1, map_name, cell=cell, pad=pad,
                        monster_name=monster)
        await cmd.ensure_turn_in_quest(660)

    # Dance with Great Godfather of Souls 661
    if not await quest_progression(cmd, 661):
        await cmd.join_map("beehive")
        await chain_quest(cmd, 661)

    # Bad Moon Rising 675
    if not await quest_progression(cmd, 675):
        if await cmd.ensure_accept_quest(675) is False:
            cmd.bot.log("[13loc] quest 675 could not be accepted; Kimberly "
                        "stops here.")
            return
        await hunt_item(cmd, "Fire Flea", 15, "orchestra", cell="R7", pad="Down",
                        monster_name="Mozard")
        await cmd.ensure_turn_in_quest(675)

    # Burning Down The House 676
    if not await quest_progression(cmd, 676):
        if await cmd.ensure_accept_quest(676) is False:
            cmd.bot.log("[13loc] quest 676 could not be accepted; Kimberly "
                        "stops here.")
            return
        await hunt_item(cmd, "Cannon Powder", 1, "orchestra", cell="R4",
                        pad="Down", monster_name=KIMBERLY_CANNON)
        await cmd.ensure_turn_in_quest(676)

    # Superstition 677, Soul Man 678
    await kill_quest(cmd, 677, "orchestra", "Mozard")
    await kill_quest(cmd, 678, "orchestra", "Faust")

    # Great gig in the Sky 4827
    if not await quest_progression(cmd, 4827):
        if await cmd.ensure_accept_quest(4827) is False:
            cmd.bot.log("[13loc] quest 4827 could not be accepted; Kimberly "
                        "stops here.")
            return
        await hunt_item(cmd, "Lobster Rocked", 5, "stairway",
                        monster_name="Rock Lobster")
        await hunt_item(cmd, "Ungrateful Undead", 5, "stairway",
                        monster_name="Grateful Undead")
        await cmd.ensure_turn_in_quest(4827)

    # Mythsong War Cutscene 707
    await chain_quest(cmd, 707)

    # Pony Gary Yellow 709
    if not await quest_progression(cmd, 709):
        if await cmd.ensure_accept_quest(709) is False:
            cmd.bot.log("[13loc] quest 709 could not be accepted; Kimberly "
                        "stops here.")
            return
        await hunt_item(cmd, "Pony Gary Yellow Defeated", 1, "palooza",
                        monster_name="Pony Gary Yellow")
        await cmd.ensure_turn_in_quest(709)

    # Kimberly 710
    if not await quest_progression(cmd, KIMBERLY_LAST):
        if await cmd.ensure_accept_quest(KIMBERLY_LAST) is False:
            cmd.bot.log("[13loc] quest 710 could not be accepted; Kimberly "
                        "stops here.")
            return
        await hunt_item(cmd, "Kimberly Defeated", 1, "palooza",
                        monster_name="Kimberly")
        await cmd.ensure_turn_in_quest(KIMBERLY_LAST)


LEDGERMAYNE_LAST = 847
LEDGERMAYNE_MAP = "ledgermayne"
#: ``LedgermayneZoneListener``'s walk targets: ``zoneSet`` -> ``(x, y)``.
LEDGERMAYNE_WALKS = {"A": (292, 355), "B": (750, 350), "": (592, 250)}
#: Quest 810 sells this one back before buying the sack from /embersea 1100.
LEDGERMAYNE_SELL_ITEM = 43280
LEDGERMAYNE_SHOP = 1100
LEDGERMAYNE_SHOP_ITEM = 5572
LEDGERMAYNE_SHOP_ITEM_ID = 17967
LEDGERMAYNE_SACK_ITEM = 141
LEDGERMAYNE_SACK_QTY = 3
#: Quest 845's five orbs, one per map.
LEDGERMAYNE_ORBS = (("mafic", "Mafic Dragon", "Astral Orb of Mafic"),
                    ("cloister", "Wendigo", "Astral Orb of the Cloister"),
                    ("mudluk", "Tiger Leech", "Astral Orb of Mudluk"),
                    ("natatorium", "Nessie", "Astral Orb of Natatorium"),
                    ("gilead", "Mana Elemental", "Astral Orb of Gilead"))

#: ``ExtensionPacketReceived`` in the reference is handed
#: ``packet["params"]["dataObj"]`` once ``params.type == "json"``.  A subscriber
#: here is handed the raw message instead, so :func:`bot.core_bots.parse_message`
#: unwraps the very same object (``b.o`` is that ``dataObj``) and the reference's
#: three checks -- ``cmd == "event"``, an ``args`` block, and ``zoneSet`` -- are
#: made on it.  This is the shape ``bot/ultra/core_ultra.py`` already reads its
#: own ``zoneSet`` with.
#:
#: A ``%xt%`` frame parses to nothing here and is ignored -- which is exactly what
#: the reference does with a packet whose ``params.type`` is not ``"json"``.
def ledgermayne_zone(message) -> Optional[str]:
    """The ``zoneSet`` of an ``event`` frame, or None when it names none."""
    data = parse_message(message)
    if not data or data.get("cmd") != "event":
        return None
    zone = (data.get("args") or {}).get("zoneSet")
    return None if zone is None else str(zone)


def ledgermayne_walk(message):
    """``(x, y)`` for a ``zoneSet`` event frame, or None for anything else."""
    zone = ledgermayne_zone(message)
    if zone is None:
        return None
    return LEDGERMAYNE_WALKS.get(zone)


def _ledgermayne_listener(cmd: Command, message: str) -> None:
    """``LedgermayneZoneListener``: walk to the zone the boss just opened.

    The reference hooks ``ExtensionPacketReceived`` and calls
    ``Bot.Player.WalkTo(x, y, 9)``.  A subscriber here is a plain callback, so
    the same ``mv`` packet ``Bot.walk_to`` would send is written directly; the
    guard order is the reference's own: not while dead, not outside
    /ledgermayne, and only for a frame that names a zone.
    """
    if cmd.bot.player.ISDEAD or cmd.is_not_in_map(LEDGERMAYNE_MAP):
        return
    target = ledgermayne_walk(message)
    if target is None:
        return
    x, y = target
    cmd.bot.write_message(f"%xt%zm%mv%{cmd.bot.areaId}%{x}%{y}%9%")


async def _sell_by_id(cmd: Command, item_id: int, qty: int = 1) -> None:
    """``Bot.Shops.SellItem(id)``: this engine sells by name, so resolve first."""
    item = cmd.bot.player.get_item_inventory_by_id(item_id)
    if item is None:
        cmd.bot.log(f"[13loc] item {item_id} is not in the bag; nothing to sell.")
        return
    await cmd.sell_item(item.item_name, qty)


async def _farm(cmd: Command, quest_id: int, body) -> bool:
    """``if (!Story.QuestProgression(q)) { accept; body; complete; }``."""
    if await quest_progression(cmd, quest_id):
        return True
    if await cmd.ensure_accept_quest(quest_id) is False:
        cmd.bot.log(f"[13loc] quest {quest_id} could not be accepted, so "
                    f"nothing is farmed for it.")
        return False
    await body()
    if await cmd.ensure_turn_in_quest(quest_id) is False:
        cmd.bot.log(f"[13loc] quest {quest_id} could not be turned in.")
        return False
    return True


async def kill_ledgermayne(cmd: Command) -> None:
    """``Core13LoC.KillLedgermayne``: quest 847, with the zone listener on."""
    if await quest_progression(cmd, LEDGERMAYNE_LAST):
        return
    if await cmd.ensure_accept_quest(LEDGERMAYNE_LAST) is False:
        cmd.bot.log(f"[13loc] quest {LEDGERMAYNE_LAST} could not be accepted; "
                    f"the fight is skipped.")
        return

    def listener(message):
        _ledgermayne_listener(cmd, message)

    cmd.subscribe(listener)
    try:
        await hunt_item(cmd, "Ledgermayne Defeated", 1, LEDGERMAYNE_MAP,
                        monster_name="Ledgermayne")
    finally:
        cmd.unsubscribe(listener)

    await cmd.ensure_turn_in_quest(LEDGERMAYNE_LAST)


async def ledgermayne(cmd: Command) -> None:
    """``Core13LoC.Ledgermayne``: quests 805-847, from /arcangrove to /elemental."""
    if await cmd.is_completed_before(LEDGERMAYNE_LAST):
        return

    # Observing the Observatory 805 .. Acorny Quest 808
    await map_item_quest(cmd, 805, "arcangrove", 139)
    await map_item_quest(cmd, 806, "cloister", 142)
    await map_item_quest(cmd, 807, "cloister", 140)
    await kill_quest(cmd, 808, "cloister", "Acornent")
    await kill_quest(cmd, 809, "cloister", "Karasu")

    # It's A Bough-t Time 810 -- sell the old sack, buy the new one
    async def q810() -> None:
        await _sell_by_id(cmd, LEDGERMAYNE_SELL_ITEM)
        await adv_buy_item(cmd, LEDGERMAYNE_SHOP, LEDGERMAYNE_SHOP_ITEM,
                           map_name="embersea",
                           shop_item_id=LEDGERMAYNE_SHOP_ITEM_ID)
        await cmd.join_map("cloister")
        await cmd.get_map_item(LEDGERMAYNE_SACK_ITEM, LEDGERMAYNE_SACK_QTY)

    await _farm(cmd, 810, q810)

    await kill_quest(cmd, 811, "cloister", "Wendigo")
    await map_item_quest(cmd, 813, "mudluk", 143)
    await kill_quest(cmd, 814, "mudluk", "Swamp Lurker")
    await kill_quest(cmd, 815, "mudluk", "Swamp Lurker")
    await kill_quest(cmd, 816, "arcangrove", "Gorillaphant")
    await kill_quest(cmd, 817, "mudluk", "Swamp Frogdrake")
    await kill_quest(cmd, 818, "mudluk", "Tiger Leech")
    await map_item_quest(cmd, 825, "natatorium", 144)
    await map_item_quest(cmd, 826, "natatorium", 145, 12)
    await kill_quest(cmd, 827, "natatorium", "Anglerfish")
    await kill_quest(cmd, 828, "natatorium", "Merdraconian")

    # Synchronized Slaying 829
    async def q829() -> None:
        await hunt_item(cmd, "Brain Coral", 5, "arcangrove",
                        monster_name="Seed Spitter")
        await hunt_item(cmd, "Staghorns", 4, "cloister",
                        monster_name="Acornent")
        await hunt_item(cmd, "Sea Fan", 3, "cloister", monster_name="Karasu")
        await hunt_item(cmd, "Sea Whip", 1, "cloister", monster_name="Wendigo")
        await hunt_item(cmd, "Anemones", 6, "mudluk",
                        monster_name="Swamp Frogdrake")

    await _farm(cmd, 829, q829)
    await kill_quest(cmd, 830, "natatorium", "Nessie")
    await map_item_quest(cmd, 831, "gilead", 146)

    # The four elementals 832-835 and their guardians
    async def q832() -> None:
        await hunt_item(cmd, "Dregs Essence", 5, "gilead",
                        monster_name="Earth Elemental")
        await hunt_item(cmd, "Spitter Spirit", 4, "arcangrove",
                        monster_name="Seed Spitter")

    async def q833() -> None:
        await hunt_item(cmd, "Aqueous Essence", 5, "gilead",
                        monster_name="Water Elemental")
        await hunt_item(cmd, "MerCore", 6, "natatorium",
                        monster_name="Merdraconian")

    async def q834() -> None:
        await hunt_item(cmd, "Welkin Essence", 5, "gilead",
                        monster_name="Wind Elemental")
        await hunt_item(cmd, "Karasu Soul", 8, "cloister",
                        monster_name="Karasu")

    async def q835() -> None:
        await hunt_item(cmd, "Pyre Essence", 5, "gilead",
                        monster_name="Fire Elemental")
        await hunt_item(cmd, "Fire Salamander", 5, "mudluk",
                        monster_name="Swamp Frogdrake")

    await _farm(cmd, 832, q832)
    await _farm(cmd, 833, q833)
    await _farm(cmd, 834, q834)
    await _farm(cmd, 835, q835)
    await kill_quest(cmd, 836, "gilead", "Mana Elemental")
    await map_item_quest(cmd, 838, "mafic", 147)
    await kill_quest(cmd, 839, "mafic", "Volcanic Maggot")
    await kill_quest(cmd, 840, "mafic", "Scoria Serpent")
    await kill_quest(cmd, 841, "mafic", "Living Fire")
    await kill_quest(cmd, 842, "mafic", "Mafic Dragon")
    await kill_quest(cmd, 843, "elemental", "Mana Imp")
    await kill_quest(cmd, 844, "elemental", "Mana Falcon")

    # Big, bad, and Baddest Bosses 845
    async def q845() -> None:
        for map_name, monster, orb in LEDGERMAYNE_ORBS:
            await hunt_item(cmd, orb, 1, map_name, monster_name=monster)

    await _farm(cmd, 845, q845)

    # The Great Mana Golem 846
    async def q846() -> None:
        await hunt_item(cmd, "Mana Golem Defeated", 1, "elemental",
                        monster_name="Mana Golem")

    await _farm(cmd, 846, q846)

    # Chaos Lord Ledgermayne 847
    await kill_ledgermayne(cmd)


TIBICENAS_LAST = 1005


async def tibicenas(cmd: Command) -> None:
    """``Core13LoC.Tibicenas``: quests 930-1005, from /sandport to /djinn."""
    if await cmd.is_completed_before(TIBICENAS_LAST):
        return

    # Sandport and Starboard 930 .. Lost and Found 933
    await map_item_quest(cmd, 930, "sandport", 251)
    await kill_quest(cmd, 931, "sandport", "Sandshark")
    await kill_quest(cmd, 932, "sandport", "Tomb Robber")
    await kill_quest(cmd, 933, "sandport", "Tomb Robber")

    # Sell-Sword Sell-Outs 934
    async def q934() -> None:
        await hunt_item(cmd, "Sell-Sword Leader Defeated", 1, "sandport",
                        cell="r6", pad="Left",
                        monster_name="Sell-Sword Leader")
        await hunt_item(cmd, "Horc Sell-Swords Defeated", 3, "sandport",
                        cell="r5", pad="Left", monster_name="Horc Sell-Sword")

    await _farm(cmd, 934, q934)

    # Sacred Scarabs 967 .. Confront Duat 971
    await kill_quest(cmd, 967, "pyramid", "Golden Scarab")
    await kill_quest(cmd, 968, "pyramid", "Anubis Deathguard")
    await kill_quest(cmd, 969, "pyramid", "Mummy")
    await kill_quest(cmd, 970, "pyramid", "Golden Scarab")
    await map_item_quest(cmd, 971, "pyramid", 304)

    # They've Gone Dark 972 .. I Dream Of... 978
    async def q972() -> None:
        await hunt_item(cmd, "Dark Medallion", 8, "wanders", cell="r2",
                        pad="Right", monster_name="Kalestri Worshiper")

    async def q973() -> None:
        await hunt_item(cmd, "Hound Defeated", 10, "wanders", cell="r3",
                        pad="Right", monster_name="Kalestri Hound")

    async def q974() -> None:
        await hunt_item(cmd, "Evil Essence", 10, "wanders", cell="r3",
                        pad="Right", monster_name="Kalestri Hound")

    async def q975() -> None:
        await hunt_item(cmd, "Spider Defeated", 10, "wanders", cell="r5",
                        pad="Right", monster_name="Lotus Spider")

    async def q976() -> None:
        await cmd.join_map("wanders")
        await cmd.get_map_item(306)

    async def q977() -> None:
        await hunt_item(cmd, "Dreamsand", 1, "wanders", cell="r5", pad="Right",
                        monster_name="Lotus Spider")

    async def q978() -> None:
        await hunt_item(cmd, "Sek-Duat Defeated", 1, "wanders", cell="Boss",
                        pad="Left", monster_name="Sek-Duat")

    await _farm(cmd, 972, q972)
    await _farm(cmd, 973, q973)
    await _farm(cmd, 974, q974)
    await _farm(cmd, 975, q975)
    await _farm(cmd, 976, q976)
    await _farm(cmd, 977, q977)
    await _farm(cmd, 978, q978)

    # Sandsational Castle 995 .. Gem Jam 998
    await map_item_quest(cmd, 995, "sandcastle", 361)
    await kill_quest(cmd, 996, "sandcastle", "War Hyena")
    await kill_quest(cmd, 997, "sandcastle", "War Mummy")
    await kill_quest(cmd, 998, "sandcastle", "War Hyena")

    # Enter the Sphinx 999 -- solo, then back to farm for Lamia
    await equip_class(cmd, solo=True)
    await kill_quest(cmd, 999, "sandcastle", "Chaos Sphinx")
    await equip_class(cmd)
    await kill_quest(cmd, 1000, "djinn", "Lamia")
    await kill_quest(cmd, 1001, "sandsea", "Desert Vase")
    await kill_quest(cmd, 1002, "sandsea", "Bupers Camel")
    await kill_quest(cmd, 1003, "djinn", "Harpy")
    await map_item_quest(cmd, 1004, "djinn", 370, 5)

    # Chaos Lord Tibicenas 1005
    await equip_class(cmd, solo=True)
    await kill_quest(cmd, TIBICENAS_LAST, "djinn", "Tibicenas")


KHASAANDA_LAST = 1473
#: Quest 1234's cell-bound kill and 1237's two map-item groups.
KHASAANDA_1234 = ("Polished Rocks", "bloodtusk", "r8", "Left", "Crystal-Rock")
KHASAANDA_1237_ITEMS = ((524, 5), (522, 5))
#: Quest 1281 collects two groups under one quest id.
KHASAANDA_1281_ITEMS = ((554, 5), (555, 10), (556, 10))
#: Quest 1457's map item and drop.
KHASAANDA_1457_MAP_ITEM = (719, 5)
#: Quest 1471 collects two map-item groups under one quest id.
KHASAANDA_1471_ITEMS = ((738, 10), (739, 11))


async def _map_items(cmd: Command, map_name: str,
                     items) -> None:
    """Collect several ``(id, qty)`` groups in one map without turning in."""
    while cmd.is_still_connected() and cmd.is_not_in_map(map_name):
        await cmd.join_map(map_name)
    for item_id, qty in items:
        await cmd.get_map_item(item_id, qty)


async def khasaanda_horc(cmd: Command) -> None:
    """``Core13LoC.KhasaandaHorc``: quests 1232-1473, /crossroads to /dreamnexus.

    Three quests collect their map items in more than one ``MapItemQuest`` call
    (1237, 1281, 1471); the reference lets the early turn-in fail silently, while
    :func:`bot.core_story.map_item_quest` raises on a refused one -- so those use
    :func:`_map_items` and turn the quest in once at the end.
    """
    if await cmd.is_completed_before(KHASAANDA_LAST):
        return

    # Troll Stink! 1232
    async def q1232() -> None:
        await equip_class(cmd)
        await hunt_item(cmd, "Scaly Skin Scrub", 7, "crossroads",
                        monster_name="Chinchilizard")
        await hunt_item(cmd, "Perfumed Trollola Flower", 5, "bloodtusk",
                        monster_name="Trollola Plant")
        await _map_items(cmd, "bloodtusk", ((523, 1),))

    # It Not Time Yet 1233
    async def q1233() -> None:
        await equip_class(cmd)
        await hunt_item(cmd, "Lemurphant Stones", 5, "crossroads",
                        monster_name="Lemurphant")
        await hunt_item(cmd, "Golden Down-fur", 5, "crossroads",
                        monster_name="Koalion")

    # Mountain Protection 1234
    async def q1234() -> None:
        await equip_class(cmd)
        item, map_name, cell, pad, monster = KHASAANDA_1234
        await hunt_item(cmd, item, 3, map_name, cell=cell, pad=pad,
                        monster_name=monster)
        await hunt_item(cmd, "Lemurphant Ivory", 5, "crossroads",
                        monster_name="Lemurphant")
        await hunt_item(cmd, "Liz-Leather Thongs", 5, "crossroads",
                        monster_name="Chinchilizard")
        await _map_items(cmd, "crossroads", ((525, 1),))

    # Clear Mind, Cleanse Spirit 1235
    async def q1235() -> None:
        await equip_class(cmd)
        await hunt_item(cmd, "Trollola Plant Resin", 4, "bloodtusk",
                        monster_name="Trollola Plant")
        await hunt_item(cmd, "Lemurphant Musk", 5, "crossroads",
                        monster_name="Lemurphant")
        await hunt_item(cmd, "Fur for Firestarting", 5, "crossroads",
                        monster_name="Koalion")
        await _map_items(cmd, "crossroads", ((521, 10),))

    # Be Horc Inside 1237
    async def q1237() -> None:
        await equip_class(cmd)
        await hunt_item(cmd, "Skin of the Mountain", 3, "bloodtusk",
                        monster_name="Rock")
        await hunt_item(cmd, "Koalion Claw", 5, "crossroads",
                        monster_name="Koalion")
        await hunt_item(cmd, "Lemurphant Tusks", 5, "crossroads",
                        monster_name="Lemurphant")
        await _map_items(cmd, "crossroads", KHASAANDA_1237_ITEMS)

    await _farm(cmd, 1232, q1232)
    await _farm(cmd, 1233, q1233)
    await _farm(cmd, 1234, q1234)
    await _farm(cmd, 1235, q1235)

    # She Who Asks 1236
    await chain_quest(cmd, 1236)
    await _farm(cmd, 1237, q1237)
    # She Who Answers 2 1241, Chaos Enrages the Horcs 1273
    await chain_quest(cmd, 1241)
    await chain_quest(cmd, 1273)

    # Into, Under the Mountain 1280
    await map_item_quest(cmd, 1280, "ravinetemple", 553)

    # Has the Land Been Tainted? 1281
    if not await quest_progression(cmd, 1281):
        if await cmd.ensure_accept_quest(1281) is False:
            cmd.bot.log("[13loc] quest 1281 could not be accepted, so nothing "
                        "is farmed for it.")
            return
        await _map_items(cmd, "ravinetemple", KHASAANDA_1281_ITEMS)
        if await cmd.ensure_turn_in_quest(1281) is False:
            cmd.bot.log("[13loc] quest 1281 could not be turned in.")
            return

    # Tears of the Mountain 1282
    await kill_quest(cmd, 1282, "ravinetemple", "Temple Guardian")

    # Defend the UnderMountain 1283
    async def q1283() -> None:
        await _map_items(cmd, "ravinetemple", ((557, 10),))
        await hunt_item(cmd, "Sharpened Bone Stake", 5, "ravinetemple",
                        monster_name="Temple Guardian")

    await _farm(cmd, 1283, q1283)
    await kill_quest(cmd, 1284, "ravinetemple", "Temple Guardian")

    # Scout and Return 1375
    await map_item_quest(cmd, 1375, "alliance", [679, 680])

    # Good and Evil Not Always Right 1376
    async def q1376() -> None:
        await equip_class(cmd)
        await hunt_item(cmd, "Good Soldier Vanquished", 10, "alliance",
                        monster_name="Good Soldier")
        await hunt_item(cmd, "Evil Soldier Vanquished", 10, "alliance",
                        monster_name="Evil Soldier")

    await _farm(cmd, 1376, q1376)
    await map_item_quest(cmd, 1377, "alliance", 675, 10)
    await map_item_quest(cmd, 1378, "alliance", 676)
    await kill_quest(cmd, 1379, "alliance", "Chaorrupted Evil Soldier")

    # Alliance Subdued 1380
    async def q1380() -> None:
        await hunt_item(cmd, "Cynari Defeated!", 1, "alliance",
                        monster_name="General Cynari")
        await hunt_item(cmd, "Tibias Defeated!", 1, "alliance",
                        monster_name="General Tibias")

    await _farm(cmd, 1380, q1380)

    # Cleanse the Chaorruption 1424, Chaorruption Cure? 1425
    await kill_quest(cmd, 1424, "ancienttemple", "Chaotic Vulture")

    async def q1425() -> None:
        await _map_items(cmd, "ancienttemple", ((706, 7),))
        await hunt_item(cmd, "Stolen Urn", 7, "ancienttemple",
                        monster_name="Chaotic Vulture")

    await _farm(cmd, 1425, q1425)
    await kill_quest(cmd, 1426, "ancienttemple", "Chaos Troll Spirit")
    await kill_quest(cmd, 1427, "ancienttemple", "Serpentress")
    await map_item_quest(cmd, 1428, "ancienttemple", 707)

    # Wounds in Stones and Beasts 1456, Light in Underhome 1457
    await map_item_quest(cmd, 1456, "orecavern", 717)

    async def q1457() -> None:
        await _map_items(cmd, "orecavern", (KHASAANDA_1457_MAP_ITEM,))
        await hunt_item(cmd, "Light Orb Recovered", 10, "orecavern",
                        monster_name="Crashroom")

    await _farm(cmd, 1457, q1457)
    await map_item_quest(cmd, 1458, "orecavern", 718, 5)
    await kill_quest(cmd, 1459, "orecavern", "Chaorrupted Evil Soldier")
    await equip_class(cmd, solo=True)
    await kill_quest(cmd, 1460, "orecavern", "Naga Baas")

    # Know the Nexus 1469
    await map_item_quest(cmd, 1469, "dreamnexus", [734, 735, 736, 737])

    # Secure a Route Home 1470
    async def q1470() -> None:
        await equip_class(cmd)
        await hunt_item(cmd, "Wyvern Scales", 2, "dreamnexus",
                        monster_name="Dark Wyvern")
        await hunt_item(cmd, "Wyvern Claws", 2, "dreamnexus",
                        monster_name="Dark Wyvern")
        await hunt_item(cmd, "Serpent Fangs", 2, "dreamnexus",
                        monster_name="Aether Serpent")
        await hunt_item(cmd, "Serpent Hair", 2, "dreamnexus",
                        monster_name="Aether Serpent")

    await _farm(cmd, 1470, q1470)

    # DreamDancers' Orbs 1471 -- two groups, one turn-in
    if not await quest_progression(cmd, 1471):
        if await cmd.ensure_accept_quest(1471) is False:
            cmd.bot.log("[13loc] quest 1471 could not be accepted.")
            return
        await _map_items(cmd, "dreamnexus", KHASAANDA_1471_ITEMS)
        await cmd.ensure_turn_in_quest(1471)

    # Master the Flames 1472
    async def q1472() -> None:
        await equip_class(cmd)
        await hunt_item(cmd, "Phoenix Tear", 10, "dreamnexus",
                        monster_name="Solar Phoenix")
        await hunt_item(cmd, "Phoenix Blood", 5, "dreamnexus",
                        monster_name="Solar Phoenix")

    await _farm(cmd, 1472, q1472)

    # Choose: Khasaanda Confrontation? 1473
    async def q1473() -> None:
        await equip_class(cmd, solo=True)
        await hunt_item(cmd, "Khasaanda Defeated!", 1, "dreamnexus",
                        cell="r17a", pad="Up", monster_name="Khasaanda")

    await _farm(cmd, KHASAANDA_LAST, q1473)


LIONFANG_LAST = 2814

#: Quest 2615's own block: the map item, then the two drops it wants.
LIONFANG_2615 = (("Scrap Of Cloth", "Restless Undead", 3),
                 ("Gas Bladder", "Tomb Spider", 3))
LIONFANG_2615_MAP_ITEM = 1616
#: Quest 2668's two drops.
LIONFANG_2668 = (("Chaonslaught Shield", "Chaonslaught Warrior", 2),
                 ("Chaonslaught Sword", "Chaonslaught Cavalry", 3))
#: Quest 2731's three drops, one per monster.
LIONFANG_2731 = (("Primarch Mace", "Sundered Darkblood", 1),
                 ("Primarch Trident", "Rotting Darkblood", 1),
                 ("Primarch Spear", "Ghastly Darkblood", 1))
#: Quest 2740: the map item and the boss drop.
LIONFANG_2740_MAP_ITEM = 1695
LIONFANG_2740 = ("Vestis Defeated", "Wrathful Vestis")
#: Quest 2805/2806 in /stormtemple: the map item, then one kill in r1.
LIONFANG_2805_MAP_ITEM = 1729
LIONFANG_2805_QTY = 4
LIONFANG_2806 = ("Lightning Boots", "r1", "Left")


async def lionfang(cmd: Command) -> None:
    """``Core13LoC.Lionfang``: quests 2612-2814 across six maps.

    The seven quests the source writes out by hand (2615, 2668, 2731, 2740, 2798
    together with its 2797, 2805, 2806) keep their own blocks, in place; the rest
    go through the same two helpers as ``escherion``.

    This is also the story the ``UpdateQuest(2621/2804/2814)`` calls stand in
    for: a socket client cannot write the client-side quest value, so the way
    through those gates is to work the chain that owns them.
    """
    if await cmd.is_completed_before(LIONFANG_LAST):
        return

    # blackhorn
    await kill_quest(cmd, 2612, "blackhorn", "Restless Undead")
    await map_item_quest(cmd, 2613, "blackhorn", 1615, 10)
    await kill_quest(cmd, 2614, "blackhorn", "Tomb Spider")

    # Fire Is The Thing 2615
    if not await cmd.is_completed_before(2615):
        await cmd.ensure_accept_quest(2615)
        await cmd.join_map("blackhorn")
        await cmd.get_map_item(LIONFANG_2615_MAP_ITEM)
        for item, monster, qty in LIONFANG_2615:
            await hunt_item(cmd, item, qty, "blackhorn", monster_name=monster)
        await cmd.ensure_turn_in_quest(2615)

    await map_item_quest(cmd, 2616, "blackhorn", 1617, 1)
    await kill_quest(cmd, 2617, "blackhorn", "Bonefeeder Spider")
    await map_item_quest(cmd, 2618, "blackhorn", 1618, 1)
    await kill_quest(cmd, 2619, "blackhorn", "Tomb Spider")
    await kill_quest(cmd, 2620, "blackhorn", "Restless Undead")
    await map_item_quest(cmd, 2621, "blackhorn", 1619, 1)

    # onslaughttower
    await map_item_quest(cmd, 2622, "onslaughttower", (1620, 1621, 1622, 1623), 1)
    await kill_quest(cmd, 2623, "onslaughttower", "Golden Caster")
    await kill_quest(cmd, 2624, "onslaughttower", "Golden Caster")
    await map_item_quest(cmd, 2625, "onslaughttower", 1624, 8)
    await map_item_quest(cmd, 2626, "onslaughttower", 1625, 1)
    await map_item_quest(cmd, 2627, "onslaughttower", 1626, 4)
    await kill_quest(cmd, 2628, "onslaughttower", "Golden Caster")
    await map_item_quest(cmd, 2629, "onslaughttower", 1627, 1)
    await kill_quest(cmd, 2630, "onslaughttower", "Maximillian Lionfang")

    # falguard
    await kill_quest(cmd, 2666, "falguard", "Chaonslaught Caster")
    await map_item_quest(cmd, 2667, "falguard", 1628, 6)

    # Feeding On The Fallen 2668
    if not await cmd.is_completed_before(2668):
        await cmd.ensure_accept_quest(2668)
        for item, monster, qty in LIONFANG_2668:
            await hunt_item(cmd, item, qty, "falguard", monster_name=monster)
        await cmd.ensure_turn_in_quest(2668)

    await map_item_quest(cmd, 2669, "falguard", 1629, 1)
    await kill_quest(cmd, 2670, "falguard", "Chaonslaught Warrior")
    await map_item_quest(cmd, 2671, "falguard", 1630, 1)
    await map_item_quest(cmd, 2672, "falguard", 1631, 1)
    await kill_quest(cmd, 2673, "falguard", "Chaonslaught Caster")
    await map_item_quest(cmd, 2674, "falguard", 1632, 1)
    await kill_quest(cmd, 2675, "falguard", "Primarch")

    # deathpits
    await kill_quest(cmd, 2720, "deathpits", "Rotting Darkblood")
    await map_item_quest(cmd, 2721, "deathpits", 1691, 5)
    await kill_quest(cmd, 2722, "deathpits", "Rotting Darkblood")
    await kill_quest(cmd, 2723, "deathpits", "Rotting Darkblood")
    await kill_quest(cmd, 2724, "deathpits", "Ghastly Darkblood")
    await kill_quest(cmd, 2725, "deathpits", "Ghastly Darkblood")
    await map_item_quest(cmd, 2726, "deathpits", 1692, 6)
    await kill_quest(cmd, 2727, "deathpits", "Rotting Darkblood")
    await kill_quest(cmd, 2728, "deathpits", "Ghastly Darkblood")
    await kill_quest(cmd, 2729, "deathpits", "Sundered Darkblood")
    await map_item_quest(cmd, 2730, "deathpits", 1693, 9)

    # Honor The Dead 2731
    if not await cmd.is_completed_before(2731):
        await cmd.ensure_accept_quest(2731)
        for item, monster, qty in LIONFANG_2731:
            await hunt_item(cmd, item, qty, "deathpits", monster_name=monster)
        await cmd.ensure_turn_in_quest(2731)

    await map_item_quest(cmd, 2732, "deathpits", 1694, 12)

    # Destroy Wrathful Vestis and Secure The Tears 2740
    if not await cmd.is_completed_before(2740):
        await cmd.ensure_accept_quest(2740)
        await cmd.join_map("deathpits")
        await cmd.get_map_item(LIONFANG_2740_MAP_ITEM)
        await hunt_item(cmd, LIONFANG_2740[0], 1, "deathpits",
                        monster_name=LIONFANG_2740[1])
        await cmd.ensure_turn_in_quest(2740)

    # venomvaults
    await map_item_quest(cmd, 2792, "venomvaults", 1724, 1)
    await kill_quest(cmd, 2793, "venomvaults", "Chaonslaught Warrior")
    await map_item_quest(cmd, 2794, "venomvaults", 1725, 1)
    await map_item_quest(cmd, 2796, "venomvaults", 1726, 1)

    # You've Been Noticed 2798 -- the source guards 2797 and 2798 together
    if not await cmd.is_completed_before(2798):
        await kill_quest(cmd, 2797, "venomvaults", "Chaonslaught Caster")
        await map_item_quest(cmd, 2798, "venomvaults", 1727, 5)

    await kill_quest(cmd, 2799, "venomvaults", "Chaonslaught Caster")
    await kill_quest(cmd, 2800, "venomvaults", "Chaonslaught Warrior")
    await kill_quest(cmd, 2801, "venomvaults", "Chaonslaught Caster")
    await map_item_quest(cmd, 2802, "venomvaults", 1728, 3)
    await kill_quest(cmd, 2803, "venomvaults", "Chaonslaught Caster")
    await kill_quest(cmd, 2804, "venomvaults", "Manticore")

    # Shocking Footwear 2805
    if not await cmd.is_completed_before(2805):
        await cmd.ensure_accept_quest(2805)
        await cmd.join_map("stormtemple")
        await cmd.get_map_item(LIONFANG_2805_MAP_ITEM, LIONFANG_2805_QTY)
        await cmd.ensure_turn_in_quest(2805)

    # New Shoes 2806
    if not await cmd.is_completed_before(2806):
        await cmd.ensure_accept_quest(2806)
        await hunt_item(cmd, LIONFANG_2806[0], 1, "stormtemple",
                        cell=LIONFANG_2806[1], pad=LIONFANG_2806[2],
                        monster_name="*")
        await cmd.ensure_turn_in_quest(2806)

    # stormtemple
    await kill_quest(cmd, 2807, "stormtemple", "Chaonslaught Caster")
    await kill_quest(cmd, 2808, "stormtemple", "Chaonslaught Caster")
    await map_item_quest(cmd, 2809, "stormtemple", 1730, 3)
    await kill_quest(cmd, 2810, "stormtemple", "Chaonslaught Caster")
    await map_item_quest(cmd, 2811, "stormtemple", 1731, 1)
    await kill_quest(cmd, 2812, "stormtemple", "Chaonslaught Cavalry")
    await map_item_quest(cmd, 2813, "stormtemple", 1732, 1)
    await kill_quest(cmd, 2814, "stormtemple", "Chaos Lord Lionfang")


# ---------------------------------------------------------------------------
# Complete13LOC
# ---------------------------------------------------------------------------
#: ``Complete13LOC``'s order, with ``None`` for the segments this port has not
#: reached yet.  Keeping the table here (rather than in the caller) is what lets
#: the walk stop at the first gap instead of skipping a Lord of Chaos.
SEGMENTS = (
    ("Prologue", prologue),
    ("Escherion", escherion),
    ("Vath", vath),
    ("Kitsune", kitsune),
    ("Wolfwing", wolfwing),
    ("Kimberly", kimberly),
    ("Ledgermayne", ledgermayne),
    ("Tibicenas", tibicenas),
    ("KhasaandaHorc", khasaanda_horc),
    ("Iadoa", None),
    ("Lionfang", lionfang),
    ("Xiang", None),
    ("Alteon", None),
    ("Hero", None),
)


async def complete13loc(cmd: Command, with_extras: bool = False) -> None:
    """``Core13LoC.Complete13LOC``: every Lord of Chaos, in the source's order.

    Args:
        cmd (Command): Facade to act through.
        with_extras (bool): The reference's ``withExtras`` -- ``KhasaandaTroll``
            and ``Extra`` after the main chain, neither of them ported.
    """
    for name, segment in SEGMENTS:
        if segment is None:
            cmd.bot.log(f"[13loc] {name} is not ported yet, so Complete13LOC "
                        f"stops here; nothing after it runs.")
            return
        await segment(cmd)

    if with_extras:
        cmd.bot.log("[13loc] KhasaandaTroll and Extra are not ported; "
                    "withExtras ran the main chain only.")


async def main(cmd: Command):
    await complete13loc(cmd)
