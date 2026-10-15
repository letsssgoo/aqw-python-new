"""Farm Fiend Token.

Port of ``Nation/Materials/FiendToken.cs``.  The C# also calls
``HanzoOrbQuest.HanzoOrb`` for non-members; that script is outside Nation and
is not ported, so the three routes inside ``farm_fiend_token`` are what run.
"""
from core.command import Command
from bot.nation.core_nation import farm_fiend_token


async def main(cmd: Command):
    await farm_fiend_token(cmd, 30)
