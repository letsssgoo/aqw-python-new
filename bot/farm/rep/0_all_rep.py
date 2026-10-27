"""Every REP in one run -- driven by the registry, so new ones join by themselves.

``FACTION_FARMS`` in ``bot/core_farms`` is the list of reputation farms this
engine actually ports (a new rep is registered there), so this file does not
keep a second copy of it: adding the farm to the registry is what adds it here.
"""
from bot.core_farms import FACTION_FARMS
from bot.script_log import ScriptLog
from core.command import Command

TAG = "All REPs"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    names = list(FACTION_FARMS)
    for name in names:
        log.info(f"--- {name} ---")
        try:
            await FACTION_FARMS[name](cmd)
        except Exception as error:  # noqa: BLE001
            log.error(f"{name} stopped: {type(error).__name__}: {error}")
            return
    log.success(f"{len(names)} reputation farms done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
