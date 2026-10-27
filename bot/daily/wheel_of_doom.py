"""Wheel of doom daily.

Logic lives in ``bot/core_dailies`` (``wheel_of_doom``).  Run it on its own account with
``python -m bot.daily.wheel_of_doom``, or through ``start.py``.
"""
from bot.core_dailies import wheel_of_doom
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Wheel of doom"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the wheel of doom daily...")
    await wheel_of_doom(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
