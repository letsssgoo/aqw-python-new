"""Escherion -- port of ``Story/lordsofchaos/02Escherion(ChiralValley).cs``.

The logic is :func:`bot.story.lordsofchaos.core13loc.escherion`.
"""
from bot.script_log import ScriptLog
from bot.story.lordsofchaos.core13loc import escherion as run_segment
from core.command import Command

TAG = "13 Lords of Chaos: Escherion"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Escherion...")
    await run_segment(cmd)
    log.success("Escherion done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
