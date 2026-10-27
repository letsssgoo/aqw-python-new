"""Sea Voice -- port of ``Story/age_of_ruin/09SeaVoice.cs``.

The logic is :func:`bot.story.age_of_ruin.core_aor.sea_voice`.
"""
from bot.script_log import ScriptLog
from bot.story.age_of_ruin.core_aor import sea_voice as run_segment
from core.command import Command

TAG = "Age of Ruin: Sea Voice"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Sea Voice...")
    await run_segment(cmd)
    log.success("Sea Voice done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
