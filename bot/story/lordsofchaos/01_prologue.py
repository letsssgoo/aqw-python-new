"""Prologue -- port of ``Story/lordsofchaos/01Prologue.cs``.

The logic is :func:`bot.story.lordsofchaos.core13loc.prologue`.
"""
from bot.script_log import ScriptLog
from bot.story.lordsofchaos.core13loc import prologue as run_segment
from core.command import Command

TAG = "13 Lords of Chaos: Prologue"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Prologue...")
    await run_segment(cmd)
    log.success("Prologue done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
