"""Blade of awe rep: farm Blade of Awe reputation to ``RANK``.

Port of ``Farm/REP/BladeofAweREP.cs``.  The logic lives in ``bot/core_farms``.

Run it on its own account with ``python -m bot.farm.rep.blade_of_awe_rep``, or through
``start.py`` by entering ``bot.farm.rep.blade_of_awe_rep`` as the bot path.
"""
from bot.core_farms import blade_of_awe_rep
from bot.script_log import ScriptLog
from core.command import Command

#: Rank to stop at, 1-10.
RANK = 10
#: Also unlock and buy the Blade of Awe itself.
FARM_BOA = True

TAG = "Blade of Awe REP"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info(f"Farming Blade of Awe reputation to rank {RANK}...")
    await blade_of_awe_rep(cmd, RANK, FARM_BOA)
    log.success(f"Blade of Awe reputation done (rank {RANK}).")


if __name__ == "__main__":
    # Runs this script on its own account, the way
    # ``bot/enhancements/valiance.py`` does.
    from bot.standalone import run_standalone

    run_standalone(main)
