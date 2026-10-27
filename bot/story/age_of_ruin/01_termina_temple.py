"""Termina Temple -- port of ``Story/age_of_ruin/01TerminaTemple.cs``.

The logic is :func:`bot.story.age_of_ruin.core_aor.termina_temple`.
"""
from bot.script_log import ScriptLog
from bot.story.age_of_ruin.core_aor import termina_temple as run_segment
from core.command import Command

TAG = "Age of Ruin: Termina Temple"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Termina Temple...")
    await run_segment(cmd)
    log.success("Termina Temple done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
