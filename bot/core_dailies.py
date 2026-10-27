"""``CoreDailies`` -- the reference's ``CoreDailies.cs``.

Ported (one function each, in the source's order)::

    daily_routine, check_dailyv2, mine_crafting, hard_core_metals,
    fungifora_fun_guy, beast_master_challenge, cyseros_super_hammer,
    mad_weapon_smith, bright_knight_armor, collector_class, cryomancer,
    pyromancer, shadow_scythe_class, grumble_grumble, tenacity_challenge,
    elders_blood, sparrows_blood, pearl_of_nulgath, shadow_shroud,
    dages_scroll_fragment, crypto_token, monthly_treasure_chest_keys,
    wheel_of_doom, power_gem, free_daily_boost, golden_inquisitor,
    design_notes, moglin_pets, ncs_gem, elden_ruby, enchanted_dark_blood

Not ported, and reported by name when asked (``not_ported``), because the
engine has no way to do what they need yet::

    nsod_daily             public-room hunts (``hunt_item`` has no publicRoom)
    break_intothe_hoard    ``HasAchievement`` is not tracked
    friendships            needs the friendship extension-packet listener

``CheckDailyv2``'s max-stack half comes from the quest's own reward payload
(``iStk``): a requested item that is a reward of that quest is compared against
its cap, and one whose cap the payload does not carry is left to the AQW server
rather than guessed.  The reference's ``SkipOnMaxStack`` flag has no counterpart
here -- there is nothing to switch off, the cap is only used when it is known.

Note:
    The reference gates a daily on its own client-side flag
    (``Bot.Quests.IsDailyComplete``).  This engine keeps no such flag, so the
    gate here is the server's answer to the accept -- a daily that is already
    done is refused -- which :meth:`Command.ensure_accept_quest` reports.
    Nothing is farmed in that case, and the call says why.
"""
from datetime import datetime, timedelta
from typing import Optional, Sequence

from bot.core_advanced import buy_item
from bot.core_bots import (chain_complete, dynamic_quant, equip_class,
                           farming_logger, hunt_monster_quest,
                           hunt_monster_quest_single, wait_for_item)
from core.command import Command
from templates.hunt import hunt_item

#: ``CoreDailies.MineCraftingMetalsArray``.
MINE_CRAFTING_METALS = ("Barium", "Copper", "Silver", "Platinum")
#: ``CoreDailies.HardCoreMetalsMetalsArray``.
HARD_CORE_METALS = ("Arsenic", "Chromium", "Rhodium")

#: ``MineCraftingMetalsEnum`` -- the reward id the quest is completed with.
MINE_CRAFTING_METAL_IDS = {
    "Aluminum": 11608, "Barium": 11932, "Gold": 12157, "Iron": 12263,
    "Copper": 12297, "Silver": 12308, "Platinum": 12315,
}
#: ``HardCoreMetalsEnum``.
HARD_CORE_METAL_IDS = {
    "Arsenic": 11287, "Beryllium": 11534, "Chromium": 11591,
    "Palladium": 11864, "Rhodium": 12032, "Thorium": 12075, "Mercury": 12122,
}
#: ``DailyBoostRewards``: the four boost reward ids, plus "lowest owned".
BOOST_EXP, BOOST_GOLD, BOOST_REP, BOOST_CLASS = 27552, 27553, 27554, 27555
BOOST_LOWEST_OWNED = 0
BOOST_REWARD_NAMES = {BOOST_EXP: "EXP", BOOST_GOLD: "Gold",
                      BOOST_REP: "Rep", BOOST_CLASS: "Class"}

#: The dailies this port cannot run yet, with the reason it tells the caller.
NOT_PORTED = {
    "nsod_daily": "public-room hunts (hunt_item has no publicRoom)",
    "break_intothe_hoard": "HasAchievement is not tracked",
    "friendships": "needs the friendship extension-packet listener",
}


def not_ported(cmd: Command, name: str) -> None:
    """Report a daily this port cannot run yet, by name and reason."""
    reason = NOT_PORTED.get(name, "not ported")
    cmd.bot.log(f"[dailies] {name} is not ported: {reason}.")


def _is_member(cmd: Command) -> bool:
    """``Core.IsMember``."""
    return bool(getattr(cmd.bot.player, "is_member", False))


def _rep_rank(cmd: Command, faction: str) -> int:
    """``Bot.Reputation.GetRank(faction)``; 0 when the faction never arrived."""
    try:
        return int(cmd.bot.player.getFactionRank(faction))
    except Exception:
        return 0


def _qty(cmd: Command, item: str) -> int:
    """How many of ``item`` the account holds in the inventory."""
    held = cmd.bot.player.get_item_inventory(item)
    return int(held.qty) if held is not None else 0


async def _reward_map(cmd: Command, quest: int) -> dict:
    """``{name: item_id}`` for a quest's turn-in rewards."""
    quest_data = cmd.get_loaded_quest(quest)
    entries = getattr(quest_data, "reward_entries", None) or []
    return {name: item_id for item_id, name, _max in entries if name}


def _held_inventory_or_bank(cmd: Command, item: str) -> int:
    """How many of ``item`` the account holds, inventory plus bank."""
    return dynamic_quant(cmd, item)


