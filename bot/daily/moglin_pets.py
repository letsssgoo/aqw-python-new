"""Moglin pets daily.

Logic lives in ``bot/core_dailies`` (``moglin_pets``).  Run it on its own account with
``python -m bot.daily.moglin_pets``, or through ``start.py``.
"""
from bot.core_dailies import moglin_pets
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Moglin pets"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the moglin pets daily...")
    await moglin_pets(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
