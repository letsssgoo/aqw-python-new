"""``CoreBLOD`` -- the Blade of Destiny core, only what is ported of it.

Port of ``Good/BLoD/CoreBLOD.cs``.  ``UnlockMineCrafting`` is what
``ArchPaladin`` needs; the rest of that core (the full Blade of Destiny chain,
``SpiritOrb``'s own farm, ``KillDoomKitten``) lives where it already was:
``SpiritOrb`` is :func:`bot.core_farms.bone_some_dust` (the same /battleunderb
farm) and ``KillDoomKitten`` is :func:`bot.core_bots.kill_doom_kitten`.
"""
from bot.core_bots import equip_class
from bot.core_farms import bone_some_dust
from bot.core_story import CustomError, buy_quest, quest_progression
from core.command import Command
from templates.hunt import hunt_item
from bot.script_log import ScriptLog
TAG = "BLoD"

MINE_CRAFTING_LAST = 2084
DOOMWOOD_SHOP = 276
DOOMWOOD_MAP = "doomwood"


async def _quest(cmd: Command, quest_id: int, body) -> None:
    """``if (!Story.QuestProgression(q)) { accept; body; complete; }``."""
    if await quest_progression(cmd, quest_id):
        return
    if await cmd.ensure_accept_quest(quest_id) is False:
        raise CustomError(f"quest {quest_id} could not be accepted")
    await body()
    if await cmd.ensure_turn_in_quest(quest_id) is False:
        raise CustomError(f"quest {quest_id} could not be turned in")


async def unlock_mine_crafting(cmd: Command) -> None:
    """``CoreBLOD.UnlockMineCrafting``: quests 2066, 2067, 2082-2084."""
    if await cmd.is_completed_before(MINE_CRAFTING_LAST):
        return

    await buy_quest(cmd, 2066, DOOMWOOD_MAP, DOOMWOOD_SHOP,
                    "Blinding Light of Destiny Handle")
    await buy_quest(cmd, 2067, DOOMWOOD_MAP, DOOMWOOD_SHOP, "Bonegrinder Medal")

    async def q2082() -> None:
        await hunt_item(cmd, "Undead Essence", 25, "battleunderb",
                        monster_name="Skeleton Warrior", is_temp=False)

    await _quest(cmd, 2082, q2082)

    async def q2083() -> None:
        await hunt_item(cmd, "Bone Dust", 40, "battleunderb",
                        monster_name="Skeleton Warrior", is_temp=False)

    await _quest(cmd, 2083, q2083)

    async def q2084() -> None:
        # ``SpiritOrb(100)``: the same /battleunderb farm the reference uses.
        await bone_some_dust(cmd, 100)
        await hunt_item(cmd, "Celestial Compass", 1, "timevoid",
                        monster_name="Ephemerite")

    await equip_class(cmd, solo=True)
    await _quest(cmd, 2084, q2084)


async def main(cmd: Command):
    await unlock_mine_crafting(cmd)


if __name__ == "__main__":
    # Runs this script on its own account, the way
    # ``bot/enhancements/valiance.py`` does.
    from bot.standalone import run_standalone

    run_standalone(main)
