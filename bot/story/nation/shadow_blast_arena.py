"""The Shadow Blast Arena questline -- quests 4733-4736.

Port of ``Story/Nation/ShadowBlastArena.cs``.

``story_line_p1`` runs the four medal quests, gated on the Round 4 medal at the
top exactly as the reference gates it on ``LegacyQuestManager``.  The file's other
two routines are helpers other scripts call directly -- ``emblem_of_gravelyn`` and
``diamond_token_of_gravelyn``, both behind quest 4750.

Note:
    The name of the Nation-side boss is spelled three different ways across the
    reference (``CaesarIsTheDark`` here, ``CaesarisTheDark`` in Tercessuinotlim,
    ``Caesaristhedark`` in CoreLegion).  Each file's own spelling is kept; the
    engine lower-cases both sides when it matches a monster, so all three match
    the same one.
"""
from bot.core_advanced import farm_quest_reward
from bot.core_bots import equip_class
from core.command import Command
from templates.hunt import hunt_item, hunt_item_by_id

#: The map, and the medal that gates the chain.
MAP_NAME = "shadowblast"
ROUND_4_MEDAL = "Shadowscythe Round 4 Medal"

#: The four medal quests, as ``(quest, ((item, qty, monster), ...))``.
MEDAL_QUESTS = (
    (4733, (
        ("Legion Rookie Defeated", 5, "Legion Airstrike"),
        ("Nation Rookie Defeated", 5, "CaesarIsTheDark"),
    )),
    (4734, (
        ("Legion Veteran Defeated", 7, "Legion Fenrir"),
        ("Nation Veteran Defeated", 7, "Carnage"),
    )),
    (4735, (
        ("Legion Elite Defeated", 10, "Legion Cannon"),
        ("Nation Elite Defeated", 10, "Minotaurofwar"),
    )),
    (4736, (
        ("Shadowscythe Destroyer Vanquished", 1, "Shadow Destroyer"),
    )),
)

#: The quest both helpers turn in, and what the Emblem routine collects.
EMBLEM_QUEST = 4750
EMBLEM = "Emblem of Gravelyn"
EMBLEM_DROPS = (("Shadow Seal", 1, "Carnage"),
                ("Gem of Superiority", 1, "Legion Fenrir"))

#: The Diamond Token routine's item, and its first step -- the only one the
#: reference does with the farm class.
DIAMOND_TOKEN = "Diamond Token of Dage"
DIAMOND_FARM_STEP = ("Defeated Makai", 25, "tercessuinotlim", "m2", "Left", "*")

#: The two solo hunts before the id kill, and the two after it -- the reference's
#: order, which matters only for the cells it walks.
DIAMOND_SOLO_BEFORE = (
    ("Carnax Eye", "aqlesson", "Frame9", "Right", "Carnax"),
    ("Kathool Tentacle", "deepchaos", None, "Left", "Kathool"),
)
DIAMOND_SOLO_AFTER = (
    ("Red Dragon's Fang", "lair", None, "Left", "Red Dragon"),
    ("Blood Titan's Blade", "bloodtitan", None, "Left", "Blood Titan"),
)

#: The one kill the reference names by monster map id and item id, in a public
#: room.
DIAMOND_ID_KILL = (33257, "dflesson", "r12", "Right", 29)


async def story_line_p1(cmd: Command) -> None:
    """Quests 4733-4736, the four Shadowscythe medals."""
    if await cmd.has_item(ROUND_4_MEDAL):
        return

    for quest_id, hunts in MEDAL_QUESTS:
        if await cmd.is_completed_before(quest_id):
            continue
        await cmd.ensure_accept_quest(quest_id)
        for item, qty, monster in hunts:
            await hunt_item(cmd, item, qty, MAP_NAME, monster_name=monster,
                            is_temp=False)
        await cmd.ensure_turn_in_quest(quest_id)


async def emblem_of_gravelyn(cmd: Command, quant: int = 100) -> None:
    """``ShadowBlastArena.EmblemofGravelyn``: quest 4750's emblem."""
    if await cmd.has_item(EMBLEM, quant):
        return
    if not await cmd.has_item(ROUND_4_MEDAL):
        await story_line_p1(cmd)

    cmd.add_drop(EMBLEM)
    # the reference logs the Diamond Token here too, in this routine
    cmd.farming_logger(DIAMOND_TOKEN, quant)

    async def farm_pass() -> None:
        for item, qty, monster in EMBLEM_DROPS:
            await hunt_item(cmd, item, qty, MAP_NAME, monster_name=monster,
                            is_temp=False)

    await farm_quest_reward(cmd, EMBLEM_QUEST, EMBLEM, quant, farm_pass)
    cmd.cancel_registered_quests()


async def diamond_token_of_gravelyn(cmd: Command, quant: int = 100) -> None:
    """``ShadowBlastArena.DiamondTokenofGravelyn``: quest 4750's token."""
    if await cmd.has_item(DIAMOND_TOKEN, quant):
        return
    if not await cmd.has_item(ROUND_4_MEDAL):
        await story_line_p1(cmd)

    cmd.add_drop(["Legion Token", DIAMOND_TOKEN])
    cmd.farming_logger(DIAMOND_TOKEN, quant)

    async def farm_pass() -> None:
        await equip_class(cmd)
        await hunt_item(cmd, *DIAMOND_FARM_STEP, is_temp=False)

        await equip_class(cmd, solo=True)
        for item, map_name, cell, pad, monster in DIAMOND_SOLO_BEFORE:
            await hunt_item(cmd, item, 1, map_name, cell=cell, pad=pad,
                            monster_name=monster, is_temp=False)

        item_id, map_name, cell, pad, monster_map_id = DIAMOND_ID_KILL
        await hunt_item_by_id(cmd, item_id, 1, map_name, cell=cell, pad=pad,
                              monster_map_id=monster_map_id)

        for item, map_name, cell, pad, monster in DIAMOND_SOLO_AFTER:
            await hunt_item(cmd, item, 1, map_name, cell=cell, pad=pad,
                            monster_name=monster, is_temp=False)

    await farm_quest_reward(cmd, EMBLEM_QUEST, DIAMOND_TOKEN, quant, farm_pass)
    cmd.cancel_registered_quests()


async def main(cmd: Command):
    await story_line_p1(cmd)
