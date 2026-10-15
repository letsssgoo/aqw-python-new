"""The Citadel Ruins questline -- Murry's, Polish's, Cutie Makai's and Casparilla's.

Port of ``Story/Nation/CitadelRuins.cs``, whose ``DoAll`` is what runs: level 30
and Good reputation first, then six chains in its own order.

Note:
    Three things have no counterpart here and are reported rather than invented:

    * the reference's ``GetReward`` flag on a kill quest -- this engine turns a
      quest in without naming a reward, which for these single-reward story quests
      is the same thing;
    * ``Bot.Quests.UpdateQuest(3008)`` before 6675, a client-side quest-slot write;
    * 6682's gear: the reference equips ``Yami no Ronin`` (or any ``Chaos Slayer``
      class) it finds in the inventory or bank, and for Yami only switches the
      rotation to ``"1 | 4"``.  Both are done here -- that rotation is
      ``[0, 1, 4]``, since slot 0 is mandatory -- and its farm-gear step, which has
      no counterpart, is reported.  Without such a class the configured solo class
      is used.
"""
from core.command import Command
from bot.core_bots import equip_class
from bot.core_farms import farm_experience, farm_faction
from bot.core_story import kill_quest, map_item_quest
from bot.nation.core_nation import (dark_makai_item, farm_tainted_gem, supplies,
                                    the_assistant)
from templates.hunt import hunt_item

#: The five items the reference banks when the last chain finishes.
REWARDS = ("Purified Claymore of Destiny", "Good Iron Wing 1",
           "Spinal Tap of Retribution", "Purified Claw of Nulgath",
           "Mage's Gratitude")

#: Level and faction reputation ``DoAll`` asks for first.
LEVEL = 30


async def main(cmd: Command):
    await farm_experience(cmd, LEVEL)
    await farm_faction(cmd, "Good")
    await murrys_quests(cmd)
    await polishs_quests_tercessuinotlim(cmd)
    await polishs_quests_citadel_ruins(cmd)
    await cutie_makais_quest(cmd)
    await casparillas_quests(cmd)


# ---------------------------------------------------------------------------
# Murry's Quests -- 144-149, 181 and 182 in /Citadel
# ---------------------------------------------------------------------------

MURRY_LAST = 182
MURRY_KILLS = (
    (144, "Inquisitor Guard"),
    (145, "Crusader"),
    (146, "Inquisitor Captain"),
    (147, "Burning Witch"),
    (148, "Inquisitor Guard"),
    (149, "Inquisitor Guard"),
    (181, "Belrot The Fiend"),
)


async def murrys_quests(cmd: Command) -> None:
    """Quests 144-149, 181 and 182 in ``/Citadel``."""
    if await cmd.is_completed_before(MURRY_LAST):
        return

    for quest_id, monster in MURRY_KILLS:
        await kill_quest(cmd, quest_id, "Citadel", monster)

    if not await cmd.is_completed_before(MURRY_LAST):
        await cmd.ensure_accept_quest(MURRY_LAST)
        await hunt_item(cmd, "Ring of Evil Intent", 1, "Citadel",
                        monster_name="Grand Inquisitor", is_temp=False)
        await cmd.ensure_turn_in_quest(MURRY_LAST)


# ---------------------------------------------------------------------------
# Polish's Quests in /Tercessuinotlim -- 560, 585 and 668
# ---------------------------------------------------------------------------

TERCESS_LAST = 668
TERCESS_DROPS = ("Unidentified 9", "Unidentified 28", "Dark Crystal Shard",
                 "Claw of Nulgath", "Relic of Chaos")


async def polishs_quests_tercessuinotlim(cmd: Command) -> None:
    """Quests 560, 585 and 668."""
    if await cmd.is_completed_before(TERCESS_LAST):
        return

    cmd.add_drop(list(TERCESS_DROPS))

    # iron wing helm enchant
    await the_assistant(cmd, "Unidentified 9")
    await kill_quest(cmd, 560, "underworld", "Undead Bruiser")

    # cleansing of spinal tap
    await supplies(cmd, "Dark Crystal Shard", 5)
    await the_assistant(cmd, "Unidentified 28")
    await kill_quest(cmd, 585, "Tercessuinotlim", "Legion Fenrir")

    # purified claw
    if not await cmd.has_item("Purified Claw of Nulgath"):
        cmd.add_drop("Purified Claw of Nulgath")
        await cmd.ensure_accept_quest(TERCESS_LAST)
        await farm_tainted_gem(cmd, 7)
        await supplies(cmd, "Claw of Nulgath")
        # the reference resets quest 7551 here, which sends no packet of its own
        await cmd.ensure_accept_quest(7551)
        await dark_makai_item(cmd, "Dark Makai Sigil")
        await cmd.ensure_turn_in_quest(TERCESS_LAST)


