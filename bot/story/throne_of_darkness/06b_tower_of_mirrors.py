"""Tower of Mirrors -- port of ``Story/throne_of_darkness/06bScarletta(TowerofMirrors).cs``.

The logic is :func:`bot.story.throne_of_darkness.core_tod.tower_of_mirrors`.
"""
from bot.script_log import ScriptLog
from bot.story.throne_of_darkness.core_tod import tower_of_mirrors as run_segment
from core.command import Command

TAG = "Throne of Darkness: Tower of Mirrors"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Tower of Mirrors...")
    await run_segment(cmd)
    log.success("Tower of Mirrors done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
