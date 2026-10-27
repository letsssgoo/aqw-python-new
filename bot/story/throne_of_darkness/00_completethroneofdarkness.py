"""Throne of Darkness -- every ported chapter of Throne of Darkness, in order.

Mirrors ``Story/throne_of_darkness/00CompleteThroneofDarkness.cs``.  Chapters the port has not reached
yet are named in ``NOT_PORTED`` instead of being skipped silently.
"""
import importlib

from bot.script_log import ScriptLog
from core.command import Command

TAG = "Throne of Darkness"

#: Chapter modules, in the source's order.
CHAPTERS = (
    "bot.story.throne_of_darkness.06a_shatter_glass_maze",
    "bot.story.throne_of_darkness.06b_tower_of_mirrors",
)

#: Source chapters with no port yet.
NOT_PORTED = (
    "01aVaden(CastleofBones)",
    "01bVaden(BoneTowers)[Mem]",
    "02aXeven(ParadoxPortal)",
    "02bXeven(DeepPortalspace)[Mem]",
    "03aZiri(BaconCatFortress)",
    "03bZiri(LaserSharkInvasion)",
    "04aPax(DeathPit)",
    "04bPax(DeathPitPvp)",
    "05aSekt(ShiftingPyramid)",
    "05bSekt(FourthDimensionalPyramid)",
    "05cSekt(Yasaris)",
    "07aStranger(AntiqueShop)",
    "07bStranger(MysteriousDungeon)",
)


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    for module_path in CHAPTERS:
        name = module_path.rsplit(".", 1)[-1]
        log.info(f"--- {name} ---")
        module = importlib.import_module(module_path)
        try:
            await module.main(cmd)
        except Exception as error:  # noqa: BLE001
            log.error(f"{name} stopped: {type(error).__name__}: {error}")
            return
    if NOT_PORTED:
        log.warning(f"not ported yet: {', '.join(NOT_PORTED)}")
    log.success(f"{len(CHAPTERS)} chapters done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
