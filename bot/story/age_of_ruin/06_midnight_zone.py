"""Midnight Zone -- port of ``Story/age_of_ruin/06MidnightZone.cs``.

The logic is :func:`bot.story.age_of_ruin.core_aor.midnight_zone`.
"""
from bot.script_log import ScriptLog
from bot.story.age_of_ruin.core_aor import midnight_zone as run_segment
from core.command import Command

TAG = "Age of Ruin: Midnight Zone"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Midnight Zone...")
    await run_segment(cmd)
    log.success("Midnight Zone done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
