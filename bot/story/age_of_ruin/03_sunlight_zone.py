"""Sunlight Zone -- port of ``Story/age_of_ruin/03SunlightZone.cs``.

The logic is :func:`bot.story.age_of_ruin.core_aor.sunlight_zone`.
"""
from bot.script_log import ScriptLog
from bot.story.age_of_ruin.core_aor import sunlight_zone as run_segment
from core.command import Command

TAG = "Age of Ruin: Sunlight Zone"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Sunlight Zone...")
    await run_segment(cmd)
    log.success("Sunlight Zone done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
