"""ShadowFlame -- port of ``Story/shadows_of_war/20ShadowFlame.cs``.

The logic is :func:`bot.story.shadows_of_war.core_sow.shadow_flame`.
"""
from bot.script_log import ScriptLog
from bot.story.shadows_of_war.core_sow import shadow_flame as run_segment
from core.command import Command

TAG = "Shadows of War: ShadowFlame"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running ShadowFlame...")
    await run_segment(cmd)
    log.success("ShadowFlame done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
