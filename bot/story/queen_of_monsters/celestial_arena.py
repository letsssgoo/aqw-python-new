"""Celestial Arena (Extra) -- quests 6013-6042 across three arenas.

Port of ``Story/QueenOfMonsters/Extra/CelestialArena.cs``.

Each arena is one guard quest (6022 / 6032 / 6042) and a run of
``Story.KillQuest``s.  The source's ``Core.JumpWait()`` after every kill has no
step here: :meth:`core.command.Command.jump_cell` already waits a second for the
move to land, and the hunts themselves pick their cell from the monster.

The third arena jumps before each kill (``Core.Jump("r2")`` .. ``"r10"``); Skua's
``Jump(cell)`` defaults to pad ``"Spawn"``, which is what is passed here.
"""
from bot.core_advanced import gear_store
from bot.core_bots import equip_class
from bot.core_story import kill_quest
from core.command import Command
from bot.script_log import ScriptLog
TAG = "Celestial Arena"

ARENA_B = "celestialarenab"
ARENA_C = "celestialarenac"
ARENA_D = "celestialarenad"

#: ``(monster, quest)`` per arena, in the source's order.
ARENA_B_ROWS = (("Slork Construct", 6013), ("Azkorath Construct", 6014),
                ("Blessed Inquisitor", 6015),
                ("Lich Ravager Construct", 6016),
                ("Ring Guardian Construct", 6017),
                ("Serepthys Construct", 6018), ("Yaomo Construct", 6019),
                ("Cerberus Construct", 6020),
                ("Infernal Warrior Construct", 6021),
                ("Infernal Warlord Construct", 6022))
ARENA_C_ROWS = (("Conquest Construct", 6023), ("War Construct", 6024),
                ("Death Construct", 6025), ("Famine Construct", 6026),
                ("Diabolical Warlord Construct", 6027),
                ("Undead Raxgore Construct", 6028),
                ("Blessed Karok", 6029), ("Kezeroth Construct", 6030),
                ("Shadow Lord Construct", 6031),
                ("Desolich Construct", 6032))
#: ``(monster, quest, the jump the source makes *before* this kill)``.
ARENA_D_ROWS = (("Queen of Hope", 6033, None),
                ("Malxas Construct", 6034, "r2"),
                ("Blessed Gladius", 6035, "r3"),
                ("High Celestial Priest", 6036, "r4"),
                ("Blessed Enfield", 6037, "r5"),
                ("Avatar of Spirits", 6038, "r6"),
                ("Avatar of Time", 6039, "r7"),
                ("Avatar of Life", 6040, "r8"),
                ("Fallen Abezeth", 6041, "r9"),
                ("Aranx", 6042, "r10"))


async def arena_1_to_10(cmd: Command) -> None:
    """``CelestialArenaQuests.Arena1to10``."""
    if await cmd.is_completed_before(6022):
        return
    await equip_class(cmd, solo=True)
    for monster, quest_id in ARENA_B_ROWS:
        await kill_quest(cmd, quest_id, ARENA_B, monster)


async def arena_11_to_20(cmd: Command) -> None:
    """``CelestialArenaQuests.Arena11to20``."""
    if await cmd.is_completed_before(6032):
        return
    await equip_class(cmd, solo=True)
    for monster, quest_id in ARENA_C_ROWS:
        await kill_quest(cmd, quest_id, ARENA_C, monster)


async def arena_21_to_29(cmd: Command) -> None:
    """``CelestialArenaQuests.Arena21to29``."""
    if await cmd.is_completed_before(6042):
        return
    await equip_class(cmd, solo=True)
    for monster, quest_id, cell in ARENA_D_ROWS:
        if cell is not None:
            await cmd.jump_cell(cell, "Spawn")
        await kill_quest(cmd, quest_id, ARENA_D, monster)


async def do_all(cmd: Command) -> None:
    """``CelestialArenaQuests.DoAll``: the three arenas, snapshot around them."""
    await gear_store(cmd)
    await arena_1_to_10(cmd)
    await arena_11_to_20(cmd)
    await arena_21_to_29(cmd)
    await gear_store(cmd, restore=True, enh_after=True)


async def main(cmd: Command):
    await do_all(cmd)


if __name__ == "__main__":
    # Runs this script on its own account, the way
    # ``bot/enhancements/valiance.py`` does.
    from bot.standalone import run_standalone

    run_standalone(main)
