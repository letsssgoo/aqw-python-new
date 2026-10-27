"""Xiang -- port of ``Story/lordsofchaos/12Xiang(MirrorRealm).cs``.

The logic is :func:`bot.story.lordsofchaos.core13loc.xiang`.
"""
from bot.script_log import ScriptLog
from bot.story.lordsofchaos.core13loc import xiang as run_segment
from core.command import Command

TAG = "13 Lords of Chaos: Xiang"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Xiang...")
    await run_segment(cmd)
    log.success("Xiang done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
