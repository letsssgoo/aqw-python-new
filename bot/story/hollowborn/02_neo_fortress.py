"""Neo Fortress -- port of ``Story/hollowborn/02NeoFortress.cs``.

The logic is :func:`bot.story.hollowborn.CoreHollowborn.NeoFortress`.
"""
from bot.script_log import ScriptLog
from bot.story.hollowborn.CoreHollowborn import NeoFortress as run_segment
from core.command import Command

TAG = "Hollowborn: Neo Fortress"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Neo Fortress...")
    await run_segment(cmd)
    log.success("Neo Fortress done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
