"""Khasaanda Horc -- port of ``Story/lordsofchaos/09Khasaanda(Horc).cs``.

The logic is :func:`bot.story.lordsofchaos.core13loc.khasaanda_horc`.
"""
from bot.script_log import ScriptLog
from bot.story.lordsofchaos.core13loc import khasaanda_horc as run_segment
from core.command import Command

TAG = "13 Lords of Chaos: Khasaanda Horc"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Khasaanda Horc...")
    await run_segment(cmd)
    log.success("Khasaanda Horc done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
