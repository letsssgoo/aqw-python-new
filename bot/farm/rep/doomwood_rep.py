"""Doomwood Rep REP: farm DoomWood reputation to ``RANK``.

Port of ``Farm/REP/DoomwoodREP.cs``.  The logic lives in ``bot/core_farms``.

Run it on its own account with ``python -m bot.farm.rep.doomwood_rep``, or through
``start.py`` by entering ``bot.farm.rep.doomwood_rep`` as the bot path.
"""
from bot.core_farms import doomwood_rep
from bot.script_log import ScriptLog
from core.command import Command

#: Rank to stop at, 1-10.
RANK = 10

TAG = "DoomWood REP"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info(f"Farming DoomWood reputation to rank {RANK}...")
    await doomwood_rep(cmd, RANK)
    log.success(f"DoomWood reputation done (rank {RANK}).")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
