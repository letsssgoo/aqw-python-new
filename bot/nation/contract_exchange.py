"""Farm the Contract Exchange (quest 870) rewards.

Port of ``Nation/ContractExchange.cs``.  The C# script asks which reward to
take; here you set it below, or leave ``ITEM = None`` to walk all four.

Choose one:
  * ``None``                     -- all four below
  * ``"Tainted Gem"``
  * ``"Dark Crystal Shard"``
  * ``"Gem of Nulgath"``
  * ``"Blood Gem of the Archfiend"``
"""
from core.command import Command
from bot.nation.core_nation import farm_contract_exchage

#: Change to one of the above.
ITEM = None
QUANT = 1000


async def main(cmd: Command):
    await farm_contract_exchage(cmd, ITEM, QUANT)
