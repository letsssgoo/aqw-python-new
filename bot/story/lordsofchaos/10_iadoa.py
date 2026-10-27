"""Iadoa -- port of ``Story/lordsofchaos/10Iadoa(TheSpan).cs``.

The logic is :func:`bot.story.lordsofchaos.core13loc.iadoa`.
"""
from bot.script_log import ScriptLog
from bot.story.lordsofchaos.core13loc import iadoa as run_segment
from core.command import Command

TAG = "13 Lords of Chaos: Iadoa"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Iadoa...")
    await run_segment(cmd)
    log.success("Iadoa done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
