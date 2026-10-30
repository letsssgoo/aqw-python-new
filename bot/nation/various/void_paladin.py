"""Void Paladin -- ``Nation/Various/VoidPaladin.cs`` plus the Void Aura helper.

``DeeperandDeeperintoDarkness()`` repeats nothing: it accepts quest **5827**,
farms its materials (Diamond 25, Tainted Gem 40, Voucher, Gem 25, Dark Crystal
40, Uni 13 x2), buys ``Nulgath Shaped Chocolate`` from citadel shop 44 when it
is missing, adds **2 Void Auras** and turns the quest in.

``VoidAuras(quant)`` is ``CoreNSOD.RetrieveVoidAuras`` (the non-SDKA path): Evil
reputation, then quest **4432** with 20 of each essence -- timespace Astral
Ephemerite plus the nine batch monsters, hunted **by map id** exactly as
``HuntMonsterBatch`` does.  The reference reads a ``MaxStack`` config for the
essence amount; with no config it falls back to 20, which is what this uses.
The member ``GatheringUnstableEssences`` and the SDKA
``CommandingShadowEssences`` branches are not ported.
"""
from typing import Optional

from bot.core_bots import buy_item, equip_class
from bot.core_farms import evil_rep
from bot.nation.core_nation import (farm_dark_crystal_shard,
                                    farm_diamond_of_nulgath, farm_gem_of_nulgath,
                                    farm_tainted_gem, farm_uni13_quest,
                                    farm_voucher)
from core.command import Command
from templates.hunt import hunt_item, hunt_item_by_id

QUEST = 5827
VOID_PALADIN = "Void Paladin"
CHOCOLATE = "Nulgath Shaped Chocolate"
CHOCOLATE_SHOP = 44
CHOCOLATE_MAP = "citadel"
CHOCOLATE_SHOP_ITEM = 22367
CHOCOLATE_ITEM = 38316
VOID_AURAS_NEEDED = 2

AURA_QUEST = 4432
ESSENCE_EACH = 20
TIMESPACE_ESSENCE = "Astral Ephemerite Essence"
#: ``HuntMonsterBatch``: (map, monster map id, essence name).
ESSENCE_BATCH = (
    ("necrocavern", 5, "Chaos Vordred Essence"),
    ("citadel", 21, "Belrot the Fiend Essence"),
    ("greenguardwest", 22, "Black Knight Essence"),
    ("mudluk", 18, "Tiger Leech Essence"),
    ("aqlesson", 17, "Carnax Essence"),
    ("hachiko", 10, "Dai Tengu Essence"),
    ("timevoid", 12, "Unending Avatar Essence"),
    ("dragonchallenge", 4, "Void Dragon Essence"),
    ("maul", 17, "Creature Creation Essence"),
)


async def _quest_item_id(cmd: Command, name: str) -> int:
    loaded = cmd.get_loaded_quest(AURA_QUEST)
    if loaded is None:
        return 0
    for entry in getattr(loaded, "items", []) or []:
        if str(entry.get("sName") or "").strip().lower() == name.lower():
            return int(entry.get("ItemID") or 0)
    return 0


async def void_auras(cmd: Command, quantity: int = 7500) -> None:
    """``CoreNSOD.RetrieveVoidAuras`` (non-SDKA path)."""
    if await cmd.has_item("Void Aura", quantity):
        return
    await evil_rep(cmd, 10)
    cmd.add_drop("Void Aura")
    cmd.add_drop([essence for _map, _id, essence in ESSENCE_BATCH])

    while cmd.is_still_connected() and not await cmd.has_item("Void Aura",
                                                               quantity):
        if not await cmd.ensure_accept_quest(AURA_QUEST):
            cmd.bot.log(f"[voidpaladin] quest {AURA_QUEST} cannot be "
                        f"accepted; no Void Aura can be made.")
            return
        cmd.farming_logger("Void Aura", quantity)

        await equip_class(cmd, solo=False)
        await hunt_item(cmd, TIMESPACE_ESSENCE, ESSENCE_EACH, "timespace",
                        monster_name="Astral Ephemerite", is_temp=False)

        await equip_class(cmd, solo=True)
        for map_name, monster_id, essence in ESSENCE_BATCH:
            item_id = await _quest_item_id(cmd, essence)
            if not item_id:
                cmd.bot.log(f"[voidpaladin] {essence!r} is not on quest "
                            f"{AURA_QUEST}; it was skipped.")
                continue
            await hunt_item_by_id(cmd, item_id, ESSENCE_EACH, map_name,
                                  monster_map_id=monster_id, is_temp=False)

        await cmd.ensure_turn_in_quest(AURA_QUEST)
        await cmd.sleep(1000)


async def deeper_and_deeper_into_darkness(cmd: Command) -> None:
    """``VoidPaladin.DeeperandDeeperintoDarkness``."""
    if await cmd.has_item(VOID_PALADIN):
        return
    cmd.add_drop(VOID_PALADIN)
    cmd.bot.log("[voidpaladin] farming Void Paladin.")

    if not await cmd.ensure_accept_quest(QUEST):
        cmd.bot.log(f"[voidpaladin] quest {QUEST} cannot be accepted.")
        return

    await farm_diamond_of_nulgath(cmd, 25)
    await farm_tainted_gem(cmd, 40)
    await farm_voucher(cmd, False)
    await farm_gem_of_nulgath(cmd, 25)
    await farm_dark_crystal_shard(cmd, 40)
    await farm_uni13_quest(cmd, 2)

    if not await cmd.has_item(CHOCOLATE):
        await buy_item(cmd, CHOCOLATE_SHOP, CHOCOLATE_ITEM, 1,
                       map_name=CHOCOLATE_MAP,
                       shop_item_id=CHOCOLATE_SHOP_ITEM)

    await void_auras(cmd, VOID_AURAS_NEEDED)
    await cmd.ensure_turn_in_quest(QUEST)
    cmd.bot.log("[voidpaladin] Void Paladin farmed.")


async def main(cmd: Command) -> None:
    """Standalone entry (``python -m bot.nation.various.void_paladin``)."""
    await deeper_and_deeper_into_darkness(cmd)
