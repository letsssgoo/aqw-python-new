"""Enchanted dark blood daily.

Logic lives in ``bot/core_dailies`` (``enchanted_dark_blood``).  Run it on its own account with
``python -m bot.daily.enchanted_dark_blood``, or through ``start.py``.
"""
from bot.core_dailies import enchanted_dark_blood
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Enchanted dark blood"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the enchanted dark blood daily...")
    await enchanted_dark_blood(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
