"""Grumble grumble daily.

Logic lives in ``bot/core_dailies`` (``grumble_grumble``).  Run it on its own account with
``python -m bot.daily.grumble_grumble``, or through ``start.py``.
"""
from bot.core_dailies import grumble_grumble
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Grumble grumble"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the grumble grumble daily...")
    await grumble_grumble(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
