"""Every ported Nation story, in one run.

Skua keeps its Nation stories as one file per map under ``Story/Nation`` and has
no ``00DoAll`` for them (the maps are reached from ``CoreNation`` instead), so
this list is the port's own: a new ``bot/story/nation/<map>.py`` gets appended
here.
"""
import importlib

from bot.script_log import ScriptLog
from core.command import Command

TAG = "Nation Stories"

#: Chapter modules, in the order they run.
CHAPTERS = (
    "bot.story.nation.citadel_ruins",
    "bot.story.nation.deleuze_tundra",
    "bot.story.nation.fiendshard",
    "bot.story.nation.oblivion_tundra",
    "bot.story.nation.originul",
    "bot.story.nation.shadow_blast_arena",
    "bot.story.nation.terces_archive",
    "bot.story.nation.terces_invasion",
    "bot.story.nation.tercessuinotlim",
    "bot.story.nation.void_chasm",
    "bot.story.nation.void_refuge",
)

#: Source chapters with no port yet.
NOT_PORTED = (
    "Bamboozle",
    "FiendPast",
    "FiendVoid",
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
    log.success(f"{len(CHAPTERS)} Nation stories done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
