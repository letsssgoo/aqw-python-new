"""Timestream War -- port of ``Story/shadows_of_war/18TimestreamWar.cs``.

The logic is :func:`bot.story.shadows_of_war.core_sow.timestream_war`.
"""
from bot.script_log import ScriptLog
from bot.story.shadows_of_war.core_sow import timestream_war as run_segment
from core.command import Command

TAG = "Shadows of War: Timestream War"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Timestream War...")
    await run_segment(cmd)
    log.success("Timestream War done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
