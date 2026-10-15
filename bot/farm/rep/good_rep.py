"""Good REP: farm Good reputation to ``RANK``.

Port of ``Farm/REP/GoodREP.cs``.  The logic lives in ``bot/core_farms``.

The reference runs the /PoisonForest storyline first so the better method is
available.  That story is not ported; ``good_rep`` notices the quest is missing
and falls back to the lower-reward route the reference itself documents for
exactly this case (quest 369, then 371 for members or 372 for the rest).
"""
from core.command import Command
from bot.core_farms import good_rep

#: Rank to stop at, 1-10.
RANK = 10


async def main(cmd: Command):
    await good_rep(cmd, RANK)
