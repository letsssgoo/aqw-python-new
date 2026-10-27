"""Trygve -- port of ``Story/hollowborn/01Trygve.cs``.

The logic is :func:`bot.story.hollowborn.CoreHollowborn.Trygve`.
"""
from bot.script_log import ScriptLog
from bot.story.hollowborn.CoreHollowborn import Trygve as run_segment
from core.command import Command

TAG = "Hollowborn: Trygve"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Trygve...")
    await run_segment(cmd)
    log.success("Trygve done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
