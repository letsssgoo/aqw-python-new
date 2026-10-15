"""Farm Fiend Emblem -- ``/originul``, quest 7890.

Port of the reference bot's ``Nation/Materials/FiendEmblem.cs``.  Unlike its neighbours that
script holds its own quest logic instead of calling ``CoreNation``; the ported
body sits in ``bot.nation.core_nation.fiend_emblem`` so the naming stays
uniform.
"""
from core.command import Command
from bot.nation.core_nation import fiend_emblem


async def main(cmd: Command):
    await fiend_emblem(cmd, 300)
