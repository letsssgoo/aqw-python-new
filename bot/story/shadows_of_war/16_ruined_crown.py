"""Ruined Crown -- port of ``Story/shadows_of_war/16RuinedCrown.cs``.

The logic is :func:`bot.story.shadows_of_war.core_sow.ruined_crown`.
"""
from bot.script_log import ScriptLog
from bot.story.shadows_of_war.core_sow import ruined_crown as run_segment
from core.command import Command

TAG = "Shadows of War: Ruined Crown"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Ruined Crown...")
    await run_segment(cmd)
    log.success("Ruined Crown done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
