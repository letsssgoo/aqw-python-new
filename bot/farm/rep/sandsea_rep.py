"""Sandsea rep: farm Sandsea reputation to ``RANK``.

Port of ``Farm/REP/SandseaREP.cs``.  The logic lives in ``bot/core_farms``.

Run it on its own account with ``python -m bot.farm.rep.sandsea_rep``, or through
``start.py`` by entering ``bot.farm.rep.sandsea_rep`` as the bot path.
"""
from bot.core_farms import sandsea_rep
from bot.script_log import ScriptLog
from core.command import Command

#: Rank to stop at, 1-10.
RANK = 10

TAG = "Sandsea REP"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info(f"Farming Sandsea reputation to rank {RANK}...")
    await sandsea_rep(cmd, RANK)
    log.success(f"Sandsea reputation done (rank {RANK}).")


if __name__ == "__main__":
    # Runs this script on its own account, the way
    # ``bot/enhancements/valiance.py`` does.
    from bot.standalone import run_standalone

    run_standalone(main)
