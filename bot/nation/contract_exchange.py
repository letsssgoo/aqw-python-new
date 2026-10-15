"""Farm the Contract Exchange (quest 870) rewards.

Port of ``Nation/ContractExchange.cs``.  The C# script asks which reward to
take; here ``farm_contract_exchage(cmd, "<reward name>", qty)`` picks one and
the no-argument form walks all four.
"""
from core.command import Command
from bot.nation.core_nation import farm_contract_exchage


async def main(cmd: Command):
    await farm_contract_exchage(cmd)
