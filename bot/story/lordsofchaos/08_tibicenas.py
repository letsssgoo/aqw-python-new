"""Tibicenas -- port of ``Story/lordsofchaos/08Tibicenas(Sandsea).cs``.

The logic is :func:`bot.story.lordsofchaos.core13loc.tibicenas`.
"""
from bot.script_log import ScriptLog
from bot.story.lordsofchaos.core13loc import tibicenas as run_segment
from core.command import Command

TAG = "13 Lords of Chaos: Tibicenas"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Tibicenas...")
    await run_segment(cmd)
    log.success("Tibicenas done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
