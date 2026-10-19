"""Undine Commissary Merge -- shop 2288 in /sunlightzone.

Port of ``Other/MergeShops/UndineCommissaryMerge.cs``.  The merge walk is the
engine's generic :func:`bot.core_advanced.start_buy_all_merge`; this file owns
the shop's own part: the story lead-in and the two items it does not sell.

The lead-in is ``AoR.SunlightZone()``, ported as
:func:`bot.story.age_of_ruin.core_aor.sunlight_zone`.
"""
from typing import Optional, Sequence

from bot.core_advanced import start_buy_all_merge
from bot.story.age_of_ruin.core_aor import sunlight_zone
from core.command import Command
from templates.hunt import hunt_item

MAP = "sunlightzone"
SHOP_ID = 2288

#: ``Sun Zone Chit``'s quest, and the three drops one pass of it wants.
CHIT_QUEST = 9252
CHIT_HUNTS = (("Marine Sample", "Marine Snow", 1),
              ("Infernal Sample", "Infernal Illusion", 10),
              ("Seraphic Sample", "Seraphic Illusion", 10))
BASE_SCRIP = "Undine Base Scrip"


async def undine_commissary_merge(cmd: Command,
                                  buy_only_this: Optional[str] = None,
                                  item_blacklist: Sequence[str] = ()) -> None:
    """``UndineCommissaryMerge.BuyAllMerge``."""
    await sunlight_zone(cmd)
    await start_buy_all_merge(cmd, MAP, SHOP_ID,
                              find_ingredients=_find_ingredients,
                              buy_only_this=buy_only_this,
                              item_blacklist=item_blacklist)


async def _find_ingredients(cmd: Command, item_id, name: str,
                            quant: int) -> None:
    """``findIngredients``: the two items this shop does not sell itself."""
    if name == BASE_SCRIP:
        await hunt_item(cmd, name, quant, MAP, monster_name="Marine Snow",
                        is_temp=False)
        return

    if name == "Sun Zone Chit":
        await cmd.register_quest(CHIT_QUEST)
        while cmd.is_still_connected() and not await cmd.has_item(name, quant):
            for item, monster, qty in CHIT_HUNTS:
                await hunt_item(cmd, item, qty, MAP, monster_name=monster,
                                is_temp=True)
        cmd.cancel_registered_quests()
        return

    cmd.bot.log(f'[merge] "{name}" is not one of Undine Commissary Merge\'s '
                f'ingredients ({BASE_SCRIP}, Sun Zone Chit); skipping it.')


async def main(cmd: Command):
    await undine_commissary_merge(cmd)
