"""Void Highlord (Class) -- the whole class: challenge tokens and both crystals.

Port of ``Nation/VHL/0VoidHighlord.cs``; the logic lives in
``bot.nation.vhl.core_vhl``.  The C# seeds its banking blacklist with the Nation
bag drops first, and this engine never auto-banks, so there is nothing to seed --
the note ``materials/0_max_bags.py`` carries too.  Its two ``Core.SetOptions``
calls are the reference's option window, which the port replaces with the
constants at the top of ``core_vhl``.
"""
from core.command import Command
from bot.nation.vhl.core_vhl import get_vhl


async def main(cmd: Command):
    await get_vhl(cmd)
