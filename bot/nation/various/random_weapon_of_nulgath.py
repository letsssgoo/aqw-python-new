"""Random Weapon of Nulgath -- one of the Supplies rewards.

Port of ``Nation/Various/RandomWeaponOfNulgath.cs``, which is one line around
``CoreNation.Supplies``.
"""
from core.command import Command
from bot.nation.core_nation import supplies

#: The reward to farm.
ITEM = "Random Weapon of Nulgath"


async def main(cmd: Command):
    await supplies(cmd, ITEM)
