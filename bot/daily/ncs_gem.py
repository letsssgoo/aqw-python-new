"""Ncs gem daily.

Logic lives in ``bot/core_dailies`` (``ncs_gem``).  Run it on its own account with
``python -m bot.daily.ncs_gem``, or through ``start.py``.
"""
from bot.core_dailies import ncs_gem
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Ncs gem"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the ncs gem daily...")
    await ncs_gem(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
