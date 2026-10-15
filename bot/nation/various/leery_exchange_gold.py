"""Leery Exchange (Gold) -- turn Unidentified 13 into gold, quest 554.

Port of ``Nation/Various/LeeryExchange(gold).cs``.  The logic lives in
``bot.nation.core_nation``.

Members only, and the reference's gold boost is reported rather than applied --
this engine has no boost-item support.
"""
from core.command import Command
from bot.nation.core_nation import leery_exchange_gold

#: Gold to stop at.
QUANT = 100_000_000


async def main(cmd: Command):
    await leery_exchange_gold(cmd, QUANT)
