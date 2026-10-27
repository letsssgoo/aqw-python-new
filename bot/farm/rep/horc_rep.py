"""Horc Rep REP: farm Horc reputation to ``RANK``.

Port of ``Farm/REP/HorcREP.cs``.  The logic lives in ``bot/core_farms``.

Run it on its own account with ``python -m bot.farm.rep.horc_rep``, or through
``start.py`` by entering ``bot.farm.rep.horc_rep`` as the bot path.
"""
from bot.core_farms import horc_rep
from bot.script_log import ScriptLog
from core.command import Command

#: Rank to stop at, 1-10.
RANK = 10

TAG = "Horc REP"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info(f"Farming Horc reputation to rank {RANK}...")
    await horc_rep(cmd, RANK)
    log.success(f"Horc reputation done (rank {RANK}).")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
