"""Tenacity challenge daily.

Logic lives in ``bot/core_dailies`` (``tenacity_challenge``).  Run it on its own account with
``python -m bot.daily.tenacity_challenge``, or through ``start.py``.
"""
from bot.core_dailies import tenacity_challenge
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Tenacity challenge"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the tenacity challenge daily...")
    await tenacity_challenge(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
