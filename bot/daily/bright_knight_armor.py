"""Bright knight armor daily.

Logic lives in ``bot/core_dailies`` (``bright_knight_armor``).  Run it on its own account with
``python -m bot.daily.bright_knight_armor``, or through ``start.py``.
"""
from bot.core_dailies import bright_knight_armor
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Bright knight armor"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the bright knight armor daily...")
    await bright_knight_armor(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
