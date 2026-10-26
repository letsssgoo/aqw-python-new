"""Cape of Awe -- the relic, then the cape itself.

Port of ``Good/GearOfAwe/CapeOfAwe.cs``.  The relic comes from
:func:`bot.other.gear_of_awe.core_awe.get_awe_relic` (quest 4178's family), and
both it and the cape are sold by the Awe shop in /museum (1129).

``Core.ToBank`` on the three Awe passes is kept: they clutter the bag and nothing
here consumes them.
"""
from bot.core_bots import buy_item
from bot.other.gear_of_awe.core_awe import AWE_SHOP, AWE_SHOP_MAP, get_awe_relic
from core.command import Command

CAPE = "Cape of Awe"
#: ``Awe.GetAweRelic("Cape", 4178, 1, 1, "doomvault", "Binky")``.
CAPE_QUEST = 4178
CAPE_MAP = "doomvault"
CAPE_MONSTER = "Binky"
#: ``Core.ToBank("Legendary Awe Pass", "Guardian Awe Pass", "Armor of Awe Pass")``.
AWE_PASSES = ("Legendary Awe Pass", "Guardian Awe Pass", "Armor of Awe Pass")


async def get_coa(cmd: Command) -> None:
    """``CapeOfAwe.GetCoA``."""
    if await cmd.has_item(CAPE):
        return

    await get_awe_relic(cmd, "Cape", CAPE_QUEST, 1, 1, CAPE_MAP, CAPE_MONSTER)
    await buy_item(cmd, AWE_SHOP, CAPE, map_name=AWE_SHOP_MAP)

    await cmd.inv_to_bank(list(AWE_PASSES))


async def main(cmd: Command):
    await get_coa(cmd)
