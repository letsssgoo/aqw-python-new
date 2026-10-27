"""Mad weapon smith daily.

Logic lives in ``bot/core_dailies`` (``mad_weapon_smith``).  Run it on its own account with
``python -m bot.daily.mad_weapon_smith``, or through ``start.py``.
"""
from bot.core_dailies import mad_weapon_smith
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Mad weapon smith"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the mad weapon smith daily...")
    await mad_weapon_smith(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
