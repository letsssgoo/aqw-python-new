"""Vath -- port of ``Story/lordsofchaos/03Vath(Dwarfhold).cs``.

The logic is :func:`bot.story.lordsofchaos.core13loc.vath`.
"""
from bot.script_log import ScriptLog
from bot.story.lordsofchaos.core13loc import vath as run_segment
from core.command import Command

TAG = "13 Lords of Chaos: Vath"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Vath...")
    await run_segment(cmd)
    log.success("Vath done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
