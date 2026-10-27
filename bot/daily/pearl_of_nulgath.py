"""Pearl of nulgath daily.

Logic lives in ``bot/core_dailies`` (``pearl_of_nulgath``).  Run it on its own account with
``python -m bot.daily.pearl_of_nulgath``, or through ``start.py``.
"""
from bot.core_dailies import pearl_of_nulgath
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Pearl of nulgath"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the pearl of nulgath daily...")
    await pearl_of_nulgath(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
