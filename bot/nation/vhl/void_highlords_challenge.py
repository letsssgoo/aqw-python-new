"""Void Highlord's Challenge -- only the Roentgenium of Nulgath tokens.

Port of ``Nation/VHL/VoidHighlordsChallenge.cs``; the logic lives in
``bot.nation.vhl.core_vhl``.  The script asks for 25 tokens, which is the
reference's own count.  The same banking-blacklist and options note as
``0_void_highlord`` applies.
"""
from core.command import Command
from bot.nation.vhl.core_vhl import vhl_challenge

#: ``VHL.VHLChallenge(25)`` -- how many Roentgenium the script farms.
QUANT = 25


async def main(cmd: Command):
    await vhl_challenge(cmd, QUANT)
