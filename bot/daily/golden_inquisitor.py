"""Golden inquisitor daily.

Logic lives in ``bot/core_dailies`` (``golden_inquisitor``).  Run it on its own account with
``python -m bot.daily.golden_inquisitor``, or through ``start.py``.
"""
from bot.core_dailies import golden_inquisitor
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Golden inquisitor"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the golden inquisitor daily...")
    await golden_inquisitor(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
