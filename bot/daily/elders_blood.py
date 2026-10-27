"""Elders blood daily.

Logic lives in ``bot/core_dailies`` (``elders_blood``).  Run it on its own account with
``python -m bot.daily.elders_blood``, or through ``start.py``.
"""
from bot.core_dailies import elders_blood
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Elders blood"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the elders blood daily...")
    await elders_blood(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
