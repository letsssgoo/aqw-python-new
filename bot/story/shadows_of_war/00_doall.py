"""Shadows of War -- every ported chapter of Shadows of War, in order.

Mirrors ``Story/shadows_of_war/00DoAll.cs``.  Chapters the port has not reached
yet are named in ``NOT_PORTED`` instead of being skipped silently.
"""
import importlib

from bot.script_log import ScriptLog
from core.command import Command

TAG = "Shadows of War"

#: Chapter modules, in the source's order.
CHAPTERS = (
    "bot.story.shadows_of_war.16_ruined_crown",
    "bot.story.shadows_of_war.17_timekeep",
    "bot.story.shadows_of_war.18_timestream_war",
    "bot.story.shadows_of_war.19_dead_lines",
    "bot.story.shadows_of_war.20_shadow_flame",
    "bot.story.shadows_of_war.21_mana_cradle",
)

#: Source chapters with no port yet.
NOT_PORTED = (
    "01ShadowWar",
    "02ShadowlordKeep",
    "03Timestream",
    "04GraniteCove",
    "05BlackseaKeep",
    "06Junkhoard",
    "07Junkheap",
    "08Shadowgrove",
    "09AozoraHills",
    "10GhostNexus",
    "11Shadowsong",
    "12DarkAlly",
    "13DarkAlliance",
    "14InnerShadows",
    "15Tyndarius",
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
