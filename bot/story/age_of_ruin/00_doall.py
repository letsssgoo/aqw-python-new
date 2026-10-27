"""Age of Ruin -- every ported chapter of Age of Ruin, in order.

Mirrors ``Story/age_of_ruin/00DoAll.cs``.  Chapters the port has not reached
yet are named in ``NOT_PORTED`` instead of being skipped silently.
"""
import importlib

from bot.script_log import ScriptLog
from core.command import Command

TAG = "Age of Ruin"

#: Chapter modules, in the source's order.
CHAPTERS = (
    "bot.story.age_of_ruin.01_termina_temple",
    "bot.story.age_of_ruin.02_ashray_village",
    "bot.story.age_of_ruin.03_sunlight_zone",
    "bot.story.age_of_ruin.04_twilight_zone",
    "bot.story.age_of_ruin.05_yulgar_aria",
    "bot.story.age_of_ruin.06_midnight_zone",
    "bot.story.age_of_ruin.07_abyssal_zone",
    "bot.story.age_of_ruin.08_deep_water",
    "bot.story.age_of_ruin.09_sea_voice",
)

#: Source chapters with no port yet.
NOT_PORTED = (
    "10Balemorale",
    "11Castleeblana",
    "12Loughshine",
    "13NaoiseGrave",
    "14LiaTaraHill",
    "15CastleGaheris",
    "16ColdThunder",
    "17ThelimaCity",
    "18MountMaleno",
    "19SanctuaryAiwass",
    "20ForgeAlbedo",
    "21FortLuma",
    "22WarWickForest",
    "23MagnumOpus",
    "24RubedoPeak",
    "25ForgeCitrinitas",
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
