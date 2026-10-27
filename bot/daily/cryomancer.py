"""Cryomancer daily.

Logic lives in ``bot/core_dailies`` (``cryomancer``).  Run it on its own account with
``python -m bot.daily.cryomancer``, or through ``start.py``.
"""
from bot.core_dailies import cryomancer
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Cryomancer"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the cryomancer daily...")
    await cryomancer(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
