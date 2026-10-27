"""Pyromancer daily.

Logic lives in ``bot/core_dailies`` (``pyromancer``).  Run it on its own account with
``python -m bot.daily.pyromancer``, or through ``start.py``.
"""
from bot.core_dailies import pyromancer
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Pyromancer"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the pyromancer daily...")
    await pyromancer(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
