"""Abyssal Zone Merge -- shop 2304 in /abyssalzone.

Port of ``Other/MergeShops/AbyssalZoneMerge.cs``.  The merge walk is the engine's
generic :func:`bot.core_advanced.start_buy_all_merge`; this file owns the shop's
own part: the story lead-in and the three items it does not sell.

The lead-in is ``AoR.AbyssalZone()``, ported as
:func:`bot.story.age_of_ruin.core_aor.abyssal_zone`.
"""
from typing import Optional, Sequence

from bot.core_advanced import farm_quest_reward, start_buy_all_merge
from bot.core_bots import equip_class
from bot.other.merge_shops.midnight_zone_merge import _kill_once
from bot.story.age_of_ruin.core_aor import abyssal_zone
from core.command import Command
from templates.hunt import hunt_item

MAP = "abyssalzone"
SHOP_ID = 2304

#: ``Water Elf Antler``'s quest (9316) and one pass of it.  The third step is a
#: kill with no item of its own, like Midnight Zone's, so ``_kill_once`` is used.
ANTLER_QUEST = 9316
ANTLER_SOLO = ("Ashray Artifacts", "The Ashray", 1)
ANTLER_FARM = (("Adipocere Antler", "Necro Adipocere", 3),)
ANTLER_KILL = "Foam Scavenger"

BASE_SCRIP = "Undine Base Scrip"
WAVES = "Waves of Tumult"


async def abyssal_zone_merge(cmd: Command,
                             buy_only_this: Optional[str] = None,
                             item_blacklist: Sequence[str] = ()) -> None:
    """``AbyssalZoneMerge.BuyAllMerge``."""
    await abyssal_zone(cmd)
    await start_buy_all_merge(cmd, MAP, SHOP_ID,
                              find_ingredients=_find_ingredients,
                              buy_only_this=buy_only_this,
                              item_blacklist=item_blacklist)


async def _find_ingredients(cmd: Command, item_id, name: str,
                            quant: int) -> None:
    """``findIngredients``: the three items this shop does not sell itself."""
    if name == BASE_SCRIP:
        await equip_class(cmd)
        await hunt_item(cmd, name, quant, MAP, monster_name="Kitefin Shark Bait",
                        is_temp=False)
        return

    if name == WAVES:
        await equip_class(cmd)
        await hunt_item(cmd, name, quant, MAP, monster_name="Blighted Water",
                        is_temp=False)
        return

    if name == "Water Elf Antler":
        async def farm_pass() -> None:
            await equip_class(cmd, solo=True)
            await hunt_item(cmd, ANTLER_SOLO[0], ANTLER_SOLO[2], MAP,
                            monster_name=ANTLER_SOLO[1], is_temp=True)
            for item, monster, qty in ANTLER_FARM:
                await hunt_item(cmd, item, qty, MAP, monster_name=monster,
                                is_temp=True)
            await _kill_once(cmd, MAP, ANTLER_KILL)

        await farm_quest_reward(cmd, ANTLER_QUEST, name, quant, farm_pass)
        cmd.cancel_registered_quests()
        return

    cmd.bot.log(f'[merge] "{name}" is not one of Abyssal Zone Merge\'s '
                f"ingredients ({BASE_SCRIP}, Water Elf Antler, {WAVES}); "
                f"skipping it.")


async def main(cmd: Command):
    await abyssal_zone_merge(cmd)
