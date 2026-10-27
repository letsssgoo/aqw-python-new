"""Burning Blade Of Abezeth -- the arena's 20 sashes, then the shop.

Port of ``Other/Weapons/BurningBladeOfAbezeth.cs``.  The source keeps its
``CelestialChampMerge`` route commented out ("Other method until it's fixed") and
buys the blade from the /celestialarena shop 1474 instead; that is what this does.

``Adv.EnhanceItem("Burning Blade Of Abezeth", EnhancementType.Lucky)`` runs last:
:func:`bot.core_advanced.enhance_item` is the same "pick the Lucky enhancement and
socket it" step.
"""
from bot.core_advanced import buy_item, enhance_item
from bot.core_bots import equip_class
from bot.story.queen_of_monsters.celestial_arena import do_all as arena_do_all
from core.command import Command
from templates.hunt import hunt_item
from bot.script_log import ScriptLog
TAG = "Burning Blade"

BBOA = "Burning Blade Of Abezeth"
SHOP_MAP = "celestialarena"
SHOP_ID = 1474
#: ``Core.HuntMonster("celestialarenad", "Aranx", "Champion Sash", 20, isTemp: false)``.
SASH = "Champion Sash"
SASH_QUANT = 20
ARENA_MAP = "celestialarenad"
ARENA_BOSS = "Aranx"
ENHANCEMENT = "Lucky"


async def get_bboa(cmd: Command) -> None:
    """``BurningBladeOfAbezeth.GetBBoA``."""
    if await cmd.has_item(BBOA):
        return

    await arena_do_all(cmd)

    await equip_class(cmd, solo=True)
    await hunt_item(cmd, SASH, SASH_QUANT, ARENA_MAP, monster_name=ARENA_BOSS,
                    is_temp=False)

    await buy_item(cmd, SHOP_ID, BBOA, map_name=SHOP_MAP)
    await enhance_item(cmd, BBOA, ENHANCEMENT)


async def main(cmd: Command):
    await get_bboa(cmd)