async def check_dailyv2(cmd: Command, quest: int, any_item: bool = True,
                        should_unbank: bool = True,
                        items: Sequence[str] = ()) -> bool:
    """``CoreDailies.CheckDailyv2``: skip a full daily, prepare its drops.

    The reference refuses here when one of ``items`` is at its max stack (or,
    with ``any_item=False``, when all of them are).  This engine's item model
    carries no ``MaxStack``, but a quest's reward payload does (``iStk``), so the
    cap is applied for items that are rewards of ``quest``; an item whose cap is
    not in the payload runs normally and the server decides, as the reference
    does for everything it cannot see.

    Args:
        cmd (Command): Facade to act through.
        quest (int): Quest the daily is for.
        any_item (bool): The reference's ``any`` -- stop on the first full item.
        should_unbank (bool): Bring missing items back from the bank.
        items (Sequence[str]): Item names to check and whitelist as drops.

    Returns:
        bool: False when the daily is already at the cap, True when it should run.
    """
    loaded = cmd.get_loaded_quest(quest)
    if loaded is None:
        cmd.bot.log(f"[dailies] quest {quest} is not loaded, so its max stacks "
                    f"are unknown; running the daily.")
    caps = {}
    for _item_id, name, max_stack in getattr(loaded, "reward_entries", []) or []:
        if name and max_stack:
            caps[name.lower()] = int(max_stack)

    full = 0
    for item in items:
        held = _held_inventory_or_bank(cmd, item)
        cap = caps.get(item.lower())
        if cap and held >= cap:
            if any_item:
                cmd.bot.log(f"You already own the maximum amount of: {item}")
                return False
            full += 1
            continue
        if should_unbank and held <= 0:
            # The reference unbanks when the item is nowhere at all (its
            # ``_item == null`` branch); a banked copy is left alone, and the
            # hunt itself is what brings it over.
            await cmd.bank_to_inv(item)

    if items:
        if not any_item and full == len(items):
            cmd.bot.log("You already own the maximum amount of: "
                        + ", ".join(items))
            return False
        cmd.add_drop(list(items))

    # ``CheckDailyv2``'s two extra drop lists; both are guarded by a quest range.
    if 7156 <= quest < 7166 and not await cmd.has_item_id(50741) \
            and not await cmd.is_completed_before(quest):
        for quest_id in range(7156, 7166):
            if await cmd.is_completed_before(quest_id):
                continue
            cmd.add_drop(cmd.get_quest_rewards(quest_id))
    if 3075 <= quest < 3078:
        for quest_id in range(3075, 3078):
            for reward in cmd.get_quest_rewards(quest_id):
                if cmd.is_in_inventory_or_bank(reward):
                    continue
                cmd.add_drop(reward)

    if loaded is not None:
        needed = [str(row.get("sName") or "")
                  for row in loaded.turn_in_requirements]
        needed = [name for name in needed if name]
        if needed:
            cmd.add_drop(needed)
    return True


async def daily_routine(cmd: Command, quest: int, map_name: str, monster: str,
                        item: str, quant: int = 1, is_temp: bool = True,
                        cell: Optional[str] = None, pad: str = "Left",
                        reward: Optional[str] = None) -> bool:
    """``CoreDailies.DailyRoutine``: accept, kill, turn in.

    Args:
        cmd (Command): Facade to act through.
        quest (int): Daily quest id.
        map_name (str): Map the monster is on.
        monster (str): Monster name, ``"*"`` for any.
        item (str): The drop the quest wants.
        quant (int): How many.
        is_temp (bool): Whether the drop lands in the temporary bag.
        cell (str): Cell to hold; ``None`` hunts the whole map.
        pad (str): Pad inside ``cell``.
        reward (str): Reward to wait for after the turn-in, when known.

    Returns:
        bool: True when the quest was accepted, farmed and turned in.
    """
    if not await cmd.ensure_accept_quest(quest):
        cmd.bot.log(f"[dailies] quest {quest} cannot be accepted right now "
                    "(the daily is done for today); nothing farmed.")
        return False

    cmd.add_drop(item)
    await cmd.join_map(map_name)
    await hunt_item(cmd, item, quant, map_name, cell=cell, pad=pad,
                    monster_name=monster, is_temp=is_temp)
    if not await cmd.ensure_turn_in_quest(quest):
        cmd.bot.log(f"[dailies] quest {quest} could not be turned in.")
        return False
    if reward:
        await wait_for_item(cmd, reward)
    return True


