"""Necro Crypt Rep REP: farm Necro Crypt reputation to ``RANK``.

Port of ``Farm/REP/NecroCryptREP.cs``.  The logic lives in ``bot/core_farms``.

Run it on its own account with ``python -m bot.farm.rep.necro_crypt_rep``, or through
``start.py`` by entering ``bot.farm.rep.necro_crypt_rep`` as the bot path.
"""
from bot.core_farms import necro_crypt_rep
from bot.script_log import ScriptLog
from core.command import Command

#: Rank to stop at, 1-10.
RANK = 10

TAG = "Necro Crypt REP"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info(f"Farming Necro Crypt reputation to rank {RANK}...")
    await necro_crypt_rep(cmd, RANK)
    log.success(f"Necro Crypt reputation done (rank {RANK}).")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
