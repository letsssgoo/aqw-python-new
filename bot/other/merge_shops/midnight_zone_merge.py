"""Midnight Zone Merge -- shop 2302 in /midnightzone.

Port of ``Other/MergeShops/MidnightZoneMerge.cs``.  The merge walk is the
engine's generic :func:`bot.core_advanced.start_buy_all_merge`; this file owns
the shop's own part: the story lead-in and the two items it does not sell.

The lead-in is ``AoR.MidnightZone()``, ported as
:func:`bot.story.age_of_ruin.core_aor.midnight_zone`.
"""
from typing import Optional, Sequence

from bot.core_advanced import start_buy_all_merge
from bot.core_bots import equip_class
from bot.story.age_of_ruin.core_aor import midnight_zone
from core.command import Command
from templates.hunt import attack_script, hunt_item

MAP = "midnightzone"
SHOP_ID = 2302

#: ``Water Elf Pearl``'s quest (9302) and one pass of it.
PEARL_QUEST = 9302
PEARL_SOLO = ("Memory Card", "Sparagmos")
PEARL_FARM = (("Fleshy Shadows", "Shadow Viscera", 8),)
#: The pass also wants the Venerated Wraith killed, with no item of its own.
PEARL_KILL = "Venerated Wraith"

BASE_SCRIP = "Undine Base Scrip"


async def midnight_zone_merge(cmd: Command,
                               buy_only_this: Optional[str] = None,
                               item_blacklist: Sequence[str] = ()) -> None:
    """``MidnightZoneMerge.BuyAllMerge``."""
    await midnight_zone(cmd)
    await start_buy_all_merge(cmd, MAP, SHOP_ID,
                              find_ingredients=_find_ingredients,
                              buy_only_this=buy_only_this,
                              item_blacklist=item_blacklist)


async def _kill_once(cmd: Command, map_name: str, monster: str) -> None:
    """Kill one monster that the quest wants dead but drops nothing.

    The reference's ``HuntMonster(map, monster, log: false)`` has no item, so it
    is a kill for quest progress rather than a drop.  This engine's ``hunt_item``
    needs an item, so the kill is driven directly: walk to the monster and cast
    until it is down.
    """
    await cmd.join_map(map_name)
    await cmd.jump_to_monster(monster)
    while cmd.is_still_connected() and cmd.is_monster_alive(monster):
        await attack_script(cmd, monster)


async def _find_ingredients(cmd: Command, item_id, name: str,
                            quant: int) -> None:
    """``findIngredients``: the two items this shop does not sell itself."""
    if name == BASE_SCRIP:
        await equip_class(cmd)
        await hunt_item(cmd, name, quant, "sunlightzone",
                        monster_name="Infernal Illusion", is_temp=False)
        return

    if name == "Water Elf Pearl":
        await cmd.register_quest(PEARL_QUEST)
        while cmd.is_still_connected() and not await cmd.has_item(name, quant):
            await equip_class(cmd, solo=True)
            await hunt_item(cmd, PEARL_SOLO[0], 1, MAP,
                            monster_name=PEARL_SOLO[1], is_temp=True)
            await equip_class(cmd)
            for item, monster, qty in PEARL_FARM:
                await hunt_item(cmd, item, qty, MAP, monster_name=monster,
                                is_temp=True)
            await _kill_once(cmd, MAP, PEARL_KILL)
        cmd.cancel_registered_quests()
        return

    cmd.bot.log(f'[merge] "{name}" is not one of Midnight Zone Merge\'s '
                f"ingredients ({BASE_SCRIP}, Water Elf Pearl); skipping it.")


async def main(cmd: Command):
    await midnight_zone_merge(cmd)
