"""Shadowfall Rise -- port of ``Story/sepulchure_saga/04ShadowfallRise.cs``.

The logic is :func:`bot.story.sepulchure_saga.core_sepulchure.shadowfall_rise`.
"""
from bot.script_log import ScriptLog
from bot.story.sepulchure_saga.core_sepulchure import shadowfall_rise as run_segment
from core.command import Command

TAG = "Sepulchure Saga: Shadowfall Rise"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Shadowfall Rise...")
    await run_segment(cmd)
    log.success("Shadowfall Rise done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
