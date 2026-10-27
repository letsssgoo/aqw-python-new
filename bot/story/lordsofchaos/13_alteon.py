"""Alteon -- port of ``Story/lordsofchaos/13Alteon(Swordhaven).cs``.

The logic is :func:`bot.story.lordsofchaos.core13loc.alteon`.
"""
from bot.script_log import ScriptLog
from bot.story.lordsofchaos.core13loc import alteon as run_segment
from core.command import Command

TAG = "13 Lords of Chaos: Alteon"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Alteon...")
    await run_segment(cmd)
    log.success("Alteon done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
