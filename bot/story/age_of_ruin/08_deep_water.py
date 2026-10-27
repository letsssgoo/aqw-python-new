"""Deep Water -- port of ``Story/age_of_ruin/08DeepWater.cs``.

The logic is :func:`bot.story.age_of_ruin.core_aor.deep_water`.
"""
from bot.script_log import ScriptLog
from bot.story.age_of_ruin.core_aor import deep_water as run_segment
from core.command import Command

TAG = "Age of Ruin: Deep Water"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Deep Water...")
    await run_segment(cmd)
    log.success("Deep Water done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
