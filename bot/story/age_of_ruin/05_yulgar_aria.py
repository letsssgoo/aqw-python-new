"""Yulgar Aria -- port of ``Story/age_of_ruin/05YulgarAria.cs``.

The logic is :func:`bot.story.age_of_ruin.core_aor.yulgar_aria`.
"""
from bot.script_log import ScriptLog
from bot.story.age_of_ruin.core_aor import yulgar_aria as run_segment
from core.command import Command

TAG = "Age of Ruin: Yulgar Aria"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Yulgar Aria...")
    await run_segment(cmd)
    log.success("Yulgar Aria done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
