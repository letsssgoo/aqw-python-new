"""ManaCradle -- port of ``Story/shadows_of_war/21ManaCradle.cs``.

The logic is :func:`bot.story.shadows_of_war.core_sow.mana_cradle`.
"""
from bot.script_log import ScriptLog
from bot.story.shadows_of_war.core_sow import mana_cradle as run_segment
from core.command import Command

TAG = "Shadows of War: ManaCradle"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running ManaCradle...")
    await run_segment(cmd)
    log.success("ManaCradle done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
