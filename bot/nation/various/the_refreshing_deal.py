"""The Refreshing Deal -- quest 4777, for Gems and Totems of Nulgath.

Port of ``Nation/Various/TheRefreshingDeal.cs``, which is one line around
``CoreNation.Deal``.  The logic lives in ``bot.nation.core_nation.deal``.

Its three options are constants here: how many of each reward, and whether to
bank the Nation drops when it finishes.
"""
from core.command import Command
from bot.nation.core_nation import BAG_DROPS, deal

#: How many of each.  The reference defaults to a full stack of each.
GEM_QUANTITY = 1000
TOTEM_QUANTITY = 100

#: Bank the Nation drops when it finishes (the reference's ``BankItems``).
BANK_ITEMS = False


async def main(cmd: Command):
    await deal(cmd, gem_quant=GEM_QUANTITY, totem_quant=TOTEM_QUANTITY)
    if BANK_ITEMS:
        await cmd.inv_to_bank(list(BAG_DROPS))
