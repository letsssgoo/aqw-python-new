"""``SynderesMerge`` -- the /enemyforest merge shop (332).

Port of ``Other/MergeShops/SynderesMerge.cs``.  Every item in that shop is built
from ``Synderes' Souvenir``, which is the one ingredient the reference's
``findIngredients`` teaches: quest 4247, registered so the server turns it in on
its own, while ``Evil Elemental`` supplies ``Forest Denizen Slain``.

The Joe kit wants a single entry of it (``NO BOTS Armor`` for ``ShirtAndHat``),
which is what :func:`no_bots_armor` asks for; :func:`buy_all_merge` merges the
whole shop the way the script itself does.
"""
from bot.core_advanced import buy_item, start_buy_all_merge
from bot.core_bots import equip_class, register_quests
from core.command import Command
from templates.hunt import hunt_item

SYNDERES_MAP = "enemyforest"
SYNDERES_SHOP = 332
SOUVENIR = "Synderes' Souvenir"
SOUVENIR_QUEST = 4247
SOUVENIR_KILL_ITEM = "Forest Denizen Slain"
SOUVENIR_MONSTER = "Evil Elemental"
NO_BOTS_ARMOR = "NO BOTS Armor"


async def find_ingredients(cmd: Command, item_id: int, name: str,
                           qty: int) -> None:
    """The merge script's own ``findIngredients`` for ``item_id``/``name``."""
    if name != SOUVENIR:
        cmd.bot.log(f"The bot hasn't been taught how to get {name}.")
        return

    cmd.farming_logger(name, qty)
    await equip_class(cmd)
    await register_quests(cmd, SOUVENIR_QUEST)
    while (cmd.is_still_connected()
           and not await cmd.has_item(name, qty)):
        await hunt_item(cmd, SOUVENIR_KILL_ITEM, 5, SYNDERES_MAP,
                        monster_name=SOUVENIR_MONSTER)
    cmd.cancel_registered_quests()


async def buy_all_merge(cmd: Command, buy_only_this: str = None) -> None:
    """``SynderesMerge.BuyAllMerge``: empty shop 332 in /enemyforest.

    Args:
        cmd (Command): Facade to act through.
        buy_only_this (str): The reference's ``buyOnlyThis``.
    """
    await start_buy_all_merge(cmd, SYNDERES_MAP, SYNDERES_SHOP,
                              find_ingredients, buy_only_this)


async def no_bots_armor(cmd: Command) -> None:
    """``SM.BuyAllMerge(buyOnlyThis: "NO BOTS Armor")`` -- what the kit calls."""
    if await cmd.has_item(NO_BOTS_ARMOR):
        return
    await buy_all_merge(cmd, NO_BOTS_ARMOR)


async def main(cmd: Command):
    await buy_all_merge(cmd)
