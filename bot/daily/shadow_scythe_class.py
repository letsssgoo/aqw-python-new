"""Shadow scythe class daily.

Logic lives in ``bot/core_dailies`` (``shadow_scythe_class``).  Run it on its own account with
``python -m bot.daily.shadow_scythe_class``, or through ``start.py``.
"""
from bot.core_dailies import shadow_scythe_class
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Shadow scythe class"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the shadow scythe class daily...")
    await shadow_scythe_class(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
