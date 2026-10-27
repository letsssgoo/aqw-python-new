"""Kitsune -- port of ``Story/lordsofchaos/04Kitsune(Yokai).cs``.

The logic is :func:`bot.story.lordsofchaos.core13loc.kitsune`.
"""
from bot.script_log import ScriptLog
from bot.story.lordsofchaos.core13loc import kitsune as run_segment
from core.command import Command

TAG = "13 Lords of Chaos: Kitsune"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Kitsune...")
    await run_segment(cmd)
    log.success("Kitsune done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
