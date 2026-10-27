"""Free daily boost daily.

Logic lives in ``bot/core_dailies`` (``free_daily_boost``).  Run it on its own account with
``python -m bot.daily.free_daily_boost``, or through ``start.py``.
"""
from bot.core_dailies import free_daily_boost
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Free daily boost"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the free daily boost daily...")
    await free_daily_boost(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
