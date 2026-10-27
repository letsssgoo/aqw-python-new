"""Design notes daily.

Logic lives in ``bot/core_dailies`` (``design_notes``).  Run it on its own account with
``python -m bot.daily.design_notes``, or through ``start.py``.
"""
from bot.core_dailies import design_notes
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Design notes"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the design notes daily...")
    await design_notes(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
