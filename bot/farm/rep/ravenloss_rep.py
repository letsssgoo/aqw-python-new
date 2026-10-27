"""Ravenloss Rep REP: farm Ravenloss reputation to ``RANK``.

Port of ``Farm/REP/RavenlossREP.cs``.  The logic lives in ``bot/core_farms``.

Run it on its own account with ``python -m bot.farm.rep.ravenloss_rep``, or through
``start.py`` by entering ``bot.farm.rep.ravenloss_rep`` as the bot path.
"""
from bot.core_farms import ravenloss_rep
from bot.script_log import ScriptLog
from core.command import Command

#: Rank to stop at, 1-10.
RANK = 10

TAG = "Ravenloss REP"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info(f"Farming Ravenloss reputation to rank {RANK}...")
    await ravenloss_rep(cmd, RANK)
    log.success(f"Ravenloss reputation done (rank {RANK}).")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
