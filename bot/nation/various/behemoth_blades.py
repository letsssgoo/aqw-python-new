"""Behemoth Blades -- the Shadow and Light blades, bought with brawl trophies.

Port of ``Nation/Various/BehemothBlades.cs``.

Set ``BLADE`` to ``"Shadow"``, ``"Light"`` or ``"Both"`` (the default, which is
the reference's own default): each blade needs a Basic War Sword and a Steel
Afterlife, both bought with Combat Trophies from the Bludrut Brawl.

Note:
    In the reference the purchase looks the blade name up from its *option*
    instead of the blade the loop just asked for, so with the default ``Both`` it
    tries to buy ``"Behemoth Blade of Both"`` -- a name no shop carries, so
    nothing is bought.  The argument is used here, which is what its own
    ``BludrutBrawlBoss``-then-buy pair means.
"""
from core.command import Command
from bot.core_bots import buy_item
from bot.core_farms import bludrut_brawl_boss
from bot.nation.core_nation import equip_class

#: Which blade: ``"Shadow"``, ``"Light"``, or ``"Both"``.
BLADE = "Both"

#: Shop the blades and their parts come from.
SHOP_ID = 222
SHOP_MAP = "battleon"

#: The two parts, and the trophies each one costs.
PARTS = ("Basic War Sword", "Steel Afterlife")
PART_TROPHIES = 50

#: Trophies the blades themselves cost.
BLADE_TROPHIES = 500


async def main(cmd: Command):
    blades = ("Shadow", "Light") if BLADE == "Both" else (BLADE,)
    for blade in blades:
        await behemoth_blade_of(cmd, blade)


async def behemoth_blade_of(cmd: Command, blade: str) -> None:
    """One blade: the parts, then the trophies, then the purchase."""
    item = f"Behemoth Blade of {blade}"
    if await cmd.has_item(item):
        return

    cmd.farming_logger(item, 1)
    await equip_class(cmd, solo=True)

    for part in PARTS:
        if not await cmd.has_item(part):
            await bludrut_brawl_boss(cmd, quant=PART_TROPHIES)
            await buy_item(cmd, SHOP_ID, part)

    await bludrut_brawl_boss(cmd, quant=BLADE_TROPHIES)
    await buy_item(cmd, SHOP_ID, item)
