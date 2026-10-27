"""Collector class daily.

Logic lives in ``bot/core_dailies`` (``collector_class``).  Run it on its own account with
``python -m bot.daily.collector_class``, or through ``start.py``.
"""
from bot.core_dailies import collector_class
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Collector class"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the collector class daily...")
    await collector_class(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
