"""Mythsong Rep REP: farm Mythsong reputation to ``RANK``.

Port of ``Farm/REP/MythSongREP.cs``.  The logic lives in ``bot/core_farms``.

Run it on its own account with ``python -m bot.farm.rep.mythsong_rep``, or through
``start.py`` by entering ``bot.farm.rep.mythsong_rep`` as the bot path.
"""
from bot.core_farms import mythsong_rep
from bot.script_log import ScriptLog
from core.command import Command

#: Rank to stop at, 1-10.
RANK = 10

TAG = "Mythsong REP"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info(f"Farming Mythsong reputation to rank {RANK}...")
    await mythsong_rep(cmd, RANK)
    log.success(f"Mythsong reputation done (rank {RANK}).")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
