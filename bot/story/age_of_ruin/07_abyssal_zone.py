"""Abyssal Zone -- port of ``Story/age_of_ruin/07AbyssalZone.cs``.

The logic is :func:`bot.story.age_of_ruin.core_aor.abyssal_zone`.
"""
from bot.script_log import ScriptLog
from bot.story.age_of_ruin.core_aor import abyssal_zone as run_segment
from core.command import Command

TAG = "Age of Ruin: Abyssal Zone"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Abyssal Zone...")
    await run_segment(cmd)
    log.success("Abyssal Zone done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
