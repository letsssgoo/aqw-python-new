"""Dirtlickers Merge -- shop 1211 in /archportal.

Port of ``Nation/MergeShops/DirtlickersMerge.cs``.  The merge walk is the
engine's generic one; this file owns the ingredients the shop does not sell.
Each case below is the reference's own case, unchanged:

* Nation farms for Approval/Favor, Diamond, Totem, Voucher, Uni 10/13, Dark
  Crystal, Tainted Gem, Gem and Essence;
* ``Pink Star Diamond`` bought from ``/tercessuinotlim`` shop 1951;
* monster drops: ``Musgravite`` (timelibrary Ancient Chest), ``Hadean Onyx``
  (tercessuinotlim Shadow of Nulgath), ``Letter from Asuka and Tendou`` (citadel
  Burning Witch), ``Chain of Nulgath`` (necrocavern Shadow Dragon), ``Yulgath's
  Hut`` (originul Fiend Champion).

Two cases need scripts this repo does not have -- the member ``ForgeTaintedGems``
path and the ``Nulgath Nation House`` / ``Corpse Maker`` / ``Overfiend Blade``
quest chains (BLOD, The Leery Contract, Juggernaut Items).  They are reported by
name rather than guessed.
"""
from typing import Optional

from bot.core_advanced import start_buy_all_merge
from bot.core_bots import buy_item
from bot.nation.core_nation import (approval_and_favor, essence_of_nulgath,
                                    farm_dark_crystal_shard,
                                    farm_diamond_of_nulgath, farm_gem_of_nulgath,
                                    farm_tainted_gem, farm_totem_of_nulgath,
                                    farm_uni10, farm_uni13_quest, farm_voucher)
from core.command import Command
from templates.hunt import hunt_item

MAP = "archportal"
SHOP_ID = 1211
IRON_DREADSAW = "Iron Dreadsaw"


async def find_ingredients(cmd: Command, item_id: int, name: str,
                           quantity: int) -> None:
    """``findIngredients`` from the merge script."""
    if name == "Pink Star Diamond of Nulgath":
        await buy_item(cmd, 1951, name, quantity, map_name="tercessuinotlim")
    elif name == "Musgravite of Nulgath":
        await hunt_item(cmd, name, quantity, "timelibrary", cell="Enter",
                        pad="Spawn", monster_name="Ancient Chest",
                        is_temp=False)
    elif name == "Nulgath's Approval":
        await approval_and_favor(cmd, quantity, 0)
    elif name == "Archfiend's Favor":
        await approval_and_favor(cmd, 0, quantity)
    elif name == "Diamond of Nulgath":
        # The reference asks for 300 here, not for the recipe's quantity.
        await farm_diamond_of_nulgath(cmd, 300)
    elif name == "Totem of Nulgath":
        await farm_totem_of_nulgath(cmd, quantity)
    elif name == "Voucher of Nulgath (non-mem)":
        await farm_voucher(cmd, False, keep_voucher=True)
    elif name == "Voucher of Nulgath":
        await farm_voucher(cmd, True, keep_voucher=True)
    elif name == "Unidentified 13":
        await farm_uni13_quest(cmd, quantity)
    elif name == "Unidentified 10":
        await farm_uni10(cmd, quantity)
    elif name == "Dark Crystal Shard":
        await farm_dark_crystal_shard(cmd, quantity)
    elif name == "Tainted Gem":
        await farm_tainted_gem(cmd, quantity)
    elif name == "Gem of Nulgath":
        await farm_gem_of_nulgath(cmd, quantity)
    elif name == "Essence of Nulgath":
        await essence_of_nulgath(cmd, quantity)
    elif name == "Hadean Onyx of Nulgath":
        await hunt_item(cmd, name, quantity, "tercessuinotlim", cell="m4",
                        pad="Right", monster_name="Shadow of Nulgath",
                        is_temp=False)
    elif name == "Letter from Asuka and Tendou":
        await hunt_item(cmd, name, quantity, "citadel", cell="Enter",
                        pad="Spawn", monster_name="Burning Witch",
                        is_temp=False)
    elif name == "Chain of Nulgath":
        await hunt_item(cmd, name, quantity, "necrocavern", cell="Enter",
                        pad="Spawn", monster_name="Shadow Dragon",
                        is_temp=False)
    elif name == "Yulgath's Hut":
        await hunt_item(cmd, name, quantity, "originul", cell="Enter",
                        pad="Spawn", monster_name="Fiend Champion",
                        is_temp=False)
    elif name in ("Nulgath Nation House", "Corpse Maker of Nulgath",
                  "Overfiend Blade of Nulgath"):
        cmd.bot.log(f"[dirtlickers] {name!r} needs a script this repo does not "
                    f"have (BLOD / The Leery Contract / Juggernaut Items); it "
                    f"was not farmed.")
    else:
        cmd.bot.log(f"[dirtlickers] the bot has not been taught how to get "
                    f"{name!r}.")


async def dirtlickers_merge(cmd: Command,
                            buy_only_this: Optional[str] = None) -> None:
    """``DirtlickersMerge.BuyAllMerge``."""
    await start_buy_all_merge(cmd, MAP, SHOP_ID, find_ingredients,
                              buy_only_this)


async def buy_iron_dreadsaw(cmd: Command) -> None:
    """What ``PrimeFiendShard`` quest 9555 asks for."""
    await dirtlickers_merge(cmd, IRON_DREADSAW)


async def main(cmd: Command) -> None:
    """Standalone entry (``python -m bot.nation.merges.dirtlickers_merge``)."""
    await dirtlickers_merge(cmd)