async def mine_crafting(cmd: Command, metals: Optional[Sequence[str]] = None,
                        quant: int = 2, to_bank: bool = False) -> None:
    """``CoreDailies.MineCrafting``: quest 2091, one metal per turn-in."""
    metals = list(metals or MINE_CRAFTING_METALS)
    cmd.bot.log(f"Daily: Mine Crafting ({'/'.join(metals)})")

    if all([await cmd.has_item(metal, quant) for metal in metals]):
        cmd.bot.log(f"All metals were found with the needed quantity ({quant}).")
        if to_bank:
            await cmd.inv_to_bank(metals)
        return

    if not await check_dailyv2(cmd, 2091, any_item=False, items=metals):
        return
    if not await cmd.ensure_accept_quest(2091):
        cmd.bot.log("[dailies] quest 2091 cannot be accepted right now; "
                    "nothing farmed.")
        return

    await equip_class(cmd)
    await hunt_item(cmd, "Axe of the Prospector", 1, "stalagbite",
                    monster_name="Balboa")
    await hunt_item(cmd, "Raw Ore", 30, "stalagbite", monster_name="Balboa",
                    is_temp=True)
    await cmd.jump_cell("r2")

    for metal in metals:
        if await cmd.has_item(metal, quant):
            continue
        cmd.add_drop(metal)
        metal_id = MINE_CRAFTING_METAL_IDS.get(metal)
        if metal_id is None:
            cmd.bot.log(f"[dailies] {metal!r} has no reward id; skipped.")
            continue
        if await cmd.ensure_turn_in_quest(2091, metal_id) is False:
            cmd.bot.log(f"[dailies] quest 2091 would not take the turn-in for "
                        f"{metal}; the remaining metals are skipped (the daily is "
                        f"one turn-in per day).")
            break
        await wait_for_item(cmd, metal)
        if to_bank and cmd.is_in_inventory(metal):
            await cmd.inv_to_bank(metals)

    if cmd.quest_in_progress(2091):
        cmd.bot.log(f"All desired metals were found with the needed quantity "
                    f"({quant}), quest not completed")


async def hard_core_metals(cmd: Command,
                           metals: Optional[Sequence[str]] = None,
                           quant: int = 1, to_bank: bool = False) -> None:
    """``CoreDailies.HardCoreMetals``: quest 2098, members who finished 2090."""
    if not _is_member(cmd) or not await cmd.is_completed_before(2090):
        return

    metals = list(metals or HARD_CORE_METALS)
    cmd.bot.log(f"Daily: Hard Core Metals ({'/'.join(metals)})")

    if all([await cmd.has_item(metal, quant) for metal in metals]):
        cmd.bot.log(f"All \"base\" metals were found with the needed quantity "
                    f"({quant}). Skipped")
        if to_bank:
            await cmd.inv_to_bank(metals)
        return

    if not await check_dailyv2(cmd, 2098, any_item=False, items=metals):
        return
    if not await cmd.ensure_accept_quest(2098):
        cmd.bot.log("[dailies] quest 2098 cannot be accepted right now; "
                    "nothing farmed.")
        return

    await equip_class(cmd)
    await hunt_item(cmd, "Axe of the Prospector", 1, "stalagbite",
                    monster_name="Balboa")
    await hunt_item(cmd, "Raw Ore", 30, "stalagbite", monster_name="Balboa",
                    is_temp=True)
    await cmd.jump_cell("r2")

    for metal in metals:
        if await cmd.has_item(metal, quant):
            continue
        cmd.add_drop(metal)
        metal_id = HARD_CORE_METAL_IDS.get(metal)
        if metal_id is None:
            cmd.bot.log(f"[dailies] {metal!r} has no reward id; skipped.")
            continue
        if await cmd.ensure_turn_in_quest(2098, metal_id) is False:
            cmd.bot.log(f"[dailies] quest 2098 would not take the turn-in for "
                        f"{metal}; the remaining metals are skipped (the daily is "
                        f"one turn-in per day).")
            break
        await wait_for_item(cmd, metal)
        if to_bank and cmd.is_in_inventory(metal):
            await cmd.inv_to_bank(metals)

    if cmd.quest_in_progress(2098):
        cmd.bot.log(f"All desired metals were found with the needed quantity "
                    f"({quant}), quest not completed")


async def fungifora_fun_guy(cmd: Command) -> None:
    """``CoreDailies.FungiforaFunGuy``: quest 4465, Brightoak reputation."""
    if not _is_member(cmd):
        return
    cmd.bot.log("Daily: Fungi for a Fun Guy (BrightOak Reputation)")
    if _rep_rank(cmd, "Brightoak") == 10:
        cmd.bot.log("BrightOak is already rank 10. Skipped")
        return
    if not await check_dailyv2(cmd, 4465):
        return

    await equip_class(cmd)
    if not await daily_routine(cmd, 4465, "brightoak", "Grove Spore",
                               "Colony Spore"):
        return
    await daily_routine(cmd, 4465, "brightoak", "Grove Spore", "Intact Spore")


async def beast_master_challenge(cmd: Command) -> None:
    """``CoreDailies.BeastMasterChallenge``: quest 3759, BeastMaster rank."""
    if not _is_member(cmd):
        return
    cmd.bot.log("Daily: Beast Master Class")
    if _rep_rank(cmd, "BeastMaster") == 10:
        cmd.bot.log("BeastMaster is already rank 10. Skipped")
        return
    if not await check_dailyv2(cmd, 3759):
        return
    await daily_routine(cmd, 3759, "swordhavenbridge", "Purple Slime",
                        "Purple Slime", 10)


