"""Trench Observe Merge -- shop 2316 in /trenchobserve.

Port of ``Other/MergeShops/TrenchObserveMerge.cs``.  The merge walk is the
engine's generic :func:`bot.core_advanced.start_buy_all_merge`; this file owns
the shop's own part: the story lead-in and the items it does not sell.

The lead-in is ``AoR.DeepWater()``, ported as
:func:`bot.story.age_of_ruin.core_aor.deep_water`.
"""
from typing import Optional, Sequence

from bot.core_advanced import farm_quest_reward, start_buy_all_merge
from bot.core_bots import equip_class
from bot.other.merge_shops.abyssal_zone_merge import abyssal_zone_merge
from bot.other.merge_shops.midnight_zone_merge import _kill_once
from bot.story.age_of_ruin.core_aor import deep_water
from core.command import Command
from templates.hunt import hunt_item

MAP = "trenchobserve"
SHOP_ID = 2316

#: ``Dark Elf Pearl``'s quest (9339) and one pass of it.  The third step kills a
#: monster that drops nothing, so ``_kill_once`` is used, as in the two shops
#: above.
PEARL_QUEST = 9339
PEARL_SOLO = ("Noelle's Brooch", "Lady Noelle")
PEARL_FARM = (("Green Sea Jelly", "Sea Spirit", 2),)
PEARL_KILL = "Necro Adipocere"

BASE_SCRIP = "Undine Base Scrip"
#: Items the Abyssal Zone shop merges; this shop hands them straight over to it,
#: exactly as the source's ``AZM.BuyAllMerge(req.Name)`` does.
ABYSSAL_ITEMS = ("Ashray Elf Top Knot", "Ashray Elf Warden", "Ashray Elf Locks",
                 "Ashray Top Knot and Horns", "Ashray Locks and Horns",
                 "Coastal Corona", "Golden Ashray Trident",
                 "Dancer's Sea Streams")


async def trench_observe_merge(cmd: Command,
                               buy_only_this: Optional[str] = None,
                               item_blacklist: Sequence[str] = ()) -> None:
    """``TrenchObserveMerge.BuyAllMerge``."""
    await deep_water(cmd)
    await start_buy_all_merge(cmd, MAP, SHOP_ID,
                              find_ingredients=_find_ingredients,
                              buy_only_this=buy_only_this,
                              item_blacklist=item_blacklist)


async def _find_ingredients(cmd: Command, item_id, name: str,
                            quant: int) -> None:
    """``findIngredients``: the story lead-in's three groups."""
    if name == BASE_SCRIP:
        await equip_class(cmd)
        await hunt_item(cmd, name, quant, "sunlightzone",
                        monster_name="Infernal Illusion", is_temp=False)
        return

    if name == "Dark Elf Pearl":
        async def farm_pass() -> None:
            await equip_class(cmd, solo=True)
            await hunt_item(cmd, PEARL_SOLO[0], 1, MAP,
                            monster_name=PEARL_SOLO[1], is_temp=True)
            await equip_class(cmd)
            for item, monster, qty in PEARL_FARM:
                await hunt_item(cmd, item, qty, MAP, monster_name=monster,
                                is_temp=True)
            await _kill_once(cmd, MAP, PEARL_KILL)

        await farm_quest_reward(cmd, PEARL_QUEST, name, quant, farm_pass)
        cmd.cancel_registered_quests()
        return

    if name in ABYSSAL_ITEMS:
        # The source delegates these to the Abyssal Zone shop's own merge.
        await abyssal_zone_merge(cmd, buy_only_this=name)
        return

    cmd.bot.log(f'[merge] "{name}" is not one of Trench Observe Merge\'s '
                f"ingredients ({BASE_SCRIP}, Dark Elf Pearl, and the Ashray set "
                f"the Abyssal Zone shop merges); skipping it.")


async def main(cmd: Command):
    await trench_observe_merge(cmd)