# ---------------------------------------------------------------------------
# Polish's Quests in /citadelruins -- 6172-6182
# ---------------------------------------------------------------------------

RUINS_LAST = 6182

#: ``(quest, map item id or ids, how many, monster or monsters)``, in order.
RUINS_STEPS = (
    (6172, 5592, 1, "Mana Sprites"),
    (6173, 5602, 1, None),
    (6174, None, 0, None),
    (6175, 5593, 5, "Inquisitor Hobo"),
    (6176, None, 0, None),
    (6177, (5594, 5595, 5596), 1, "Inquisitor Hobo"),
    (6178, 5597, 1, "Mana Sprites"),
    (6179, 5598, 1, None),
    (6180, (5599, 5600, 5601), 1, "Inquisitor Hobo"),
    (6181, None, 0, "Grand Inquisitor Murry"),
    (RUINS_LAST, None, 0, "Enn'tröpy"),
)

#: The two steps the reference writes out itself, as ``(quest, ((item, qty,
#: monster), ...), map item id or None)``.
RUINS_BY_HAND = (
    (6174, (("Inquisitor Hobos Defeated", 8, "Inquisitor Hobo"),
            ("Inquisitors' Manifesto", 5, "Inquisitor Hobo")), None),
    (6176, (("Heavies Beat Down", 2, "Inquisitor Heavy"),
            ("Citadel Key", 1, "Inquisitor Heavy")), 5603),
)


async def polishs_quests_citadel_ruins(cmd: Command) -> None:
    """Quests 6172-6182 in ``/citadelruins``."""
    if await cmd.is_completed_before(RUINS_LAST):
        return

    cmd.add_drop("Mage's Gratitude")

    for quest_id, item_ids, qty, monsters in RUINS_STEPS:
        by_hand = next((step for step in RUINS_BY_HAND
                        if step[0] == quest_id), None)
        if by_hand is not None:
            _, hunts, extra_item = by_hand
            if await cmd.is_completed_before(quest_id):
                continue
            await cmd.ensure_accept_quest(quest_id)
            for item, hunt_qty, monster in hunts:
                await hunt_item(cmd, item, hunt_qty, "citadelruins",
                                monster_name=monster, is_temp=False)
            if extra_item is not None:
                await map_item_quest(cmd, quest_id, "citadelruins", extra_item)
            else:
                await cmd.ensure_turn_in_quest(quest_id)
            continue

        if item_ids is not None:
            await map_item_quest(cmd, quest_id, "citadelruins", item_ids, qty)
        if monsters is not None:
            await kill_quest(cmd, quest_id, "citadelruins", monsters)
        if quest_id == 6175:
            # the reference pauses here between the grab and the next quest
            await cmd.sleep(2500)

    await cmd.inv_to_bank(list(REWARDS))


# ---------------------------------------------------------------------------
# Cutie Makai's Quest -- 4312-4325
# ---------------------------------------------------------------------------

CUTIE_LAST = 4325

#: ``(quest, map, ((map item id, qty) or None), monster or monsters or None)``.
CUTIE_STEPS = (
    (4312, "drearia", ((3485, 1),), ("Dark Makai", "Evil Elemental", "Green Rat")),
    (4313, "drearia", None, "Dark Makai"),
    (4314, "drearia", ((3466, 1),), "Green Rat"),
    (4315, "drearia", ((3467, 1),), "Green Rat"),
    (4316, "drearia", ((3468, 1),), None),
    (4317, "swordhavenpink", ((3469, 1),), None),
    (4318, "swordhavenpink", ((3486, 5),), "Pink Slime"),
    (4319, "sewerpink", None, "Pink Rat"),
    (4320, "sewerpink", None, "Cutie Grumbley"),
    (4321, "pinewoodpink", ((3470, 1),), "Pink Grizzly"),
    (4322, "pinewoodpink", ((3471, 5),), "Pink Shell Turtle"),
    (4323, "pinewoodpink", None, "Sparkletooth"),
    (4324, "Citadel", ((3472, 1),), None),
    (CUTIE_LAST, "pinewoodpink", None, "Pink Grizzly"),
)


