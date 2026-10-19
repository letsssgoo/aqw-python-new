"""Seaview Souvenirs Merge -- shop 2273 in /ashray.

Port of ``Other/MergeShops/SeaviewSouvenirsMerge.cs``.  The merge walk is the
engine's generic :func:`bot.core_advanced.start_buy_all_merge`; this file owns
the shop's own part: the story lead-in and the two items it does not sell.

The lead-in is ``AoR.AshrayVillage()``, ported as
:func:`bot.story.age_of_ruin.core_aor.ashray_village`.  The recipe itself comes
from the shop payload -- see ``tools/test_merge.py``, which pins it against a
real capture of this very shop.
"""
from typing import Optional, Sequence

from bot.core_advanced import start_buy_all_merge
from bot.core_bots import equip_class
from bot.story.age_of_ruin.core_aor import ashray_village
from core.command import Command
from templates.hunt import hunt_item

MAP = "ashray"
SHOP_ID = 2273

#: ``Sur-gion Token``'s quest (9235) and the farm of one pass of it.
TOKEN_QUEST = 9235
TOKEN_FARM = (("Shark Fin", "Kitefin Shark Bait", 7, "Enter", "Spawn"),
              ("Ashray Blood Sample", "Ashray Fisherman", 7, "r2", "Left"))
TOKEN_SOLO = ("Seafoam Bubbles", "Seafoam Elemental")

#: ``Treasure Chest`` drops in /finalbattle, r2/Left, from anything.
CHEST_MAP, CHEST_CELL, CHEST_PAD = "finalbattle", "r2", "Left"


async def seaview_souvenirs_merge(cmd: Command,
                                  buy_only_this: Optional[str] = None,
                                  item_blacklist: Sequence[str] = ()) -> None:
    """``SeaviewSouvenirsMerge.BuyAllMerge``."""
    await ashray_village(cmd)
    await start_buy_all_merge(cmd, MAP, SHOP_ID,
                              find_ingredients=_find_ingredients,
                              buy_only_this=buy_only_this,
                              item_blacklist=item_blacklist)


async def _find_ingredients(cmd: Command, item_id, name: str,
                            quant: int) -> None:
    """``findIngredients``: the two items this shop does not sell itself."""
    if name == "Treasure Chest":
        await equip_class(cmd)
        await hunt_item(cmd, name, quant, CHEST_MAP, cell=CHEST_CELL,
                        pad=CHEST_PAD, monster_name="*", is_temp=False)
        return

    if name == "Sur-gion Token":
        await cmd.register_quest(TOKEN_QUEST)
        while cmd.is_still_connected() and not await cmd.has_item(name, quant):
            await equip_class(cmd)
            for item, monster, qty, cell, pad in TOKEN_FARM:
                await hunt_item(cmd, item, qty, MAP, cell=cell, pad=pad,
                                monster_name=monster, is_temp=True)
            await equip_class(cmd, solo=True)
            await hunt_item(cmd, TOKEN_SOLO[0], 1, MAP,
                            monster_name=TOKEN_SOLO[1], is_temp=True)
        cmd.cancel_registered_quests()
        return

    cmd.bot.log(f'[merge] "{name}" is not one of Seaview Souvenirs Merge\'s '
                f'ingredients (Treasure Chest, Sur-gion Token); skipping it.')


async def main(cmd: Command):
    await seaview_souvenirs_merge(cmd)
