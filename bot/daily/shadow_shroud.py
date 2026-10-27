"""Shadow shroud daily.

Logic lives in ``bot/core_dailies`` (``shadow_shroud``).  Run it on its own account with
``python -m bot.daily.shadow_shroud``, or through ``start.py``.
"""
from bot.core_dailies import shadow_shroud
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Shadow shroud"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the shadow shroud daily...")
    await shadow_shroud(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
