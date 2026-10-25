"""Sea Voice Merge -- shop 2320 in /seavoice.

Port of ``Other/MergeShops/SeaVoiceMerge.cs``, the last of the seven merge shops
the Kathool prerequisite calls.  The merge walk is the engine's generic
:func:`bot.core_advanced.start_buy_all_merge`; this file owns the shop's own part:
five ingredient groups, four of which are farmed through the **Vigil fight** at
/seavoice, and one that is a plain farm.

This shop opens no story of its own: the source assumes /seavoice is unlocked,
and its ingredients are what actually need the regions (Twilight Zone, Midnight
Zone, Abyssal Zone, Trench Observe), all ported.
"""
from typing import Optional, Sequence

from bot.core_advanced import (farm_quest_reward, smart_enhance,
                               start_buy_all_merge)
from bot.core_bots import equip_class
from bot.other.merge_shops.midnight_zone_merge import _kill_once
from bot.story.age_of_ruin.core_aor import kill_thing
from core.command import Command
from templates.hunt import hunt_item

MAP = "seavoice"
SHOP_ID = 2320

#: The solo classes the source tries for the Vigil fight, in its own order.
SOLO_CLASSES = ("Chrono ShadowHunter", "Chrono ShadowSlayer", "Chaos Avenger",
                "Verus DoomKnight", "Hollowborn Vindicator", "Lich",
                "ArchPaladin", "Lord of Order", "StoneCrusher",
                "Dragon of Time", "Unundead Goat")

#: Quest the fight is registered for, and the item its drop list needs.
FIGHT_QUEST = 9349
FIGHT_DROP = "Algal Bloom"

#: The four items that all come from the Vigil fight.
FIGHT_ITEMS = ("Bioluminessence", "Calamity Atlanticus Trident",
               "Glaucus Mystic", "Glaucus Companion")

#: ``Dark Elf Pearl``: quest 9339 in /trenchobserve (solo throughout, and the
#: last step is a kill with no item of its own).
DARK_PEARL_QUEST = 9339
DARK_PEARL_SOLO = ("Noelle's Brooch", "Lady Noelle", 1)
DARK_PEARL_FARM = (("Green Sea Jelly", "Sea Spirit", 2),)
DARK_PEARL_KILL = "Necro Adipocere"

#: ``Water Elf Pearl``: quest 9302 in /midnightzone.  Note the third drop is
#: ``Wraith Memento`` here, where the Midnight Zone shop's own pearl wants the
#: wraith *killed* instead -- this shop's list is the one followed.
WATER_PEARL_QUEST = 9302
WATER_PEARL_HUNTS = (("Fleshy Shadows", "Shadow Viscera", 8),
                     ("Wraith Memento", "Venerated Wraith", 8),
                     ("Memory Card", "Sparagmos", 1))

#: ``Water Elf Antler``: quest 9316 in /abyssalzone.
ANTLER_QUEST = 9316
ANTLER_HUNTS = (("Ashray Artifacts", "The Ashray", 1),
                ("Adipocere Antler", "Necro Adipocere", 3))
ANTLER_KILL = "Foam Scavenger"

#: ``Sundered Tentacle``: quest 9269 in /twilightzone.
TENTACLE_QUEST = 9269
TENTACLE_HUNTS = (("Leviathan Tentacle", "Leviathan", 1),
                  ("Decay Essence", "Decay Spirit", 8),
                  ("Tarnished Icicle", "Ice Guardian", 8))
TENTACLE_MAP = "twilightzone"


async def sea_voice_merge(cmd: Command,
                          buy_only_this: Optional[str] = None,
                          item_blacklist: Sequence[str] = ()) -> None:
    """``SeaVoiceMerge.BuyAllMerge``."""
    await start_buy_all_merge(cmd, MAP, SHOP_ID,
                              find_ingredients=_find_ingredients,
                              buy_only_this=buy_only_this,
                              item_blacklist=item_blacklist)


async def _pick_solo_class(cmd: Command):
    """The first class from the source's list that the account owns."""
    for name in SOLO_CLASSES:
        if cmd.is_in_inventory(name) or cmd.is_in_bank(name):
            return name
    equipped = cmd.get_equipped_class()
    return equipped.item_name if equipped else ""


