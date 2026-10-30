"""Nulgath Diamond Merge -- shop 456 in /evilwarnul.

Port of ``Nation/MergeShops/NulgathDiamondMerge.cs``.  The merge walk is the
engine's generic one; the cases below are the reference's own, mapped onto this
repo's Nation helpers:

* Diamond, Approval, Favor, Dark Crystal, Tainted Gem, Blood Gem, Uni 13, Gem,
  Totem, Voucher (non-mem);
* ``Blade of Holy Might`` -- ``northlands`` Aisha's Drake;
* ``Staff of Imp Fire`` -- ``bludrut2`` Fire Elemental;
* ``Cloak of Nulgath`` (shop 4667) and ``Cool Head`` (shop 4826) in
  ``/tercessuinotlim``, and ``Gold Star of Avarice`` from shop 1951 there;
* ``Primal Dread Fang`` / ``Random Weapon of Nulgath`` -- the Supplies quest;
* ``Crystal Phoenix Blade of Nulgath`` -- its materials plus quest 837.

Reported, not guessed: ``Taro's Manslayer`` (Taro script), ``Iron`` (BLOD +
MineCrafting daily), ``Bone Dust`` (BattleUnderB) and ``Unidentified 27``
(needs ``Core.ResetQuest``, which this engine does not have).
"""
from typing import Optional

from bot.core_advanced import start_buy_all_merge
from bot.core_bots import buy_item, equip_class
from bot.nation.core_nation import (approval_and_favor, dark_makai_item,
                                    farm_blood_gem, farm_dark_crystal_shard,
                                    farm_diamond_of_nulgath, farm_gem_of_nulgath,
                                    farm_tainted_gem, farm_totem_of_nulgath,
                                    farm_uni13_quest, farm_voucher, supplies)
from core.command import Command
from templates.hunt import hunt_item

MAP = "evilwarnul"
SHOP_ID = 456
ABYSSAL_PRIEST = "Abyssal Priest of Nulgath"
STORM_KNIGHT = "Storm Knight"

#: Cases whose script this repo does not have, with the reason.
UNPORTED = {
    "Taro's Manslayer": "the Taro script",
    "Iron": "BLOD + the MineCrafting daily",
    "Bone Dust": "BattleUnderB",
    "Unidentified 27": "Core.ResetQuest",
}


async def find_ingredients(cmd: Command, item_id: int, name: str,
                           quantity: int) -> None:
    if name == "Diamond of Nulgath":
        await farm_diamond_of_nulgath(cmd, quantity)
    elif name == "Nulgath's Approval":
        await approval_and_favor(cmd, quantity, 0)
    elif name == "Archfiend's Favor":
        await approval_and_favor(cmd, 0, quantity)
    elif name == "Dark Crystal Shard":
        await farm_dark_crystal_shard(cmd, quantity)
    elif name == "Tainted Gem":
        await farm_tainted_gem(cmd, quantity)
    elif name == "Blood Gem of the Archfiend":
        await farm_blood_gem(cmd, quantity)
    elif name == "Unidentified 13":
        await farm_uni13_quest(cmd, quantity)
    elif name == "Gem of Nulgath":
        await farm_gem_of_nulgath(cmd, quantity)
    elif name == "Totem of Nulgath":
        await farm_totem_of_nulgath(cmd, quantity)
    elif name == "Voucher of Nulgath (non-mem)":
        await farm_voucher(cmd, False)
    elif name == "Blade of Holy Might":
        await equip_class(cmd, solo=True)
        await hunt_item(cmd, name, quantity, "northlands",
                        monster_name="Aisha's Drake", is_temp=False)
    elif name == "Staff of Imp Fire":
        await equip_class(cmd, solo=False)
        await hunt_item(cmd, name, quantity, "bludrut2",
                        monster_name="Fire Elemental", is_temp=False)
    elif name == "Cloak of Nulgath":
        await buy_item(cmd, 4667, name, quantity, map_name="tercessuinotlim")
    elif name == "Cool Head":
        await buy_item(cmd, 4826, name, quantity, map_name="tercessuinotlim")
    elif name == "Gold Star of Avarice":
        await buy_item(cmd, 1951, name, quantity, map_name="tercessuinotlim")
    elif name in ("Primal Dread Fang", "Random Weapon of Nulgath"):
        await supplies(cmd, name, quantity)
    elif name == "Crystal Phoenix Blade of Nulgath":
        await _crystal_phoenix_blade(cmd, item_id)
    elif name in UNPORTED:
        cmd.bot.log(f"[nulgathdiamond] {name!r} needs {UNPORTED[name]}, which "
                    f"this repo does not have; it was not farmed.")
    else:
        cmd.bot.log(f"[nulgathdiamond] the bot has not been taught how to get "
                    f"{name!r}.")


async def _crystal_phoenix_blade(cmd: Command, item_id: int) -> None:
    """``case "Crystal Phoenix Blade of Nulgath"``."""
    await farm_diamond_of_nulgath(cmd, 13)
    await farm_dark_crystal_shard(cmd, 50)
    await farm_totem_of_nulgath(cmd, 3)
    await farm_gem_of_nulgath(cmd, 20)
    await farm_voucher(cmd, False)
    await farm_tainted_gem(cmd, 50)
    await cmd.ensure_accept_quest(837)
    await hunt_item(cmd, "Undead Bruiser Rune", 1, "underworld",
                    monster_name="Undead Bruiser", is_temp=True)
    await cmd.ensure_turn_in_quest(837, item_id=item_id)


async def nulgath_diamond_merge(cmd: Command,
                                buy_only_this: Optional[str] = None) -> None:
    """``NulgathDiamondMerge.BuyAllMerge``."""
    await start_buy_all_merge(cmd, MAP, SHOP_ID, find_ingredients,
                              buy_only_this)


async def buy_abyssal_priest(cmd: Command) -> None:
    await nulgath_diamond_merge(cmd, ABYSSAL_PRIEST)


async def buy_storm_knight(cmd: Command) -> None:
    await nulgath_diamond_merge(cmd, STORM_KNIGHT)


async def main(cmd: Command) -> None:
    """Standalone entry (``python -m bot.nation.merges.nulgath_diamond_merge``)."""
    await nulgath_diamond_merge(cmd)
