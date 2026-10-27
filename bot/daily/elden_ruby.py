"""Elden ruby daily.

Logic lives in ``bot/core_dailies`` (``elden_ruby``).  Run it on its own account with
``python -m bot.daily.elden_ruby``, or through ``start.py``.
"""
from bot.core_dailies import elden_ruby
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Elden ruby"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the elden ruby daily...")
    await elden_ruby(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