async def _attack_voice_in_the_sea(cmd: Command, item: str,
                                   quant: int) -> None:
    """``AttackVoiceInTheSea``: the 9349 fight, class chosen per pass."""
    chosen = await _pick_solo_class(cmd)
    if not chosen:
        cmd.stop_bot("No soloing classes found in inventory; stopping "
                     "(go get AP at least and rerun)")
        return

    await equip_class(cmd, solo=True)
    cmd.add_drop(FIGHT_DROP)
    if cmd.is_in_bank(FIGHT_DROP):
        await cmd.bank_to_inv(FIGHT_DROP)

    async def farm_pass() -> None:
        pick = await _pick_solo_class(cmd) or chosen
        cmd.bot.log(f'Soloing "Voice of the Sea" with {pick}')
        # Adv.GearStore/EnhanceItem are skipped (GearStore is not ported), but
        # SmartEnhance is: it is what the source runs on the chosen class.
        cmd.add_drop(FIGHT_DROP)
        await smart_enhance(cmd, pick)
        await cmd.equip_item(pick)
        # These four are regular inventory items, not quest-progress items:
        # "Bioluminessence" arrives as "add items ..." with a CharItemID.  The
        # reference passes ``isTemp: true`` here, and a temp-only wait never
        # ends for an item that is not in the temp bag -- the fight ran past its
        # own target and kept going.
        await kill_thing(cmd, MAP, item, VIGIL_ITEM_ID, quant, is_temp=False)

    await farm_quest_reward(cmd, FIGHT_QUEST, item, quant, farm_pass,
                            is_temp=False)
    cmd.cancel_registered_quests()


#: Item id of the Vigil the fight equips (``KillThing``'s ``itemUsed``).
VIGIL_ITEM_ID = 78994


async def _find_ingredients(cmd: Command, item_id, name: str,
                            quant: int) -> None:
    """``findIngredients``: the shop's five ingredient groups."""
    if name in FIGHT_ITEMS:
        await _attack_voice_in_the_sea(cmd, name, quant)
        return

    if name == "Dark Elf Pearl":
        async def farm_pass() -> None:
            await equip_class(cmd, solo=True)
            await hunt_item(cmd, DARK_PEARL_SOLO[0], DARK_PEARL_SOLO[2],
                            "trenchobserve", monster_name=DARK_PEARL_SOLO[1],
                            is_temp=True)
            for entry, monster, qty in DARK_PEARL_FARM:
                await hunt_item(cmd, entry, qty, "trenchobserve",
                                monster_name=monster, is_temp=True)
            await _kill_once(cmd, "trenchobserve", DARK_PEARL_KILL)

        await farm_quest_reward(cmd, DARK_PEARL_QUEST, name, quant, farm_pass)
        cmd.cancel_registered_quests()
        return

    if name == "Water Elf Pearl":
        async def farm_pass() -> None:
            await equip_class(cmd, solo=True)
            for entry, monster, qty in WATER_PEARL_HUNTS:
                await hunt_item(cmd, entry, qty, "midnightzone",
                                monster_name=monster, is_temp=True)

        await farm_quest_reward(cmd, WATER_PEARL_QUEST, name, quant, farm_pass)
        cmd.cancel_registered_quests()
        return

    if name == "Water Elf Antler":
        async def farm_pass() -> None:
            await equip_class(cmd, solo=True)
            for entry, monster, qty in ANTLER_HUNTS:
                await hunt_item(cmd, entry, qty, "abyssalzone",
                                monster_name=monster, is_temp=True)
            await _kill_once(cmd, "abyssalzone", ANTLER_KILL)

        await farm_quest_reward(cmd, ANTLER_QUEST, name, quant, farm_pass)
        cmd.cancel_registered_quests()
        return

    if name == "Sundered Tentacle":
        await equip_class(cmd)

        async def farm_pass() -> None:
            for entry, monster, qty in TENTACLE_HUNTS:
                await hunt_item(cmd, entry, qty, TENTACLE_MAP,
                                monster_name=monster, is_temp=True)

        await farm_quest_reward(cmd, TENTACLE_QUEST, name, quant, farm_pass)
        cmd.cancel_registered_quests()
        return

    cmd.bot.log(f'[merge] "{name}" is not one of Sea Voice Merge\'s '
                f"ingredients ({', '.join(FIGHT_ITEMS)}, Dark Elf Pearl, "
                f"Water Elf Pearl, Water Elf Antler, Sundered Tentacle); "
                f"skipping it.")


async def main(cmd: Command):
    await sea_voice_merge(cmd)
