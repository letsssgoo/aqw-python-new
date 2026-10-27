"""Beast master challenge daily.

Logic lives in ``bot/core_dailies`` (``beast_master_challenge``).  Run it on its own account with
``python -m bot.daily.beast_master_challenge``, or through ``start.py``.
"""
from bot.core_dailies import beast_master_challenge
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Beast master challenge"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the beast master challenge daily...")
    await beast_master_challenge(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
