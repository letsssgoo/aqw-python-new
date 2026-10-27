"""Monthly treasure chest keys daily.

Logic lives in ``bot/core_dailies`` (``monthly_treasure_chest_keys``).  Run it on its own account with
``python -m bot.daily.monthly_treasure_chest_keys``, or through ``start.py``.
"""
from bot.core_dailies import monthly_treasure_chest_keys
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Monthly treasure chest keys"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the monthly treasure chest keys daily...")
    await monthly_treasure_chest_keys(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
