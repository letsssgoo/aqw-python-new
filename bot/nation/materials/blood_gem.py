"""Farm Blood Gem of the Archfiend.

Port of ``Nation/Materials/BloodGem.cs``.  The C# script offers a choice
between the Bloody Chaos route and the plain farm, with a Hydra level option;
``farm_blood_gem`` already walks every route including Bloody Chaos, so the
choice is not needed here.
"""
from core.command import Command
from bot.nation.core_nation import farm_blood_gem


async def main(cmd: Command):
    await farm_blood_gem(cmd, 100)
