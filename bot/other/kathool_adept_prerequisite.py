"""Kathool Adept class prerequisites -- the seven set items, then the Acolyte.

Port of ``Prototypes/KathoolAdept/KathoolAdeptPrerequisite.cs``.  Every piece it
needs is now ported: the seven merge shops it calls (each with its Age of Ruin
story), ``FishingREP`` and ``SomniaREP``.

Two source quirks are kept as they are:

* ``FarmPreReqs(bool BuyItems = false)`` -- the parameter is never used in the
  body;
* the ``Midnight Glaucus Sage`` line runs twice (once, then again when the item
  is still missing).  The second attempt cannot conjure an item the first could
  not, but the source has it, so this does too.
"""
from typing import Optional

from bot.core_bots import equip_class
from bot.core_farms import fishing_rep, somnia_rep
from bot.other.merge_shops.abyssal_zone_merge import abyssal_zone_merge
from bot.other.merge_shops.midnight_zone_merge import midnight_zone_merge
from bot.other.merge_shops.sea_voice_merge import sea_voice_merge
from bot.other.merge_shops.seaview_souvenirs_merge import seaview_souvenirs_merge
from bot.other.merge_shops.trench_observe_merge import trench_observe_merge
from bot.other.merge_shops.twilight_zone_merge import twilight_zone_merge
from bot.other.merge_shops.undine_commissary_merge import undine_commissary_merge
from core.command import Command
from templates.hunt import hunt_item

#: The class the prerequisite unlocks, and the boss that hands it over.
CLASS = "Adeptus Kathooli"
ACOLYTE = ("Kathool Acolyte", "Kathool", "deepchaos")

#: ``(item, the merge shop call that farms it)``, in the source's order.
MERGE_STEPS = (
    ("Ashray Villager", seaview_souvenirs_merge),
    ("Undine Defence Director", undine_commissary_merge),
    ("Evacuation Protocol Suit", twilight_zone_merge),
    ("Elven Heritage Guardian", midnight_zone_merge),
    ("Ashray Elf Warden", abyssal_zone_merge),
    ("DeepWater Drow", trench_observe_merge),
)
#: The seventh, which the source runs on its own (it adds the drop first and
#: retries when the merge did not deliver).
GLAUCUS = "Midnight Glaucus Sage"
GLAUCUS_DROP = "Glaucus Mystic"


async def kathool_adept_prerequisite(cmd: Command,
                                     buy_items: bool = False) -> None:
    """``KathoolAdeptPrerequisites.FarmPreReqs``.

    Args:
        cmd (Command): Facade to act through.
        buy_items (bool): The reference's ``BuyItems`` option; accepted and
            unused, exactly as the source leaves it.
    """
    if await cmd.has_item(CLASS):
        cmd.bot.log(f'Prerequisites already in inventory ({CLASS})')
        return

    if all([await cmd.has_item(item) for item in (
            "Ashray Villager", "Undine Defence Director",
            "Evacuation Protocol Suit", "Elven Heritage Guardian",
            "Ashray Elf Warden", "DeepWater Drow", GLAUCUS, ACOLYTE[0])]):
        cmd.bot.log("Prerequisites already in inventory (Method 1)")
        return

    cmd.bot.log("Farming Prerequisites")

    for item, merge in MERGE_STEPS:
        await merge(cmd, buy_only_this=item)

    cmd.add_drop(GLAUCUS_DROP)
    await sea_voice_merge(cmd, buy_only_this=GLAUCUS)
    if not await cmd.has_item(GLAUCUS):
        await sea_voice_merge(cmd, buy_only_this=GLAUCUS)

    await equip_class(cmd, solo=True)
    await hunt_item(cmd, ACOLYTE[0], 1, ACOLYTE[2],
                    monster_name=ACOLYTE[1], is_temp=False)


async def main(cmd: Command):
    await cmd.equip_enhancement("Valiance")
    await cmd.equip_enhancement("Vainglory")
    await cmd.equip_enhancement("Wizard Helm Enhancement")

    await kathool_adept_prerequisite(cmd)
    await fishing_rep(cmd)
    await somnia_rep(cmd)