async def cutie_makais_quest(cmd: Command) -> None:
    """Quests 4312-4325, across five maps."""
    if await cmd.is_completed_before(CUTIE_LAST):
        return

    for quest_id, map_name, map_items, monsters in CUTIE_STEPS:
        if map_items is not None:
            await map_item_quest(cmd, quest_id, map_name, map_items)
        if monsters is not None:
            await kill_quest(cmd, quest_id, map_name, monsters)


# ---------------------------------------------------------------------------
# Casparilla's Quests -- 6669-6682
# ---------------------------------------------------------------------------

CASPARILLA_LAST = 6682

#: The plain kills, as ``(quest, map, monster)``.
CASPARILLA_KILLS = (
    (6669, "forest", "Boss Zardman"),
    (6671, "bludrut2", "Shadow Creeper"),
    (6672, "marsh2", "Thrax Ironhide"),
    (6673, "sleuthhound", "Harmoire"),
    (6674, "noobshire", "Kittarian Mouse Eater"),
    (6676, "beachparty", "Sun Flare"),
    (6677, "marsh", "Dreadspider"),
    (6678, "iceplane", "Enfield"),
    (6679, "lair", "Red Dragon"),
    (6680, "ledgermayne", "Ledgermayne"),
    (6681, "palace", "Invisible"),
)

#: Quest 6675 hunts a monster by its map id, and 6682 is the DragonLord.
QUEST_6675 = 6675
PRINCESS = ("Your Princess is Not in This Castle", "doomvault", 21)
DRAGON_LORD_QUEST = CASPARILLA_LAST
DRAGON_LORD = ("underlair", "ArchFiend DragonLord")

#: What 6682's fight wants equipped: this exact class, or any name starting with
#: the other.  Both searches are the reference's own, case and all.
YAMI = "Yami no Ronin"
CHAOS_SLAYER = "Chaos Slayer"

#: The reference's advanced ``"1 | 4"`` rotation for Yami no Ronin: skills 1 and 4
#: only, which needs slot 0 (the auto attack) in front of it here.
YAMI_ROTATION = [0, 1, 4]


async def casparillas_quests(cmd: Command) -> None:
    """Quests 6669-6682."""
    if await cmd.is_completed_before(CASPARILLA_LAST):
        return

    for quest_id, map_name, monster in CASPARILLA_KILLS:
        await kill_quest(cmd, quest_id, map_name, monster)

    if not await cmd.is_completed_before(QUEST_6675):
        await cmd.ensure_accept_quest(QUEST_6675)
        await hunt_item(cmd, PRINCESS[0], 1, PRINCESS[1],
                        monster_name=f"id.{PRINCESS[2]}", is_temp=False)
        await cmd.ensure_turn_in_quest(QUEST_6675)

    cmd.add_drop("Elite Void Sword Pet")
    skill_list = await _equip_dragon_lord_class(cmd)
    await kill_quest(cmd, DRAGON_LORD_QUEST, DRAGON_LORD[0], DRAGON_LORD[1],
                     skill_list=skill_list)


async def _equip_dragon_lord_class(cmd: Command):
    """Equip the class the reference picks for the DragonLord, and report the rest.

    It looks for ``Yami no Ronin`` or any ``Chaos Slayer`` class in the inventory
    or the bank and equips it, then its farm gear, and for Yami only it switches
    the rotation to ``"1 | 4"`` -- skills 1 and 4, which is ``[0, 1, 4]`` here.
    This engine has no farm-gear step, so that one is reported; without such a
    class the configured solo class is used.

    Returns:
        list[int] | None: The rotation to cast, or None for the default one.
    """
    held = [item.s_name for item in
            list(cmd.bot.player.INVENTORY) + list(cmd.bot.player.BANK)]

    for name in held:
        if name == YAMI or name.startswith(CHAOS_SLAYER):
            print(f"[nation] quest {DRAGON_LORD_QUEST}: equipping {name}"
                  + (f" with the \"1 | 4\" rotation ({YAMI_ROTATION})"
                     if name == YAMI else "")
                  + ". Its farm gear has no counterpart here, so the configured "
                    "gear is kept.")
            await cmd.equip_item(name)
            return YAMI_ROTATION if name == YAMI else None

    print(f"[nation] quest {DRAGON_LORD_QUEST}: neither \"{YAMI}\" nor a "
          f"\"{CHAOS_SLAYER}\" class is held; using the configured solo class.")
    await equip_class(cmd, solo=True)
    return None
