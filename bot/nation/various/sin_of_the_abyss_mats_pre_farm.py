"""Sin of the Abyss -- pre-farm its materials, then merge it if asked to.

Port of ``Nation/Various/SinoftheAbyssMatsPreFarm[NoInsignia].cs``.

``MERGE_SWORD`` is the reference's ``MergeSword`` option.  The merge itself needs
25 Nulgath Insignia, and this variant deliberately does not farm them: with the
option off, the script reports what is still needed instead of merging.
"""
from core.command import Command
from bot.core_bots import buy_item
from bot.nation.core_nation import (farm_blood_gem, farm_dark_crystal_shard,
                                    farm_diamond_of_nulgath,
                                    farm_gem_of_nulgath, farm_tainted_gem,
                                    farm_totem_of_nulgath)

#: Shop and item the merge buys from.
SHOP_ID = 2137
ITEM = "Sin of the Abyss"

#: Set True to merge the sword once the materials and the insignias are there.
MERGE_SWORD = False

#: What the merge needs on top of the materials.
INSIGNIA = "Nulgath Insignia"
INSIGNIA_QUANT = 25

#: Materials to pre-farm, in the reference's order.
MATERIALS = (
    ("Tainted Gem", 300),
    ("Dark Crystal Shard", 200),
    ("Diamond of Nulgath", 500),
    ("Totem of Nulgath", 50),
    ("Gem of Nulgath", 150),
    ("Blood Gem of the Archfiend", 50),
)

_FARMS = {
    "Tainted Gem": farm_tainted_gem,
    "Dark Crystal Shard": farm_dark_crystal_shard,
    "Diamond of Nulgath": farm_diamond_of_nulgath,
    "Totem of Nulgath": farm_totem_of_nulgath,
    "Gem of Nulgath": farm_gem_of_nulgath,
    "Blood Gem of the Archfiend": farm_blood_gem,
}


async def main(cmd: Command):
    if await cmd.has_item(ITEM):
        return

    for name, qty in MATERIALS:
        await _FARMS[name](cmd, qty)

    cmd.bot.log("[nation] materials done. The merge needs "
          f"{INSIGNIA} x{INSIGNIA_QUANT} on top of them.")
    if not MERGE_SWORD:
        cmd.bot.log("[nation] MERGE_SWORD is off, so the sword is not bought. Turn it "
              "on to merge once the insignias are held.")
        return

    if await cmd.has_item(INSIGNIA, INSIGNIA_QUANT):
        cmd.bot.log(f"[nation] merging {ITEM} from shop {SHOP_ID}")
        await buy_item(cmd, SHOP_ID, ITEM, map_name="ultranulgath")
    else:
        missing = INSIGNIA_QUANT - cmd.get_quant_item(INSIGNIA)
        cmd.bot.log(f"[nation] missing {missing}/{INSIGNIA_QUANT} {INSIGNIA}; the "
              f"merge needs them and this script does not farm them.")
