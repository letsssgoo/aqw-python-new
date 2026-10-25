"""Twilight Zone Merge -- shop 2293 in /twilightzone.

Port of ``Other/MergeShops/TwilightZoneMerge.cs``.  The merge walk itself is the
engine's generic :func:`bot.core_advanced.start_buy_all_merge`; this file owns
the part that is specific to the shop: which items it does *not* sell, and how
each of those is farmed.

Note:
    The merge walk is the engine's generic one, and the story lead-in is
    ``AoR.TwilightZone()`` -- ported as
    :func:`bot.story.age_of_ruin.core_aor.twilight_zone`, which walks its own
    chain (TerminaTemple -> AshrayVillage -> SunlightZone -> TwilightZone).
    ``Core.SetOptions`` (the reference's option menu) and ``BankingBlackList``
    (this engine never auto-banks) have no counterpart here.
"""
from typing import Optional, Sequence

from bot.core_advanced import farm_quest_reward, start_buy_all_merge
from bot.core_bots import equip_class
from bot.story.age_of_ruin.core_aor import twilight_zone
from core.command import Command
from templates.hunt import hunt_item

MAP = "twilightzone"
SHOP_ID = 2293

#: ``Sundered Tentacle``'s quest, and the three drops one pass of it wants.
TENTACLE_QUEST = 9269
TENTACLE_HUNTS = (("Leviathan Tentacle", "Leviathan", 1),
                  ("Decay Essence", "Decay Spirit", 8),
                  ("Tarnished Icicle", "Ice Guardian", 8))

#: ``Undine Visitor Badge`` drops in the neighbouring zone.
BADGE_MAP = "sunlightzone"
BADGE_MONSTER = "Astravian Illusion"


async def twilight_zone_merge(cmd: Command, buy_only_this: Optional[str] = None,
                              item_blacklist: Sequence[str] = ()) -> None:
    """``TwilightZoneMerge.BuyAllMerge``.

    Args:
        cmd (Command): Facade to act through.
        buy_only_this (str | None): The reference's ``buyOnlyThis``.
        item_blacklist (Sequence[str]): Names to skip.
    """
    # AoR.TwilightZone(): the story that unlocks the map, now ported.
    await twilight_zone(cmd)
    await start_buy_all_merge(cmd, MAP, SHOP_ID,
                              find_ingredients=_find_ingredients,
                              buy_only_this=buy_only_this,
                              item_blacklist=item_blacklist)


async def _find_ingredients(cmd: Command, item_id, name: str,
                            quant: int) -> None:
    """``findIngredients``: the three items this shop does not sell itself."""
    if name == "Undine Visitor Badge":
        await equip_class(cmd)
        await hunt_item(cmd, name, quant, BADGE_MAP,
                        monster_name=BADGE_MONSTER, is_temp=False)
        return

    if name == "Sundered Tentacle":
        await equip_class(cmd)

        async def farm_pass() -> None:
            for item, monster, qty in TENTACLE_HUNTS:
                await hunt_item(cmd, item, qty, MAP, monster_name=monster,
                                is_temp=True)

        await farm_quest_reward(cmd, TENTACLE_QUEST, name, quant, farm_pass)
        cmd.cancel_registered_quests()
        return

    if name == "Leviathan Scale":
        await equip_class(cmd, solo=True)
        cmd.bot.log("[merge] better to use alts to farm it faster.")
        await hunt_item(cmd, name, quant, MAP, monster_name="Leviathan",
                        is_temp=False)
        return

    # The reference's own default case: this shop was never taught how to get
    # that item.  Say so rather than looping for something that cannot come.
    cmd.bot.log(f'[merge] "{name}" is not one of Twilight Zone Merge\'s '
                f'ingredients (Undine Visitor Badge, Sundered Tentacle, '
                f'Leviathan Scale); skipping it.')


async def main(cmd: Command):
    await twilight_zone_merge(cmd)
