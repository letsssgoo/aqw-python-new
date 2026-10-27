"""Sparrows blood daily.

Logic lives in ``bot/core_dailies`` (``sparrows_blood``).  Run it on its own account with
``python -m bot.daily.sparrows_blood``, or through ``start.py``.
"""
from bot.core_dailies import sparrows_blood
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Sparrows blood"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the sparrows blood daily...")
    await sparrows_blood(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