async def cyseros_super_hammer(cmd: Command) -> None:
    """``CoreDailies.CyserosSuperHammer``: quests 4310/4311 in /deadmoor."""
    cmd.bot.log("Daily: Cysero's Super Hammer")
    if cmd.is_in_inventory_or_bank("Cysero's SUPER Hammer"):
        cmd.bot.log("Skipped")
        return
    if await cmd.has_item("C-Hammer Token", 90):
        await buy_item(cmd, 500, "Cysero's SUPER Hammer", map_name="deadmoor")
        return
    if not await cmd.has_item("Mad Weaponsmith"):
        cmd.bot.log("You don't own Mad Weaponsmith yet. Skipped")
        return
    if not await check_dailyv2(cmd, 4310, items=("C-Hammer Token",)) \
            and not _is_member(cmd):
        return
    if not await check_dailyv2(cmd, 4311, items=("C-Hammer Token",)) \
            and _is_member(cmd):
        return

    await equip_class(cmd, solo=True)
    await daily_routine(cmd, 4310, "deadmoor", "Geist",
                        "Geist's Chain Link")
    if _is_member(cmd):
        await daily_routine(cmd, 4311, "deadmoor", "Geist",
                            "Geist's Pocket Lint")
    await cmd.inv_to_bank(["C-Hammer Token", "Mad Weaponsmith",
                           "Cysero's SUPER Hammer"])


async def mad_weapon_smith(cmd: Command) -> None:
    """``CoreDailies.MadWeaponSmith``: quests 4308/4309 in /deadmoor."""
    cmd.bot.log("Daily: Mad Weaponsmith")
    if cmd.is_in_inventory_or_bank("Mad Weaponsmith"):
        cmd.bot.log("Skipped")
        return
    if await cmd.has_item("C-Armor Token", 90):
        await cmd.bank_to_inv("C-Armor Token")
        await buy_item(cmd, 500, "Mad Weaponsmith", map_name="deadmoor")
        return
    if not await check_dailyv2(cmd, 4308, items=("C-Armor Token",)) \
            and not _is_member(cmd):
        return
    if not await check_dailyv2(cmd, 4309, items=("C-Armor Token",)) \
            and _is_member(cmd):
        return

    await equip_class(cmd, solo=True)
    await daily_routine(cmd, 4308, "deadmoor", "Nightmare", "Nightmare Fire")
    if _is_member(cmd):
        await daily_routine(cmd, 4309, "deadmoor", "Nightmare",
                            "Unlucky Horseshoe")
    await cmd.inv_to_bank(["C-Armor Token", "Mad Weaponsmith"])


async def bright_knight_armor(cmd: Command, check_armor: bool = True) -> None:
    """``CoreDailies.BrightKnightArmor``: quests 3826/3825, 50 of each seal."""
    cmd.bot.log("Daily: Bright Knight Armor")
    if check_armor and cmd.is_in_inventory_or_bank("Bright Knight"):
        cmd.bot.log("You already own the Bright Knight Armor, Skipped")
        return
    if await cmd.has_item("Seal of Light", 50) \
            and await cmd.has_item("Seal of Darkness", 50):
        await buy_item(cmd, 574, "Bright Knight", map_name="alteonbattle")
        return

    await equip_class(cmd, solo=True)
    if await check_dailyv2(cmd, 3826, items=("Seal of Light",)):
        await daily_routine(cmd, 3826, "alteonbattle", "ULTRA Alteon",
                            "Alteon Defeated")
    if await check_dailyv2(cmd, 3825, items=("Seal of Darkness",)):
        await equip_class(cmd, solo=True)
        await daily_routine(cmd, 3825, "sepulchurebattle", "ULTRA Sepulchure",
                            "Sepulchure Defeated")


async def collector_class(cmd: Command) -> None:
    """``CoreDailies.CollectorClass``: quests 1316/1331/1332 in /terrarium."""
    cmd.bot.log("Daily: The Collector Class")
    if any([await cmd.has_item_id(30229), await cmd.has_item_id(30250),
            await cmd.has_item_id(30253)]):
        cmd.bot.log("You already own The Collector. Skipped")
        return

    await equip_class(cmd)
    if await check_dailyv2(cmd, 1316, items=("Token of Collection",)):
        await daily_routine(cmd, 1316, "terrarium", "Carnivorous Cricket",
                            "This Might Be A Token", 2, False, cell="r2",
                            pad="Right", reward="Token of Collection")
    if _is_member(cmd):
        if await check_dailyv2(cmd, 1331, items=("Token of Collection",)):
            await daily_routine(cmd, 1331, "terrarium", "Killer Cricket",
                                "This Is Definitely A Token", 2, False,
                                cell="r2", pad="Right",
                                reward="Token of Collection")
        if await check_dailyv2(cmd, 1332, items=("Token of Collection",)):
            await daily_routine(cmd, 1332, "terrarium", "Killer Cricket",
                                "This Could Be A Token", 2, False, cell="r2",
                                pad="Right", reward="Token of Collection")
    if await cmd.has_item("Token of Collection", 90):
        await buy_item(cmd, 324, 30250, map_name="Collection",
                       shop_item_id=3015)


async def cryomancer(cmd: Command) -> None:
    """``CoreDailies.Cryomancer``: quests 3965/3966, 84 Glacera Ice Tokens."""
    cmd.bot.log("Daily: Cryomancer Class")
    if cmd.is_in_inventory_or_bank("Cryomancer"):
        cmd.bot.log("You already own Cryomancer, Skipped")
        return

    await equip_class(cmd)
    if _is_member(cmd) and await check_dailyv2(
            cmd, 3965, items=("Glacera Ice Token",)):
        await daily_routine(cmd, 3965, "frozentower", "Frost Invader",
                            "Dark Ice", reward="Glacera Ice Token")
        await cmd.inv_to_bank("Glacera Ice Token")
    if await check_dailyv2(cmd, 3966, items=("Glacera Ice Token",)):
        await equip_class(cmd)
        await daily_routine(cmd, 3966, "frozentower", "Frost Invader",
                            "Dark Ice", reward="Glacera Ice Token")
    if await cmd.has_item("Glacera Ice Token", 84):
        await buy_item(cmd, 1056, 27525, map_name="frozenruins",
                       shop_item_id=2603)
    await cmd.inv_to_bank("Glacera Ice Token")


