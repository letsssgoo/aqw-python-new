"""Lionfang -- port of ``Story/lordsofchaos/11Lionfang(Darkblood).cs``.

The logic is :func:`bot.story.lordsofchaos.core13loc.lionfang`.
"""
from bot.script_log import ScriptLog
from bot.story.lordsofchaos.core13loc import lionfang as run_segment
from core.command import Command

TAG = "13 Lords of Chaos: Lionfang"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Lionfang...")
    await run_segment(cmd)
    log.success("Lionfang done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
