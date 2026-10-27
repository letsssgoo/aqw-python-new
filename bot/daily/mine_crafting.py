"""Mine crafting daily.

Logic lives in ``bot/core_dailies`` (``mine_crafting``).  Run it on its own account with
``python -m bot.daily.mine_crafting``, or through ``start.py``.
"""
from bot.core_dailies import mine_crafting
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Mine crafting"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the mine crafting daily...")
    await mine_crafting(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