async def pyromancer(cmd: Command) -> None:
    """``CoreDailies.Pyromancer``: 84 Shurpu Blaze Tokens in /xancave.

    The source notes this is no longer a daily ("i just dont fee like moving
    it"), and it stays where it is.
    """
    cmd.bot.log("Daily: Pyromancer Class")
    if await cmd.has_item_id(12811) or await cmd.has_item_id(12812):
        cmd.bot.log("You already own Pryomancer, Skipped")
        return

    cmd.add_drop("Shurpu Blaze Token")
    await equip_class(cmd)
    await hunt_item(cmd, "Shurpu Blaze Token", 84, "xancave", cell="r9",
                    pad="Down", monster_name="*")
    await buy_item(cmd, 447, 12812, map_name="xancave", shop_item_id=1278)
    held = _qty(cmd, "Shurpu Blaze Token")
    if held:
        await cmd.sell_item("Shurpu Blaze Token", held)


async def shadow_scythe_class(cmd: Command) -> None:
    """``CoreDailies.ShadowScytheClass``: quests 3828/3827, 100 Shadow Shields."""
    cmd.bot.log("Daily: ShadowScythe General Class")
    if cmd.is_in_inventory_or_bank("ShadowScythe General"):
        cmd.bot.log("Skipped")
        return
    if await cmd.has_item("Shadow Shield", 100):
        await buy_item(cmd, 1644, "ShadowScythe General", map_name="shadowfall")
        return

    if not await check_dailyv2(cmd, 3828, items=("Shadow Shield",)) \
            and (_is_member(cmd)
                 and not await check_dailyv2(cmd, 3827,
                                             items=("Shadow Shield",))):
        return
    await daily_routine(cmd, 3828, "lightguardwar", "Citadel Crusader",
                        "Broken Blade")
    if _is_member(cmd):
        await daily_routine(cmd, 3827, "lightguardwar", "Citadel Crusader",
                            "Broken Blade")
        if await cmd.has_item("Shadow Shield", 100):
            await buy_item(cmd, 1644, "ShadowScythe General",
                           map_name="shadowfall")
    await cmd.jump_cell("Cut1", "Left")
    await cmd.inv_to_bank("Shadow Shield")


async def grumble_grumble(cmd: Command) -> None:
    """``CoreDailies.GrumbleGrumble``: quest 592, needs item 4845 owned."""
    if not await cmd.has_item_id(4845):
        return
    cmd.bot.log("Daily: Grumble Grumble (Blood Gem of the Archfiend)")
    if not await check_dailyv2(cmd, 592, any_item=False,
                               items=("Diamond of Nulgath",
                                      "Blood Gem of the Archfiend")):
        return
    await chain_complete(cmd, 592)
    await cmd.inv_to_bank(["Diamond of Nulgath", "Blood Gem of the Archfiend"])


async def tenacity_challenge(cmd: Command, item: Optional[str] = None) -> None:
    """``CoreDailies.TenacityChallenge``: quest 3319, needs the challenge pet."""
    pet = await cmd.has_item("Nulgath Challenge Pet")
    daily = await check_dailyv2(cmd, 3319)
    if not pet or not daily:
        cmd.bot.log("Daily Not Avaiable" if not daily
                    else "You Don't Have \"Nulgath Challenge Pet\". Pet is "
                         "required for doing the quests.")
        return

    cmd.bot.log("Daily: Tenacity Challenge")
    await equip_class(cmd)
    cmd.add_drop(cmd.get_quest_rewards(3319))
    if not await cmd.ensure_accept_quest(3319):
        cmd.bot.log("[dailies] quest 3319 cannot be accepted right now; "
                    "nothing farmed.")
        return
    await hunt_item(cmd, "Dark Runes", 6, "deathpits",
                    monster_name="Ghastly Darkblood")
    await hunt_item(cmd, "Blood Runes", 7, "evilwardage",
                    monster_name="Bloodfiend")

    if item:
        rewards = await _reward_map(cmd, 3319)
        await cmd.ensure_turn_in_quest(3319, rewards.get(item, -1))
    elif not await cmd.has_item("Blood Gem of the Archfiend", 100):
        await cmd.ensure_turn_in_quest(3319, 22332)
    else:
        rewards = await _reward_map(cmd, 3319)
        for reward, reward_id in rewards.items():
            if not await cmd.has_item(reward, 1):
                await cmd.ensure_turn_in_quest(3319, reward_id)
                break
    await cmd.inv_to_bank(["Tained Gem", "Dark Crystal Shard",
                           "Blood Gem of the Archfiend"])


