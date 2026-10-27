"""Ashray Village -- port of ``Story/age_of_ruin/02AshrayVillage.cs``.

The logic is :func:`bot.story.age_of_ruin.core_aor.ashray_village`.
"""
from bot.script_log import ScriptLog
from bot.story.age_of_ruin.core_aor import ashray_village as run_segment
from core.command import Command

TAG = "Age of Ruin: Ashray Village"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Ashray Village...")
    await run_segment(cmd)
    log.success("Ashray Village done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
