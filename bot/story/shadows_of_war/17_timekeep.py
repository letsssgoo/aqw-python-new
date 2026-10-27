"""Timekeep -- port of ``Story/shadows_of_war/17Timekeep.cs``.

The logic is :func:`bot.story.shadows_of_war.core_sow.timekeep`.
"""
from bot.script_log import ScriptLog
from bot.story.shadows_of_war.core_sow import timekeep as run_segment
from core.command import Command

TAG = "Shadows of War: Timekeep"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Timekeep...")
    await run_segment(cmd)
    log.success("Timekeep done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