async def elders_blood(cmd: Command) -> None:
    """``CoreDailies.EldersBlood``: the one-a-day Elders' Blood, quest 802."""
    if await cmd.has_item("Elders' Blood", 20):
        return
    if not await check_dailyv2(cmd, 802, items=("Elders' Blood",)):
        return
    cmd.add_drop("Elders' Blood")
    cmd.bot.log("Daily: Elders' Blood")
    await equip_class(cmd)
    await daily_routine(cmd, 802, "arcangrove", "Gorillaphant",
                        "Slain Gorillaphant", 50, cell="LeftBack", pad="Left",
                        reward="Elders' Blood")


async def sparrows_blood(cmd: Command, quant: int = 3) -> None:
    """``CoreDailies.SparrowsBlood``: quest 803 in /arcangrove."""
    item = "Sparrow's Blood"
    if not await check_dailyv2(cmd, 803, any_item=False, items=(item,)):
        return
    if await cmd.has_item(item, 3):
        cmd.bot.log(f"You've maxed out {item} [3]")
        return
    if await cmd.has_item(item, quant):
        # The item name is a variable, not a literal inside the f-string: a
        # backslash in an f-string *expression* is only legal from Python 3.12,
        # and a 3.11 host refused to import this module over exactly that.
        cmd.bot.log(f"You already have enough {item} "
                    f"({_qty(cmd, item)}/{quant}). Skipped")
        return

    cmd.bot.log("Daily: Sparrow's Blood")
    cmd.add_drop(5584)
    cmd.add_drop("Sparrow's Blood")
    await equip_class(cmd)
    if not await cmd.ensure_accept_quest(803):
        cmd.bot.log("[dailies] quest 803 cannot be accepted right now; "
                    "nothing farmed.")
        return
    await hunt_item(cmd, "Blood Lily", 30, "arcangrove", cell="LeftBack",
                    pad="Left", monster_name="*")
    await hunt_item(cmd, "Snapdrake", 17, "arcangrove", cell="RightBack",
                    pad="Left", monster_name="*")
    await hunt_item(cmd, "DOOM Dirt", 12, "arcangrove", cell="Back",
                    pad="Left", monster_name="*")
    await cmd.ensure_turn_in_quest(803)
    await wait_for_item(cmd, "Sparrow's Blood")


async def pearl_of_nulgath(cmd: Command) -> None:
    """``CoreDailies.PearlOfNulgath``: quest 10047, needs 25 Unidentified 10."""
    cmd.bot.log("Daily: Pearl of Nulgath")
    if not await check_dailyv2(cmd, 10047, items=("Pearl of Nulgath",)) \
            or await cmd.has_item("Pearl of Nulgath", 20) \
            or not await cmd.has_item("Malakai's Katana Pet"):
        return

    await cmd.bank_to_inv("Unidentified 10")
    if not await cmd.has_item("Unidentified 10", 25):
        cmd.bot.log(f"You don't have enough Unidentified 10 "
                    f"({_qty(cmd, 'Unidentified 10')}/25). Skipped")
        return
    await chain_complete(cmd, 10047)
    await wait_for_item(cmd, "Pearl of Nulgath")
    await cmd.inv_to_bank("Unidentified 10")


async def shadow_shroud(cmd: Command) -> None:
    """``CoreDailies.ShadowShroud``: quest 486 in /bludrut2."""
    cmd.bot.log("Daily: Shadow Shroud")
    if not await check_dailyv2(cmd, 486, items=("Shadow Shroud",)) \
            or cmd.is_in_inventory("Shadow Shroud", 15):
        return
    await daily_routine(cmd, 486, "bludrut2", "Shadow Creeper",
                        "Shadow Canvas", 5, cell="Enter", pad="Down",
                        reward="Shadow Shroud")
    await cmd.inv_to_bank("Shadow Shroud")


async def dages_scroll_fragment(cmd: Command, to_bank: bool = False) -> None:
    """``CoreDailies.DagesScrollFragment``: quest 3596 in /mountdoomskull."""
    cmd.bot.log("Daily: Dage's Scroll Fragment")
    if not await check_dailyv2(cmd, 3596,
                               items=("Dage's Scroll Fragment",)) \
            or cmd.is_in_inventory("Dage's Scroll Fragment", 13):
        return
    await daily_routine(cmd, 3596, "mountdoomskull", "*",
                        "Chaos Power Increased", 6, cell="b1", pad="Left",
                        reward="Dage's Scroll Fragment")
    if to_bank:
        await cmd.inv_to_bank("Dage's Scroll Fragment")


async def crypto_token(cmd: Command) -> None:
    """``CoreDailies.CryptoToken``: quest 6187 in /boxes."""
    cmd.bot.log("Daily: Crypto Token (/curio)")
    if not await check_dailyv2(cmd, 6187, items=("Crypto Token",)) \
            or cmd.is_in_inventory("Crypto Token", 300):
        return
    await equip_class(cmd)
    await daily_routine(cmd, 6187, "boxes", "Sneevil", "Metal Ore",
                        cell="Closet", pad="Center", reward="Crypto Token")
    await cmd.inv_to_bank("Crypto Token")


