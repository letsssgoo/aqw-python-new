"""ThunderForge Rep REP: farm ThunderForge reputation to ``RANK``.

Port of ``Farm/REP/ThunderForgeREP.cs``.  The logic lives in ``bot/core_farms``.

Run it on its own account with ``python -m bot.farm.rep.thunderforge_rep``, or through
``start.py`` by entering ``bot.farm.rep.thunderforge_rep`` as the bot path.
"""
from bot.core_farms import thunderforge_rep
from bot.script_log import ScriptLog
from core.command import Command

#: Rank to stop at, 1-10.
RANK = 10

TAG = "ThunderForge REP"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info(f"Farming ThunderForge reputation to rank {RANK}...")
    await thunderforge_rep(cmd, RANK)
    log.success(f"ThunderForge reputation done (rank {RANK}).")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
