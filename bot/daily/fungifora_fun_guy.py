"""Fungifora fun guy daily.

Logic lives in ``bot/core_dailies`` (``fungifora_fun_guy``).  Run it on its own account with
``python -m bot.daily.fungifora_fun_guy``, or through ``start.py``.
"""
from bot.core_dailies import fungifora_fun_guy
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Fungifora fun guy"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the fungifora fun guy daily...")
    await fungifora_fun_guy(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
