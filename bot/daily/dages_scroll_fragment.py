"""Dages scroll fragment daily.

Logic lives in ``bot/core_dailies`` (``dages_scroll_fragment``).  Run it on its own account with
``python -m bot.daily.dages_scroll_fragment``, or through ``start.py``.
"""
from bot.core_dailies import dages_scroll_fragment
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Dages scroll fragment"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the dages scroll fragment daily...")
    await dages_scroll_fragment(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
