"""Void Crystals -- only Void Crystal A and B of the Void Highlord class.

Port of ``Nation/VHL/VoidCrystals.cs``; the logic lives in
``bot.nation.vhl.core_vhl``.  The same banking-blacklist and options note as
``0_void_highlord`` applies.
"""
from core.command import Command
from bot.nation.vhl.core_vhl import vhl_crystals


async def main(cmd: Command):
    await vhl_crystals(cmd)
