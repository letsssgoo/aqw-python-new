"""Kimberly -- port of ``Story/lordsofchaos/06Kimberly(Mythsong).cs``.

The logic is :func:`bot.story.lordsofchaos.core13loc.kimberly`.
"""
from bot.script_log import ScriptLog
from bot.story.lordsofchaos.core13loc import kimberly as run_segment
from core.command import Command

TAG = "13 Lords of Chaos: Kimberly"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Kimberly...")
    await run_segment(cmd)
    log.success("Kimberly done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
