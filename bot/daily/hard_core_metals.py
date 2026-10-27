"""Hard core metals daily.

Logic lives in ``bot/core_dailies`` (``hard_core_metals``).  Run it on its own account with
``python -m bot.daily.hard_core_metals``, or through ``start.py``.
"""
from bot.core_dailies import hard_core_metals
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Hard core metals"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the hard core metals daily...")
    await hard_core_metals(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
