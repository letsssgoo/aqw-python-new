"""Every daily in one run, through the reference's own ``daily_routine``.

A daily added to ``bot/core_dailies`` (and to ``daily_routine`` there) is picked
up here without touching this file; the individual ``bot/daily/<name>.py``
modules are for running one on its own.
"""
from bot.core_dailies import daily_routine
from bot.script_log import ScriptLog
from core.command import Command

TAG = "All Dailies"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running every ported daily...")
    await daily_routine(cmd)
    log.success("Dailies finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
