"""Wolfwing -- port of ``Story/lordsofchaos/05Wolfwing(Darkovia).cs``.

The logic is :func:`bot.story.lordsofchaos.core13loc.wolfwing`.
"""
from bot.script_log import ScriptLog
from bot.story.lordsofchaos.core13loc import wolfwing as run_segment
from core.command import Command

TAG = "13 Lords of Chaos: Wolfwing"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Wolfwing...")
    await run_segment(cmd)
    log.success("Wolfwing done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