async def monthly_treasure_chest_keys(cmd: Command, log: bool = True) -> None:
    """``CoreDailies.MonthlyTreasureChestKeys``: quests 1239/1238."""
    if not _is_member(cmd) or not await cmd.has_item("Treasure Chest"):
        return

    cmd.bot.log("Montly: Treasure Chest Keys")
    # The reference only touches 1239 when the monthly is *not* available:
    # `if (!CheckDailyv2(1239)) if (log) log the next date; else ChainComplete`.
    # Ours cannot see "already claimed", so this branch is kept where the source
    # has it and stays dormant until CheckDailyv2 can answer it.
    if not await check_dailyv2(cmd, 1239):
        if log:
            now = datetime.now()
            next_month = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
            cmd.bot.log(f"Next keys are available on "
                        f"{next_month.strftime('%B %d, %Y')}")
        else:
            await chain_complete(cmd, 1239)

    quest_data = cmd.get_loaded_quest(1238)
    if quest_data is None:
        cmd.bot.log("[dailies] quest 1238 is not loaded; keys not opened.")
        return
    rewards = cmd.get_quest_rewards(1238)
    if rewards and all(cmd.is_in_inventory_or_bank(reward)
                       for reward in rewards):
        return

    before = [item.item_name for item in cmd.bot.player.INVENTORY]
    cmd.add_drop(rewards)
    while (cmd.is_still_connected()
           and await cmd.has_item("Magic Treasure Chest Key")
           and await cmd.has_item("Treasure Chest")):
        if await chain_complete(cmd, 1238) is False:
            cmd.bot.log("[dailies] quest 1238 would not complete; the chest "
                        "loop stops here before it can spin.")
            break
    after = [item.item_name for item in cmd.bot.player.INVENTORY]
    new_items = [name for name in after if name not in before]
    if new_items:
        await cmd.inv_to_bank(new_items)


async def wheel_of_doom(cmd: Command, log: bool = True) -> None:
    """``CoreDailies.WheelofDoom``: quests 3075 (daily) / 3076 (weekly)."""
    gear = _qty(cmd, "Gear of Doom")
    potion = _qty(cmd, "Treasure Potion")
    if log:
        cmd.bot.log(f"Wheel of Doom\nGear of Doom: {gear}/3 | "
                    f"Treasure Potion: {potion}")

    before = [item.item_name for item in cmd.bot.player.INVENTORY]
    if _is_member(cmd) and await check_dailyv2(cmd, 3075):
        await chain_complete(cmd, 3075)
    if await cmd.has_item("Gear of Doom", 3) \
            and await check_dailyv2(cmd, 3076):
        await chain_complete(cmd, 3076)

    after = [item.item_name for item in cmd.bot.player.INVENTORY]
    new_items = [name for name in after if name not in before]
    if not new_items:
        return
    cmd.bot.log("New items: " + " | ".join(new_items))
    await cmd.inv_to_bank(new_items)


async def power_gem(cmd: Command) -> None:
    """``CoreDailies.PowerGem``: the weekly quest 9109.

    The reference first asks the client whether the account's email is verified
    (``world.myAvatar.isEmailVerified``); that flag is client-side only and this
    engine never sees it, so the gate is not reproduced and the server's own
    answer decides.
    """
    cmd.bot.log("Weekly: Power Gems")
    if await cmd.has_item("Power Gem", 1000) \
            or not await check_dailyv2(cmd, 9109):
        cmd.bot.log("You have the maximum amount of Power Gems")
        return
    if not await cmd.ensure_accept_quest(9109):
        cmd.bot.log("[dailies] quest 9109 cannot be accepted right now; "
                    "nothing farmed.")
        return
    await hunt_item(cmd, "News Scroll", 1, "boxes", monster_name="Sneevil")
    await cmd.ensure_turn_in_quest(9109)
    await wait_for_item(cmd, "Power Gem")
    await cmd.inv_to_bank("Power Gem")


async def free_daily_boost(cmd: Command,
                           reward: int = BOOST_LOWEST_OWNED) -> None:
    """``CoreDailies.FreeDailyBoost``: quest 4069, pick the boost to take."""
    if not _is_member(cmd) or not await check_dailyv2(cmd, 4069):
        return

    reward_ids = await _reward_map(cmd, 4069)
    if not reward_ids:
        cmd.bot.log("[dailies] quest 4069 is not loaded; boost not taken.")
        return

    quantities = {}
    names = {}
    for name, item_id in reward_ids.items():
        if item_id == BOOST_EXP and cmd.bot.player.LEVEL >= 100:
            continue
        quantities[item_id] = _qty(cmd, name)
        names[item_id] = name
    if not quantities:
        return

    if reward != BOOST_LOWEST_OWNED and reward in quantities:
        if quantities[reward] == max(quantities.values()):
            cmd.bot.log(f"Selected reward {names.get(reward, reward)} "
                        f"is max stacked with quantity {quantities[reward]}. "
                        f"Switching to the lowest quantity reward.")
            reward = BOOST_LOWEST_OWNED
    if reward == BOOST_LOWEST_OWNED or reward not in quantities:
        reward = min(quantities, key=quantities.get)

    cmd.bot.log("Daily: Free Boost")
    name = names.get(reward, str(reward))
    cmd.bot.log(f"Selected reward: {name} (ID: {reward}) with quantity "
                f"{quantities.get(reward, 0)}")
    cmd.add_drop(list(reward_ids))
    await chain_complete(cmd, 4069, reward)
    await wait_for_item(cmd, name)
    await cmd.inv_to_bank(name)


