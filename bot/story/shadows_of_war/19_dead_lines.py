"""DeadLines -- port of ``Story/shadows_of_war/19DeadLines.cs``.

The logic is :func:`bot.story.shadows_of_war.core_sow.dead_lines`.
"""
from bot.script_log import ScriptLog
from bot.story.shadows_of_war.core_sow import dead_lines as run_segment
from core.command import Command

TAG = "Shadows of War: DeadLines"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running DeadLines...")
    await run_segment(cmd)
    log.success("DeadLines done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
