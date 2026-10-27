"""Cyseros super hammer daily.

Logic lives in ``bot/core_dailies`` (``cyseros_super_hammer``).  Run it on its own account with
``python -m bot.daily.cyseros_super_hammer``, or through ``start.py``.
"""
from bot.core_dailies import cyseros_super_hammer
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Cyseros super hammer"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the cyseros super hammer daily...")
    await cyseros_super_hammer(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