async def golden_inquisitor(cmd: Command) -> None:
    """``CoreDailies.GoldenInquisitor``: quest 491 in /citadel."""
    cmd.bot.log("Daily: Golden Inquisitor of Shadowfall")
    rewards = cmd.get_quest_rewards(491)
    if rewards and all(cmd.is_in_inventory_or_bank(reward)
                       for reward in rewards):
        return
    if not await check_dailyv2(cmd, 491):
        return

    await equip_class(cmd)
    if not await cmd.ensure_accept_quest(491):
        cmd.bot.log("[dailies] quest 491 cannot be accepted right now; "
                    "nothing farmed.")
        return
    cmd.add_drop(rewards)
    await hunt_item(cmd, "Inquisitor Contract", 7, "citadel",
                    monster_name="Inquisitor Guard")
    await cmd.ensure_turn_in_quest(491)
    if rewards:
        await cmd.inv_to_bank(list(rewards))


async def design_notes(cmd: Command) -> None:
    """``CoreDailies.DesignNotes``: the weekly quest 1213."""
    cmd.bot.log("Weekly: Read the Design Notes!")
    if _rep_rank(cmd, "Loremaster") != 10 and await check_dailyv2(cmd, 1213):
        await chain_complete(cmd, 1213)


async def moglin_pets(cmd: Command) -> None:
    """``CoreDailies.MoglinPets``: quest 4159, 30 Moglin MEAL per pet."""
    cmd.bot.log("Daily: Moglin Pets")
    pets = ("Twig Pet", "Twilly Pet", "Zorbak Pet")
    if all(cmd.is_in_inventory_or_bank(pet) for pet in pets):
        return

    for pet in pets:
        if cmd.is_in_inventory_or_bank(pet):
            continue

        daily_done = not await check_dailyv2(cmd, 4159)

        if not await cmd.has_item("Moglin MEAL", 30) and not daily_done:
            cmd.bot.log("Dedicating daily to " + pet)
            cmd.add_drop("Moglin MEAL")
            if not await cmd.ensure_accept_quest(4159):
                cmd.bot.log("[dailies] quest 4159 cannot be accepted right "
                            "now; nothing farmed.")
                return
            await hunt_item(cmd, "Frogzard Meat", 3, "nexus",
                            monster_name="Frogzard")
            await cmd.ensure_turn_in_quest(4159)
            await wait_for_item(cmd, "Moglin MEAL")
            daily_done = True

        if await cmd.has_item("Moglin MEAL", 30):
            await buy_item(cmd, 1081, pet, map_name="ariapet")
        await cmd.inv_to_bank("Moglin MEAL")

        if daily_done:
            break


async def elden_ruby(cmd: Command, quant: int = 25) -> None:
    """``CoreDailies.EldenRuby``: quest 9896, 25 Elden Ruby."""
    cmd.bot.log("Daily: Elden Ruby")
    if await cmd.has_item("Elden Ruby", quant):
        return
    if not await check_dailyv2(cmd, 9896, items=("Elden Ruby",)):
        return

    if not await cmd.has_item("Compass Rose Skull"):
        cmd.bot.log("Getting the Compass Rose Skull.")
        await hunt_monster_quest(
            cmd, 9894,
            ("dracocon", "Treasure Pile", False),
            ("battleundere", "Treasure Pile", False),
            ("greed", "Treasure Pile", False))
    if not await cmd.has_item("Obsessor Captain"):
        cmd.bot.log("Getting the Obsessor Captain.")
        await hunt_monster_quest(cmd, 9895,
                                 ("shadowrealm", "Shadow Lord", True))

    await cmd.bank_to_inv(["Compass Rose Skull", "Obsessor Captain"])
    cmd.add_drop("Elden Ruby")
    await hunt_monster_quest(cmd, 9896,
                             ("trygve", "Vindicator Recruit", False),
                             ("greed", "Cursed Treasure", True))
    await cmd.inv_to_bank(["Compass Rose Skull", "Obsessor Captain"])


async def enchanted_dark_blood(cmd: Command, quant: int = 10) -> None:
    """``CoreDailies.EnchantedDarkBlood``: quest 2677, 10 Enchanted Dark Blood."""
    cmd.bot.log("Daily: Enchanted Dark Blood")
    if await cmd.has_item("Enchanted Dark Blood", quant):
        return
    if not await check_dailyv2(cmd, 2677, items=("Enchanted Dark Blood",)):
        return
    await equip_class(cmd)
    await hunt_monster_quest_single(cmd, 2677, "falguard",
                                    "Chaonslaught Caster")


async def ncs_gem(cmd: Command, quant: int = 15) -> None:
    """``CoreDailies.NCSGem``: quest 9642 in /shadowrealm."""
    cmd.bot.log("Daily: NCS Gem")
    if await cmd.has_item("NCS Gem", quant):
        return
    if not await check_dailyv2(cmd, 9642, items=("NCS Gem",)):
        return

    cmd.add_drop("NCS Gem")
    if not await cmd.ensure_accept_quest(9642):
        cmd.bot.log("[dailies] quest 9642 cannot be accepted right now; "
                    "nothing farmed.")
        return
    await equip_class(cmd, solo=True)
    await hunt_item(cmd, "Lovely Favor", 1, "shadowrealm",
                    monster_name="Shadow Lord")
    await equip_class(cmd)
    await hunt_item(cmd, "Lovely Request", 100, "shadowrealm",
                    monster_name="Shadow Makai")
    await cmd.ensure_turn_in_quest(9642)
