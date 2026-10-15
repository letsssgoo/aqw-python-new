"""Vampire REP: farm Vampire reputation to ``RANK``.

Port of ``Farm/REP/VampireREP.cs``.  The logic lives in ``bot/core_farms``.

The reference runs ``Core13LoC.Wolfwing()`` first; that story is not ported, so
``vampire_rep`` asks the server to accept quest 522 and stops with a report when
it refuses -- which is what an unfinished /safiria story produces.
"""
from core.command import Command
from bot.core_farms import vampire_rep

#: Rank to stop at, 1-10.
RANK = 10


async def main(cmd: Command):
    await vampire_rep(cmd, RANK)
