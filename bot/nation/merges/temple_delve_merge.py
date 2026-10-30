"""Temple Delve Merge -- shop 2232 in /templedelve.

Port of ``Seasonal/StaffBirthdays/Nulgath/TempleDelveMerge.cs``.  Seasonal like
its storyline, and the shop only exists while the event runs.  Ingredients the
shop does not sell:

* **Doomed Extract** -- quest **9090** registered while hunting ``Elemental
  Study`` x6 (Delirious Elemental), ``Infestation Study`` x6 (Infested Nation)
  and ``Fiend Worm`` (Doomed Fiend); the quest is cancelled afterwards, exactly
  as the reference does;
* **Tainted Gem**, **Dark Crystal Shard**, **Diamond of Nulgath** -- Nation;
* **Nation Ritualist** / **Void Nation Ritualist** -- drops from Doomed Fiend.
"""
from typing import Optional

from bot.core_advanced import start_buy_all_merge
from bot.core_bots import equip_class, register_quests
from bot.nation.core_nation import (farm_dark_crystal_shard,
                                    farm_diamond_of_nulgath, farm_tainted_gem)
from bot.story.nation.temple_delve import (seasonal_active,
                                           temple_delve_storyline)
from core.command import Command
from templates.hunt import hunt_item

MAP = "templedelve"
SHOP_ID = 2232
DOOMED_EXTRACT = "Doomed Extract"
DOOMED_EXTRACT_QUEST = 9090
VOID_NATION_CASTER = "Void Nation Caster"


async def _farm_doomed_extract(cmd: Command, quantity: int) -> None:
    """``case "Doomed Extract"``: quest 9090 while hunting its three drops."""
    await register_quests(cmd, DOOMED_EXTRACT_QUEST)
    try:
        while (cmd.is_still_connected()
               and not await cmd.has_item(DOOMED_EXTRACT, quantity)):
            await equip_class(cmd, solo=False)
            await hunt_item(cmd, "Elemental Study", 6, MAP,
                            monster_name="Delirious Elemental", is_temp=True)
            await hunt_item(cmd, "Infestation Study", 6, MAP,
                            monster_name="Infested Nation", is_temp=True)
            await equip_class(cmd, solo=True)
            await hunt_item(cmd, "Fiend Worm", 1, MAP,
                            monster_name="Doomed Fiend", is_temp=True)
    finally:
        cmd.cancel_registered_quests()


async def find_ingredients(cmd: Command, item_id: int, name: str,
                           quantity: int) -> None:
    if name == DOOMED_EXTRACT:
        await _farm_doomed_extract(cmd, quantity)
    elif name == "Tainted Gem":
        await farm_tainted_gem(cmd, quantity)
    elif name == "Dark Crystal Shard":
        await farm_dark_crystal_shard(cmd, quantity)
    elif name == "Diamond of Nulgath":
        await farm_diamond_of_nulgath(cmd, quantity)
    elif name in ("Nation Ritualist", "Void Nation Ritualist"):
        await equip_class(cmd, solo=True)
        await hunt_item(cmd, name, quantity, MAP, monster_name="Doomed Fiend",
                        is_temp=False)
    else:
        cmd.bot.log(f"[templedelve] the bot has not been taught how to get "
                    f"{name!r}.")


async def temple_delve_merge(cmd: Command,
                             buy_only_this: Optional[str] = None) -> None:
    """``TempleDelveMerge.BuyAllMerge``: seasonal gate, storyline, shop."""
    if not await seasonal_active(cmd, MAP):
        return
    await temple_delve_storyline(cmd)
    await start_buy_all_merge(cmd, MAP, SHOP_ID, find_ingredients,
                              buy_only_this)


async def buy_void_nation_caster(cmd: Command) -> None:
    """What ``PrimeFiendShard`` quest 9555 asks for."""
    await temple_delve_merge(cmd, VOID_NATION_CASTER)


async def main(cmd: Command) -> None:
    """Standalone entry (``python -m bot.nation.merges.temple_delve_merge``)."""
    await temple_delve_merge(cmd)
