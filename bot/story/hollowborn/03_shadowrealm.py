"""Shadowrealm -- port of ``Story/hollowborn/03Shadowrealm.cs``.

The logic is :func:`bot.story.hollowborn.CoreHollowborn.Shadowrealm`.
"""
from bot.script_log import ScriptLog
from bot.story.hollowborn.CoreHollowborn import Shadowrealm as run_segment
from core.command import Command

TAG = "Hollowborn: Shadowrealm"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Shadowrealm...")
    await run_segment(cmd)
    log.success("Shadowrealm done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
