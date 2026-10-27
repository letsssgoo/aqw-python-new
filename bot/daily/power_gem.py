"""Power gem daily.

Logic lives in ``bot/core_dailies`` (``power_gem``).  Run it on its own account with
``python -m bot.daily.power_gem``, or through ``start.py``.
"""
from bot.core_dailies import power_gem
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Power gem"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the power gem daily...")
    await power_gem(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
