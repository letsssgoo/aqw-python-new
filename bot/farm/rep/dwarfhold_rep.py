"""Dwarfhold Rep REP: farm Dwarfhold reputation to ``RANK``.

Port of ``Farm/REP/DwarfholdREP.cs``.  The logic lives in ``bot/core_farms``.

Run it on its own account with ``python -m bot.farm.rep.dwarfhold_rep``, or through
``start.py`` by entering ``bot.farm.rep.dwarfhold_rep`` as the bot path.
"""
from bot.core_farms import dwarfhold_rep
from bot.script_log import ScriptLog
from core.command import Command

#: Rank to stop at, 1-10.
RANK = 10

TAG = "Dwarfhold REP"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info(f"Farming Dwarfhold reputation to rank {RANK}...")
    await dwarfhold_rep(cmd, RANK)
    log.success(f"Dwarfhold reputation done (rank {RANK}).")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
