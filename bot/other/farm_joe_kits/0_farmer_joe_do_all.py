"""FarmerJoeKit0DoAll -- the whole Farmer Joe progression in one run.

Port of ``Other/FarmJoeKits/0FarmerJoeDoAll.cs``, which is a wrapper around
``CoreFarmerJoe.DoAll``; the logic lives in ``bot.other.farm_joe_kits.core_farmer_joe``.
Its ``BAI.BankAll()`` is commented out in the reference as well, so there is no
banking pass to run.
"""
from core.command import Command
from bot.other.farm_joe_kits.core_farmer_joe import do_all


async def main(cmd: Command):
    await do_all(cmd)
