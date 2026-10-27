"""Ledgermayne -- port of ``Story/lordsofchaos/07Ledgermayne(Arcangrove).cs``.

The logic is :func:`bot.story.lordsofchaos.core13loc.ledgermayne`.
"""
from bot.script_log import ScriptLog
from bot.story.lordsofchaos.core13loc import ledgermayne as run_segment
from core.command import Command

TAG = "13 Lords of Chaos: Ledgermayne"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Ledgermayne...")
    await run_segment(cmd)
    log.success("Ledgermayne done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
