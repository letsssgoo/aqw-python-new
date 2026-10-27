"""ShatterGlass Maze -- port of ``Story/throne_of_darkness/06aScarletta(ShatterGlassMaze).cs``.

The logic is :func:`bot.story.throne_of_darkness.core_tod.shatter_glass_maze`.
"""
from bot.script_log import ScriptLog
from bot.story.throne_of_darkness.core_tod import shatter_glass_maze as run_segment
from core.command import Command

TAG = "Throne of Darkness: ShatterGlass Maze"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running ShatterGlass Maze...")
    await run_segment(cmd)
    log.success("ShatterGlass Maze done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
