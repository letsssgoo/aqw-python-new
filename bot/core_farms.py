"""The reference bot's ``CoreFarms``: gold, experience and faction reputation.

Port of ``CoreFarms.cs``.  It sits in ``bot/`` beside the other root cores
because that is where the reference keeps it; the runnable ``Farm/`` scripts
that wrap it are mirrored under ``bot/farm/``.

Both cores are driven the same way: register the quests the reference registers
and let the auto-quest task (``handlers/register_quest.py``) accept and turn them
in between kills, which is what its own auto-quest task does.  What differs is
noted where it happens:

* ``Core.SavedState`` / ``CheckSaveState`` / ``ExecuteSaveState`` live in
  :mod:`bot.core_bots` now, where the reference keeps them; the farms here do not
  call them, because this engine's ``check_alive`` waits for the respawn and its
  ``death_handler`` owns the recovery a save state would otherwise repair.
* Boosts are not available: ``CoreFarms.ToggleBoost`` drives Skua's boost
  items, which this engine has no support for.  The reference keeps every boost
  switched **off** by default, so leaving the calls out changes nothing today --
  the sites that would toggle one carry a comment saying so.
* ``ClassType`` has no "unset" case in the reference.  Here an unconfigured
  class is reported and the farm continues, rather than stopping a long run
  over a settings gap.
"""
import random
import time
from typing import Awaitable, Callable, Optional, Sequence, Tuple

from bot.core_bots import (Alignment, REP_THRESHOLDS, buy_item, can_we_aggro,
                           chain_complete, change_alignment, check_save_state,
                           equip_class, execute_save_state, kill_once,
                           saved_state, wait_for_item)
from core.command import Command
from templates.hunt import DEFAULT_SKILL_LIST, hunt_item, move_to_cell

#: Gold the reference asks for when a caller does not say.
DEFAULT_GOLD = 100_000_000

#: Levels below this are farmed through the story chain, not the arena.
_ICESTORM_FROM = 20

#: The monster ``CoreFarms.CraggleRockREP`` hunts in /wanders, by its own id.
CRAGGLE_ROCK_ID = 560

#: The PvP amulets ``BludrutBrawlBoss`` looks for, in its own order.
PVP_AMULETS: Tuple[str, ...] = (
    "Mithril PvP Amulet +15000",
    "Diamond PvP Amulet +5500",
    "Platinum PvP Amulet +5000",
)

#: The brawl route, as ``(mtcid, cell, x range, y range)``: the four moves before
#: the boss, the three the "kill ads" branch adds (with two kills between them),
#: and one ``(â€¦, monster map id)`` per boss.
PVP_ENTRY = (
    (5, "Morale0C", (784, 862), (254, 274)),
    (4, "Morale0B", (786, 850), (262, 287)),
    (7, "Morale0A", (783, 857), (263, 293)),
    (9, "Crosslower", (777, 857), (254, 290)),
)
PVP_ADS_HEAD = (
    (14, "Crossupper", (399, 545), (255, 256)),
    (18, "Resource1A", (786, 860), (255, 274)),
)
PVP_ADS_MIDDLE = ((20, "Resource1B", (784, 852), (254, 293)),)
PVP_ADS_TAIL = (
    (21, "Resource1A", (123, 189), (262, 297)),
    (19, "Crossupper", (122, 189), (258, 282)),
    (17, "Crosslower", (439, 536), (467, 470)),
)
PVP_BOSS_STEPS = (
    (15, "Morale1A", (781, 858), (258, 290), 13),
    (23, "Morale1B", (782, 850), (259, 276), 14),
    (25, "Morale1C", (802, 865), (264, 286), 15),
    (28, "Captain1", (430, 537), (254, 255), 16),
)

#: What ``BludrutBrawlBoss`` banks when it is after something else.
PVP_OTHER_REWARDS: Tuple[str, ...] = ("Yoshino's Citrine", "The Secret 4")

#: ``TheSecret4``'s own route: the same map, five cell selections (only the last
#: of which walks anywhere) and two restorers to kill by name.
PVP_SECRET_MOVES = (
    (5, "Morale0C", 0, 0),
    (4, "Morale0B", 0, 0),
    (7, "Morale0A", 0, 0),
    (9, "Crosslower", 0, 0),
    (14, "Crossupper", 528, 255),
)
PVP_SECRET_KILLS = ((18, "Resource1A"), (20, "Resource1B"))
PVP_SECRET_TARGET = "(B) Defensive Restorer"
PVP_SECRET_ITEM = "The Secret 4"

#: The Undead Energy unlock chain (quests 2066-2084) and what it buys.
UNDEAD_ENERGY = "Undead Energy"
UNDEAD_ENERGY_UNLOCK = 2084
DOOMWOOD_SHOP_ID = 276
DOOMWOOD_MAP = "doomwood"
UNDEAD_UNLOCK_QUESTS: Tuple[Tuple[int, str], ...] = (
    (2066, "Blinding Light of Destiny Handle"),
    (2067, "Bonegrinder Medal"),
)
UNDEAD_UNLOCK_HUNTS: Tuple[Tuple[int, str, str, int], ...] = (
    (2082, "Undead Essence", "Skeleton Warrior", 25),
    (2083, "Bone Dust", "Skeleton Warrior", 40),
)
CELESTIAL_COMPASS = ("Celestial Compass", "timevoid", "Ephemerite")
SPIRIT_ORB = "Spirit Orb"
BATTLE_UNDER_B = ("battleunderb", "Enter", "Spawn")


async def farm_until(
        cmd: Command,
        done: Callable[[], bool],
        map_name: str,
        cell: Optional[str] = None,
        pad: str = "Left",
        monster: str = "*",
        quests: Sequence[int] = (),
        drops: Sequence[str] = (),
        solo: bool = False,
        hunt: bool = False,
        each: Optional[Callable[[], Awaitable[None]]] = None) -> bool:
    """Fight one map (or cell) until the predicate ``done()`` says stop.

    The port of the reference's ``RegisterQuests`` + ``KillMonster`` /
    ``HuntMonster`` pair.  The item those take is a *drop filter*, not a stop
    condition -- which is why ``drops`` is filtered here and ``done`` is the only
    thing that ends the loop.

    Args:
        cmd (Command): Facade to act through.
        done (Callable[[], bool]): Sync predicate; the loop runs until it is
            True.
        map_name (str): Map to fight in.
        cell (str | None): Cell to hold; when unset, the monster's cell is used.
        pad (str): Pad identifier within that cell.
        monster (str): Target monster, ``*`` for everything.
        quests (Sequence[int]): Quests to register for the auto-quest task.
        drops (Sequence[str]): Items to whitelist as drops.
        solo (bool): Equip the solo class instead of the farm one.
        hunt (bool): Walk to the target rather than stand and fight.
        each (Callable | None): Awaited once per pass, for the routines that sell
            or buy between kills.

    Returns:
        bool: True when ``done()`` held; False when the client dropped, the map
        could not be reached, or the class could not be equipped -- each
        reported.
    """
    if done():
        return True
    if not cmd.is_still_connected():
        cmd.bot.log("[farm] the client is not connected; nothing farmed.")
        return False

    await equip_class(cmd, solo=solo)

    if cmd.is_not_in_map(map_name):
        cmd.bot.log(f"[farm] {map_name}: travelling")
    while cmd.is_still_connected() and cmd.is_not_in_map(map_name):
        await cmd.join_map(map_name)
        await cmd.sleep(500)
    if not cmd.is_still_connected():
        cmd.bot.log(f"[farm] disconnected while joining {map_name}.")
        return False

    if cell:
        if not await move_to_cell(cmd, cell, pad, monster):
            return False
    else:
        await cmd.jump_to_monster(monster)
    if not cmd.is_still_connected():
        cmd.bot.log(f"[farm] disconnected while moving to {cell or monster}.")
        return False

    if quests:
        # The reference registers its quests and hopes; a quest whose story or
        # level requirement is missing then farms forever for a turn-in that can
        # never come.  Ask the server once, and report instead of spinning.
        if not await cmd.ensure_accept_quest(quests[0], max_attempts=3):
            cmd.bot.log(f"[farm] quest {quests[0]} cannot be accepted, so its story or "
                  f"requirements are missing. Nothing farmed in {map_name}.")
            return False
        for quest_id in quests:
            await cmd.register_quest(quest_id)
    if drops:
        cmd.add_drop(list(drops))

    # ``Core.SavedState(true, map)``: the hop to /whitemap is how the reference
    # saves a long farm's progress, so it is armed for the loop and disarmed
    # after it, exactly as there.
    saved_state(cmd, True, map_name)

    while cmd.is_still_connected() and not done():
        if check_save_state(cmd):
            await execute_save_state(cmd)
        can_we_aggro(cmd)
        await cmd.use_next_skill(DEFAULT_SKILL_LIST, monster, hunt)
        if each is not None:
            await each()

    saved_state(cmd, False)

    if quests:
        cmd.cancel_registered_quests()

    if not cmd.is_still_connected():
        cmd.bot.log(f"[farm] disconnected before {map_name} was done.")
        return False
    return True


async def the_secret4(cmd: Command) -> None:
    """``CoreFarms.TheSecret4``: the Secret 4 off the brawl's restorers.

    The same PvP map as :func:`bludrut_brawl_boss`, walked differently: five cell
    selections, only the last of which moves anywhere, then two restorers killed
    by name for the drop.
    """
    if await cmd.has_item(PVP_SECRET_ITEM):
        return

    cmd.bot.log(f"[farm] {PVP_SECRET_ITEM}: running the brawl route")
    await equip_class(cmd, solo=True)

    while cmd.is_still_connected() and not await cmd.has_item(PVP_SECRET_ITEM):
        while cmd.is_still_connected() and cmd.is_not_in_map("bludrutbrawl"):
            await cmd.sleep(5000)
            await cmd.join_map("bludrutbrawl", 999999)
            await cmd.jump_cell("Enter0", "Spawn")

        for mtcid, cell, x, y in PVP_SECRET_MOVES:
            if not await _pvp_move(cmd, mtcid, cell, x, y):
                return
        for mtcid, cell in PVP_SECRET_KILLS:
            if not await _pvp_move(cmd, mtcid, cell, 0, 0):
                return
            await _pvp_killing(cmd, PVP_SECRET_TARGET)

        while cmd.is_still_connected() and cmd.is_not_in_map("battleon"):
            await cmd.sleep(5000)
            await cmd.join_map("battleon", 999999)


async def battle_under_b(cmd: Command, item: str = "Bone Dust",
                         quant: int = 10000, is_temp: bool = False) -> None:
    """``CoreFarms.BattleUnderB``: kill everything in /battleunderb for ``item``.

    For ``Undead Energy`` the reference first runs quests 2066-2084, without
    which the energy does not drop from there at all.
    """
    if await cmd.has_item(item, quant, isTemp=is_temp):
        cmd.farming_logger(item, quant)
        return

    if item == UNDEAD_ENERGY and not await cmd.is_completed_before(
            UNDEAD_ENERGY_UNLOCK):
        cmd.bot.log("[farm] unlocking the /battleunderb Undead Energy drops (quests "
              "2066-2084)")
        await _undead_energy_unlock(cmd)

    cmd.add_drop(item)
    cmd.farming_logger(item, quant)
    await equip_class(cmd)
    await hunt_item(cmd, item, quant, BATTLE_UNDER_B[0], cell=BATTLE_UNDER_B[1],
                    pad=BATTLE_UNDER_B[2], monster_name="*", is_temp=is_temp)


async def _undead_energy_unlock(cmd: Command) -> None:
    """The four prerequisite quests for /battleunderb's Undead Energy."""
    for quest_id, purchase in UNDEAD_UNLOCK_QUESTS:
        if await cmd.is_completed_before(quest_id):
            continue
        await cmd.ensure_accept_quest(quest_id)
        await buy_item(cmd, DOOMWOOD_SHOP_ID, purchase, map_name=DOOMWOOD_MAP)
        await cmd.ensure_turn_in_quest(quest_id)

    for quest_id, drop, monster, qty in UNDEAD_UNLOCK_HUNTS:
        if await cmd.is_completed_before(quest_id):
            continue
        await cmd.ensure_accept_quest(quest_id)
        await hunt_item(cmd, drop, qty, BATTLE_UNDER_B[0], monster_name=monster,
                        is_temp=False)
        await cmd.ensure_turn_in_quest(quest_id)

    if await cmd.is_completed_before(UNDEAD_ENERGY_UNLOCK):
        return
    await cmd.ensure_accept_quest(UNDEAD_ENERGY_UNLOCK)
    await bone_some_dust(cmd, 100)
    await hunt_item(cmd, CELESTIAL_COMPASS[0], 1, CELESTIAL_COMPASS[1],
                    monster_name=CELESTIAL_COMPASS[2], is_temp=False)
    await cmd.ensure_turn_in_quest(UNDEAD_ENERGY_UNLOCK)


async def bone_some_dust(cmd: Command, quant: int = 65000) -> None:
    """``CoreFarms.BoneSomeDust``: quests 2082+2083 until Spirit Orbs are full."""
    if await cmd.has_item(SPIRIT_ORB, quant):
        return

    cmd.add_drop(["Bone Dust", "Undead Essence", UNDEAD_ENERGY, SPIRIT_ORB])
    cmd.farming_logger(SPIRIT_ORB, quant)
    await farm_until(
        cmd, lambda: cmd.get_quant_item(SPIRIT_ORB) >= quant, BATTLE_UNDER_B[0],
        cell=BATTLE_UNDER_B[1], pad=BATTLE_UNDER_B[2], monster="*",
        quests=(2082, 2083),
        drops=("Bone Dust", "Undead Essence", UNDEAD_ENERGY, SPIRIT_ORB))


async def _sell_all(cmd: Command, item_name: str) -> None:
    """Sell every copy held (the reference's ``Core.SellItem(name, all: true)``)."""
    have = cmd.get_quant_item(item_name)
    if have:
        await cmd.sell_item(item_name, have)


# ----------------------------------------------------------------------------
# PvP: the Bludrut Brawl boss
# ----------------------------------------------------------------------------

async def _pvp_move(cmd: Command, mtcid: int, cell: str, x=0, y=0) -> bool:
    """``CoreBots.PvPMove``: walk to a coordinate, then select the cell's id.

    The reference sends the move packet and then a ``mtcid`` packet, waits, and
    repeats the pair until the cell it asked for is the cell it is in.  Its call
    sites pass either a fixed coordinate or a random one drawn from a range -- and
    draw it **once**, retrying with the same numbers, which is how this does it
    too.  ``0, 0`` means "do not walk", as it does there.

    Returns:
        bool: True once the cell is reached, False when the client dropped first
        -- which the reference cannot notice, having no ``ShouldExit`` here.
    """
    if isinstance(x, tuple):
        x = random.randint(*x)
    if isinstance(y, tuple):
        y = random.randint(*y)

    while cmd.is_still_connected():
        if x or y:
            await cmd.walk_to(x, y)
        cmd.bot.write_message(f"%xt%zm%mtcid%{cmd.bot.areaId}%{mtcid}%")
        await cmd.sleep(2500)
        if cmd.is_in_cell(cell):
            return True
        await cmd.sleep(1500)
    cmd.bot.log(f"[farm] disconnected while moving to {cell}.")
    return False


async def _pvp_killing(cmd: Command, target: str = "*") -> None:
    """``CoreBots.PVPKilling``: keep attacking until the target is down."""
    while cmd.is_still_connected() and cmd.is_monster_alive(target):
        await cmd.use_next_skill(DEFAULT_SKILL_LIST, target)


async def bludrut_brawl_boss(cmd: Command, item: str = "Combat Trophy",
                             quant: int = 5000,
                             kill_ads: bool = False) -> bool:
    """``CoreFarms.BludrutBrawlBoss``: the Team B Captain in /bludrutbrawl.

    A PvP map, so this walks a fixed route of cells and coordinate ranges and
    kills the enemy team by their map ids, then waits for the server to credit
    the trophy before starting the next pass.

    Args:
        cmd (Command): Facade to act through.
        item (str): What to farm -- ``Combat Trophy`` or another brawl reward.
        quant (int): How many of it.
        kill_ads (bool): The reference's ``KillAds`` option: also clear the
            healers for three extra trophies, which takes longer.

    Returns:
        bool: True when the item is held, False when it stopped early (reported).
    """
    if await cmd.has_item(item, quant):
        return True

    if cmd.is_in_map("bludrutbrawl"):
        cmd.bot.log("[farm] starting in the PvP map; joining /whitemap first so "
              "things can be equipped")
        await cmd.join_map("whitemap")

    cmd.add_drop(item)
    await equip_class(cmd, solo=True)
    cmd.farming_logger(item, quant)

    for amulet in PVP_AMULETS:
        if await cmd.has_item(amulet):
            # equip_item withdraws it from the bank itself when it has to
            await cmd.equip_item(amulet)
            break

    while cmd.is_still_connected() and not await cmd.has_item(item, quant):
        before = cmd.get_quant_item(item)
        await cmd.join_map("bludrutbrawl", 999999)
        await cmd.jump_cell("Enter0", "Spawn")

        for mtcid, cell, x_range, y_range in PVP_ENTRY:
            if not await _pvp_move(cmd, mtcid, cell, x_range, y_range):
                return False

        if kill_ads:
            for mtcid, cell, x_range, y_range in PVP_ADS_HEAD:
                if not await _pvp_move(cmd, mtcid, cell, x_range, y_range):
                    return False
            await _pvp_killing(cmd)
            for mtcid, cell, x_range, y_range in PVP_ADS_MIDDLE:
                if not await _pvp_move(cmd, mtcid, cell, x_range, y_range):
                    return False
            await _pvp_killing(cmd)
            for mtcid, cell, x_range, y_range in PVP_ADS_TAIL:
                if not await _pvp_move(cmd, mtcid, cell, x_range, y_range):
                    return False

        for mtcid, cell, x_range, y_range, mon_id in PVP_BOSS_STEPS:
            if not await _pvp_move(cmd, mtcid, cell, x_range, y_range):
                return False
            await _pvp_killing(cmd, f"id.{mon_id}")
            if not cmd.is_player_alive():
                cmd.bot.log("[farm] died in the brawl; leaving and retrying")
                await cmd.join_map("battleon", 999999)
                await cmd.sleep(1500)
                break

        for _ in range(40):        # the reference waits for the server itself
            if cmd.get_quant_item(item) > before:
                break
            await cmd.sleep(500)
        else:
            cmd.bot.log(f"[farm] {item} did not move from {before} after a full brawl "
                  f"pass; stopping rather than brawling forever.")
            return False

        await cmd.leave_combat()
        while cmd.is_still_connected() and cmd.is_not_in_map("battleon"):
            await cmd.join_map("battleon", 999999)
            await cmd.sleep(1500)

    for reward in PVP_OTHER_REWARDS:
        if reward != item and await cmd.has_item(reward):
            await cmd.inv_to_bank(reward)

    gained = await cmd.has_item(item, quant)
    if not gained:
        cmd.bot.log(f"[farm] the brawl stopped without reaching {quant} {item}.")
    return gained



# ----------------------------------------------------------------------------
# Gold
# ----------------------------------------------------------------------------

async def farm_gold(cmd: Command, quant: int = DEFAULT_GOLD) -> bool:
    """``CoreFarms.Gold``: members to HonorHall, everyone to BattleGroundE.

    The reference runs the three methods in this order and lets each one's own
    guard decide whether it applies; so does this.  ``DarkWarLegion`` is *not*
    part of the chain there either -- it has its own script.
    """
    if cmd.get_player().GOLD >= quant:
        return True

    # the reference toggles its gold boost here; this engine has no boosts
    await honor_hall(cmd, quant)
    await battle_ground_e(cmd, quant)
    await berserker_bunny(cmd, quant)

    gold = cmd.get_player().GOLD
    if gold < quant:
        cmd.bot.log(f"[farm] gold farm stopped at {gold} of {quant}: no method could "
              f"take it further (HonorHall needs membership and level 61, "
              f"BattleGroundE level 61, BerserkerBunny the /greenguardwest farm).")
        return False
    return True


async def honor_hall(cmd: Command, gold_quant: int = DEFAULT_GOLD) -> None:
    """``CoreFarms.HonorHall``: quests 3992+3993 on Ice Demons, members, 61+."""
    player = cmd.get_player()
    if not player.is_member or player.LEVEL < 61 or player.GOLD >= gold_quant:
        return
    cmd.bot.log(f"[farm] honorhall: farming to {gold_quant} gold on Ice Demons")
    await farm_until(cmd, lambda: cmd.get_player().GOLD >= gold_quant,
                     "honorhall", cell="r1", pad="Center", monster="Ice Demon",
                     quests=(3992, 3993))


async def battle_ground_e(cmd: Command, gold_quant: int = DEFAULT_GOLD) -> None:
    """``CoreFarms.BattleGroundE``: quests 3991+3992 in /battlegrounde, 61+."""
    player = cmd.get_player()
    if player.LEVEL < 61 or player.GOLD >= gold_quant:
        return
    cmd.bot.log(f"[farm] battlegrounde: farming to {gold_quant} gold")
    await farm_until(cmd, lambda: cmd.get_player().GOLD >= gold_quant,
                     "battlegrounde", cell="r2", pad="center", monster="*",
                     quests=(3991, 3992))


async def berserker_bunny(cmd: Command, gold_quant: int = DEFAULT_GOLD,
                          sell: bool = True) -> None:
    """``CoreFarms.BerserkerBunny``: quest 236 in /greenguardwest, selling drops."""
    if cmd.get_player().GOLD >= gold_quant:
        return
    cmd.bot.log(f"[farm] greenguardwest: farming to {gold_quant} gold on Berserker "
          f"Bunny drops{' (selling them)' if sell else ''}")

    async def sell_pass() -> None:
        await _sell_all(cmd, "Berserker Bunny")

    await farm_until(cmd, lambda: cmd.get_player().GOLD >= gold_quant,
                     "greenguardwest", cell="West12", pad="Up", monster="*",
                     quests=(236,), drops=["Berserker Bunny"], solo=True,
                     each=sell_pass if sell else None)


async def dark_war_legion(cmd: Command, gold_quant: int = DEFAULT_GOLD) -> None:
    """``CoreFarms.DarkWarLegion``: quests 8584+8585 on Nation Badge drops."""
    if cmd.get_player().GOLD >= gold_quant:
        return
    # the reference toggles its gold boost here; this engine has no boosts
    cmd.bot.log(f"[farm] darkwarlegion: farming to {gold_quant} gold")
    await farm_until(cmd, lambda: cmd.get_player().GOLD >= gold_quant,
                     "darkwarlegion", cell="r2", pad="Left", monster="*",
                     quests=(8584, 8585), drops=["Nation Badge"])


# ----------------------------------------------------------------------------
# Experience
# ----------------------------------------------------------------------------

async def farm_experience(cmd: Command, level: int = 100,
                          rank_up_class: bool = False) -> None:
    """``CoreFarms.Experience``: the story chain up to 20, then the arena."""
    player = cmd.get_player()
    if player.LEVEL >= level and not rank_up_class:
        return

    if rank_up_class:
        cmd.bot.log("[farm] rank-up-class farming needs the class rank, which this "
              f"engine cannot read; farming to level {level} instead.")

    await equip_class(cmd)
    # the reference toggles its experience boost here; this engine has no boosts

    if cmd.get_player().LEVEL < 10:
        cmd.bot.log('[farm] oaklore: "Bone Berserker" up to level 10')
        await farm_until(cmd, lambda: cmd.get_player().LEVEL >= min(10, level),
                         "oaklore", cell="r3", pad="Left",
                         monster="Bone Berserker", quests=(4007, 6257))

    if cmd.get_player().LEVEL >= level and not rank_up_class:
        return

    if cmd.get_player().LEVEL < 20:
        await undead_giant_unlock(cmd)
        cmd.bot.log('[farm] swordhavenundead: "Undead Giant" up to level 20')
        await farm_until(cmd, lambda: cmd.get_player().LEVEL >= min(20, level),
                         "swordhavenundead", cell="Gates", pad="Left",
                         monster="Undead Giant", quests=(178,))

    if cmd.get_player().LEVEL >= level and not rank_up_class:
        return

    await icestorm_arena(cmd, level, rank_up_class)


async def undead_giant_unlock(cmd: Command) -> None:
    """``CoreFarms.UndeadGiantUnlock``: quests 183 / 176 / 177 unlock 178."""
    if await cmd.is_completed_before(177):
        return
    cmd.bot.log("[farm] unlocking the Undead Giant farm quest (183, 176, 177)")

    await cmd.ensure_accept_quest(183)
    await hunt_item(cmd, "Defeated Fire Mage", 4, "portalundead", cell="Enter",
                    pad="Left", monster_name="Skeletal Fire Mage",
                    is_temp=False)
    await cmd.ensure_turn_in_quest(183)

    await cmd.ensure_accept_quest(176)
    await hunt_item(cmd, "Slain Skeletal Soldier", 5, "swordhavenundead",
                    monster_name="Skeletal Soldier", is_temp=False)
    await cmd.ensure_turn_in_quest(176)

    await cmd.ensure_accept_quest(177)
    await hunt_item(cmd, "Frozen Bonehead", 6, "swordhavenundead",
                    monster_name="Skeletal Ice Mage", is_temp=False)
    await cmd.ensure_turn_in_quest(177)


#: ``CoreFarms.IcestormArena``'s ladder: ``(from level, to level, map, cell, pad,
#: quests)``.  The reference repeats the same block once per band; the band is
#: data here.  Each cell is the one its own block jumps to, the 35-50 band's
#: ``r11`` included -- that block's death-recovery branch says ``r14``, but the
#: block itself jumps to ``r11``, and the source is what is followed.
ICESTORM_LADDER = (
    (0, 5, "icestormarena", "r4", "Bottom", ()),
    (5, 10, "icestormarena", "r5", "Left", ()),
    (10, 20, "icestormarena", "r6", "Left", ()),
    (20, 25, "icestormarena", "r7", "Left", (6628,)),
    (25, 30, "icestormarena", "r10", "Left", ()),
    (30, 35, "icestormarena", "r11", "Left", (6629,)),
    (35, 50, "icestormarena", "r11", "Left", (6629,)),
    (50, 61, "icestormarena", "r16", "Left", ()),
)


async def icestorm_arena(cmd: Command, level: int = 100,
                         rank_up_class: bool = False,
                         keep_class: bool = False) -> None:
    """``CoreFarms.IcestormArena``: one cell per level band, up to level 100.

    Levels 61-75 follow BattleGroundE instead of the arena -- except for a
    rank-up run, which stays in the arena -- and 75+ moves to /icestormunder.

    Args:
        cmd (Command): Facade to act through.
        level (int): Level to stop at.
        rank_up_class (bool): Keep farming after the level cap, for class rank.
        keep_class (bool): Do not equip the configured class first; a rank-up
            run has to keep the class it is ranking on.
    """
    if cmd.get_player().LEVEL >= level and not rank_up_class:
        return

    if not keep_class:
        await equip_class(cmd)
    # the reference toggles its experience boost here; this engine has no boosts

    for start, end, map_name, cell, pad, quests in ICESTORM_LADDER:
        current = cmd.get_player().LEVEL
        if current < start:
            continue
        if current >= level and not rank_up_class:
            break
        cmd.bot.log(f"[farm] {map_name} {cell}: levels {start}-{end}")
        await farm_until(
            cmd,
            lambda end=end: cmd.get_player().LEVEL >= min(end, level),
            map_name, cell=cell, pad=pad, monster="*", quests=quests)
        if cmd.get_player().LEVEL >= level and not rank_up_class:
            return

    current = cmd.get_player().LEVEL
    if 61 <= current < 75 and (current < level or rank_up_class):
        if rank_up_class:
            cmd.bot.log("[farm] icestormarena r17: levels 61-75 (ranking the class)")
            await farm_until(cmd, lambda: cmd.get_player().LEVEL >= min(75, level),
                             "icestormarena", cell="r17", pad="Left",
                             monster="*")
        else:
            cmd.bot.log("[farm] battlegrounde: levels 61-75")
            await farm_until(cmd, lambda: cmd.get_player().LEVEL >= min(75, level),
                             "battlegrounde", cell="r2", pad="center",
                             monster="*", quests=(3991, 3992))
        if cmd.get_player().LEVEL >= level and not rank_up_class:
            return

    if cmd.get_player().LEVEL < level or rank_up_class:
        cmd.bot.log("[farm] icestormunder r2: levels 75-100")
        await farm_until(cmd, lambda: cmd.get_player().LEVEL >= level,
                         "icestormunder", cell="r2", pad="Top", monster="*")

    await cmd.leave_combat()
    cmd.stop_aggro()
    await cmd.rest()


# ----------------------------------------------------------------------------
# Reputation
# ----------------------------------------------------------------------------

def _rep_done(cmd: Command, faction: str, rank: int) -> Callable[[], bool]:
    """A predicate that reads the faction rank each time it is asked."""
    return lambda: cmd.get_faction_rank(faction) >= rank


async def good_rep(cmd: Command, rank: int = 10) -> None:
    """``CoreFarms.GoodREP``: quest 1952 in /PoisonForest, or the fallback route.

    The reference picks the fallback whenever the /PoisonForest story (quest
    1955) is unfinished: quest 369 in /swordhavenbridge to rank 4, then quest
    371 in /sewer for members or 372 in /castleundead for everyone else.
    """
    if cmd.get_faction_rank("Good") >= rank:
        return

    await change_alignment(cmd, Alignment.GOOD)
    await equip_class(cmd)
    cmd.bot.log(f"[farm] farming Good reputation to rank {rank}")

    if await cmd.is_completed_before(1955):
        await farm_until(cmd, _rep_done(cmd, "Good", rank), "poisonforest",
                         monster="Burning Loyalist", quests=(1952,))
        return

    cmd.bot.log("[farm] the /PoisonForest story (quest 1955) is not complete: farming "
          "the lower-reward route -- quest 369 in /swordhavenbridge first.")
    await farm_until(cmd, _rep_done(cmd, "Good", 4), "swordhavenbridge",
                     cell="Bridge", pad="Left", monster="*", quests=(369,))

    if cmd.get_player().is_member:
        await farm_until(cmd, _rep_done(cmd, "Good", rank), "sewer",
                         cell="End", pad="Left", monster="Grumble",
                         quests=(371,))
    else:
        await farm_until(cmd, _rep_done(cmd, "Good", rank), "castleundead",
                         cell="Enter", pad="Spawn", monster="*", quests=(372,))


async def vampire_rep(cmd: Command, rank: int = 10) -> None:
    """``CoreFarms.VampireREP``: quest 522 (Twisted Paw) in /safiria.

    The reference checks a table of unlocked quests before farming; here the
    server answers for itself -- :meth:`Command.ensure_accept_quest` reports a
    refusal, which is what an unfinished /safiria story produces.
    """
    if cmd.get_faction_rank("Vampire") >= rank:
        return

    if not await cmd.ensure_accept_quest(522):
        cmd.bot.log("[farm] quest 522 (Twisted Paw) cannot be accepted, so the "
              "/safiria story is not done. Nothing farmed.")
        return

    await equip_class(cmd, solo=True)
    cmd.bot.log(f"[farm] farming Vampire reputation to rank {rank}")
    cmd.remove_drop("Old Moon")
    await farm_until(cmd, _rep_done(cmd, "Vampire", rank), "safiria",
                     monster="Twisted Paw", quests=(522,),
                     drops=["Twisted Paw's Head"])


async def yokai_rep(cmd: Command, rank: int = 10) -> None:
    """``CoreFarms.YokaiREP``: quest 383 in /dragonkoiz."""
    if cmd.get_faction_rank("Yokai") >= rank:
        return
    cmd.bot.log(f"[farm] farming Yokai reputation to rank {rank}")
    await farm_until(cmd, _rep_done(cmd, "Yokai", rank), "dragonkoiz",
                     monster="Pockey Chew", quests=(383,),
                     drops=["Piece of Pockey"])


async def evil_rep(cmd: Command, rank: int = 10) -> None:
    """``CoreFarms.EvilREP``: quest 364 to rank 4, then 367 (366 for members)."""
    if cmd.get_faction_rank("Evil") >= rank:
        return

    await change_alignment(cmd, Alignment.EVIL)
    cmd.bot.log(f"[farm] farming Evil reputation to rank {rank}")

    await farm_until(cmd, _rep_done(cmd, "Evil", 4), "swordhavenbridge",
                     monster="Slime", quests=(364,), drops=["Youthanize"])
    if cmd.get_faction_rank("Evil") >= rank:
        return

    # the reference registers 367 for both routes and, for members, turns 366 in
    # on every pass as well
    await cmd.register_quest(367)
    if cmd.get_player().is_member:
        while (cmd.is_still_connected()
               and cmd.get_faction_rank("Evil") < rank):
            await cmd.ensure_accept_quest(366)
            await hunt_item(cmd, "Chair", 4, "sleuthhound",
                            monster_name="Chair", is_temp=False)
            await hunt_item(cmd, "Table", 2, "sleuthhound",
                            monster_name="Table", is_temp=False)
            await hunt_item(cmd, "Bookcase", 1, "sleuthhound",
                            monster_name="Bookcase", is_temp=False)
            await cmd.ensure_turn_in_quest(366)
    else:
        await farm_until(cmd, _rep_done(cmd, "Evil", rank), "castleundead",
                         cell="Enter", pad="Left", monster="*")
    cmd.cancel_registered_quests()


async def chronospan_rep(cmd: Command, rank: int = 10) -> None:
    """``CoreFarms.ChronoSpanREP``: quest 2204's three drops in /thespan."""
    if cmd.get_faction_rank("ChronoSpan") >= rank:
        return

    cmd.bot.log(f"[farm] farming ChronoSpan reputation to rank {rank}")
    await equip_class(cmd)
    await cmd.register_quest(2204)
    guard = cmd.pass_guard(f"ChronoSpan rank {rank} (quest 2204)")
    saved_state(cmd, True, "thespan")

    while (cmd.is_still_connected()
           and cmd.get_faction_rank("ChronoSpan") < rank):
        if check_save_state(cmd):
            await execute_save_state(cmd)
        await hunt_item(cmd, "Tin of Ghost Dust", 2, "thespan", cell="r6",
                        pad="Left", monster_name="Moglin Ghost", is_temp=False)
        await hunt_item(cmd, "8 oz Fairy Glitter", 3, "thespan", cell="r4",
                        pad="Left", monster_name="Minx Fairy", is_temp=False)
        await hunt_item(cmd, "Tog Fang", 4, "thespan", cell="r4", pad="Left",
                        monster_name="Tog", is_temp=False)
        if not await guard.tick():
            break

    saved_state(cmd, False)
    cmd.cancel_registered_quests()


def monster_by_definition_id(cmd: Command, mon_id: int):
    """The map monster whose id is ``mon_id``, by either id the model carries.

    ``CraggleRockREP`` compares against Skua's ``Monster.ID``, and which id that
    is cannot be told from the scripts: ``z_CompiledScript.cs`` matches a monster
    by ``m.MapID == id || m.ID == id``, so the two are the same field in some
    builds and different in others.  This engine keeps both -- ``mon_map_id`` and
    ``mon_id`` -- and either match is accepted rather than guessing.
    """
    for monster in cmd.bot.monsters:
        if (str(monster.mon_id) == str(mon_id)
                or str(monster.mon_map_id) == str(mon_id)):
            return monster
    return None


async def craggle_rock_rep(cmd: Command, rank: int = 10) -> None:
    """``CoreFarms.CraggleRockREP``: quest 7277, chasing one monster id."""
    if cmd.get_faction_rank("CraggleRock") >= rank:
        return

    cmd.bot.log(f"[farm] farming CraggleRock reputation to rank {rank}")
    cmd.add_drop("Empowered Voidstone")
    await cmd.register_quest(7277)
    await equip_class(cmd, solo=True)
    saved_state(cmd, True, "wanders")

    while (cmd.is_still_connected()
           and cmd.get_faction_rank("CraggleRock") < rank):
        if check_save_state(cmd):
            await execute_save_state(cmd)
        monster = monster_by_definition_id(cmd, CRAGGLE_ROCK_ID)
        if monster is None:
            cmd.bot.log(f"[farm] monster id {CRAGGLE_ROCK_ID} is not in /wanders, so "
                  f"CraggleRock cannot be farmed. Stopping.")
            saved_state(cmd, False)
            cmd.cancel_registered_quests()
            return
        while cmd.is_still_connected() and cmd.is_not_in_cell(monster.frame):
            await cmd.jump_cell(monster.frame, "Left")
            await cmd.sleep(500)
        await cmd.use_next_skill(DEFAULT_SKILL_LIST,
                                f"id.{monster.mon_map_id}")

    saved_state(cmd, False)
    cmd.cancel_registered_quests()


#: ``CoreFarms.SandseaREP``: the five reputation quests, at the map's entrance.
SANDSEA_QUESTS = (916, 917, 919, 921, 922)
SANDSEA_MAP = "sandsea"
SANDSEA_CELL = "Enter"
SANDSEA_PAD = "Spawn"


async def sandsea_rep(cmd: Command, rank: int = 10) -> None:
    """``CoreFarms.SandseaREP``: quests 916/917/919/921/922 in /sandsea.

    The reference pins a save state and toggles the reputation boost around this
    loop; this engine has neither, and the boost stays off here as it does by
    default there.  Its trailing ``JumpWait`` is this engine's polling.

    This is the farm ``Adv.BuyItem`` reaches for when a shop entry needs Sandsea
    reputation -- Master Ranger's shop is one.
    """
    if cmd.get_faction_rank("Sandsea") >= rank:
        return

    await equip_class(cmd)
    cmd.bot.log(f"Farming rank {rank}")
    await farm_until(cmd, _rep_done(cmd, "Sandsea", rank), SANDSEA_MAP,
                     cell=SANDSEA_CELL, pad=SANDSEA_PAD, monster="*",
                     quests=SANDSEA_QUESTS)


#: ``CoreFarms.FishingREP``: the fishing minigame, not a quest farm.
FISHING_MAP = "fishing"
FISHING_BAIT = "Fishing Bait"
FISHING_DYNAMITE = "Fishing Dynamite"
FISHING_QUEST = 1682
FISHING_BAIT_FARM = ("greenguardwest", "West3", "Right", "Frogzard")
FISHING_DYNAMITE_FARM = ("greenguardwest", "West4", "Right", "Slime")
#: The reference's own starter value; the server's ``castWait`` replaces it.
FISHING_WAIT_MS = 3500
#: How long to wait for ``castWait`` / ``CatchResult`` before casting again.
FISHING_REPLY_TIMEOUT_MS = 10_000

#: How many casts between the rank/rep progress lines (see ``fishing_rep``).
FISHING_PROGRESS_EVERY = 25
#: How many casts with no reputation gain at all before the farm gives up.
FISHING_QUIET_CASTS = 100


async def get_bait_and_dynamite(cmd: Command, bait: int = 0,
                                dynamite: int = 20) -> None:
    """``CoreFarms.GetBaitandDynamite``: quest 1682 in /greenguardwest."""
    if (await cmd.has_item(FISHING_BAIT, bait)
            and await cmd.has_item(FISHING_DYNAMITE, dynamite)):
        return

    await cmd.register_quest(FISHING_QUEST)
    for item, qty, (map_name, cell, pad, monster) in (
            (FISHING_BAIT, bait, FISHING_BAIT_FARM),
            (FISHING_DYNAMITE, dynamite, FISHING_DYNAMITE_FARM)):
        if qty <= 0:
            continue
        await hunt_item(cmd, item, qty, map_name, cell=cell, pad=pad,
                        monster_name=monster, is_temp=False)
    cmd.cancel_registered_quests()
    cmd.bot.log("Returning to Fishing Map")


async def fishing_rep(cmd: Command, rank: int = 10) -> None:
    """``CoreFarms.FishingREP``: cast, wait, pull, repeat.

    A minigame rather than a quest farm: the rep comes from the fish the server
    turns in itself, so the whole job is the three-packet exchange

    ``FishCast`` -> ``castWait`` (its own ``wait`` ms) -> ``getFish`` ->
    ``CatchResult``.

    The cast timer is **not** fixed -- 2800 to 7000 ms in the capture -- so the
    wait comes from the ``castWait`` reply; the reference keeps ``3500`` only as
    its starter value.  What this port leaves out, and says so: ``shouldDerp``
    (the Derp Moosefish hunt, which needs achievement and web-badge reads this
    engine does not have) and ``TrashCan`` (discarding bait; there is no trash
    action here -- sell it instead if you want it gone).

    Progress is counted in catches, not in faction rank: the reputation lands
    with the ``turnIn`` the server sends *after* ``CatchResult``, so a rank read
    in the same pass would call every good cast a failed one.

    The loop keeps casting until the **server's** rank reaches ``rank`` -- an
    account that arrives at rank 9 simply keeps fishing.  ``FISHING_QUIET_CASTS``
    catches the case where the reputation stops moving at all, so a run reports
    instead of casting into the void.
    """
    if cmd.get_faction_rank("Fishing") >= rank:
        return

    caught = 0
    last_rep = cmd.get_faction_rep("Fishing")
    quiet_casts = 0
    await get_bait_and_dynamite(cmd, 0, 1)
    await equip_class(cmd)
    cmd.bot.log(f"Farming Fishing rank {rank}")

    while (cmd.is_still_connected()
           and cmd.get_faction_rank("Fishing") < rank):
        await get_bait_and_dynamite(cmd, 0, 50)
        if cmd.is_not_in_map(FISHING_MAP):
            await cmd.join_map(FISHING_MAP)
        while (cmd.is_still_connected()
               and await cmd.has_item(FISHING_DYNAMITE)
               and cmd.get_faction_rank("Fishing") < rank):
            cmd.bot.fishing_cast_wait = False
            cmd.bot.fishing_caught = False
            await cmd.sleep(1000)
            cmd.bot.log("Casting Dynamite...")
            # The last field is the dynamite the client is casting with, and a
            # real client sends how many it holds (capture: ``%23%`` with 23 in
            # the bag) -- Skua hard-codes 30, which only holds while its own
            # farm has left 30 or more.  Sending more than is held is what a
            # cast the server ignores looks like.
            held = max(1, int(cmd.get_quant_item(FISHING_DYNAMITE) or 0))
            await cmd.send_packet(f"%xt%zm%FishCast%1%Dynamite%{held}%")

            if not await _fishing_reply(cmd, "fishing_cast_wait"):
                cmd.bot.log("Timed out waiting for castWait packet.")
                continue
            wait_ms = cmd.bot.fishing_wait_ms or FISHING_WAIT_MS
            cmd.bot.log(f"Cast timer received: {wait_ms}ms")

            # The whole point of the packet: do not cast again before the timer
            # the server named has elapsed.
            await cmd.sleep(wait_ms)

            await cmd.send_packet("%xt%zm%getFish%1%false%")
            if not await _fishing_reply(cmd, "fishing_caught"):
                cmd.bot.log("Timed out waiting for CatchResult; skipping result "
                            "evaluation.")
                continue

            # The catch itself is the confirmation.  Reputation arrives from the
            # server (``addGoldExp`` carries the ``iRep``), so comparing the
            # faction rank inside the same pass reports a good cast as a failed
            # one -- which is why the reference only counts casts here.
            caught += 1
            cmd.bot.log(f"Dynamite cast completed [x{caught}]")
            if caught % FISHING_PROGRESS_EVERY == 0:
                # The rank/rep below are the server's own numbers, which is what
                # a shop gates on; logged so a run that never moves is visible
                # instead of silent.
                cmd.bot.log(f"[fish] {caught} casts, rank "
                            f"{cmd.get_faction_rank('Fishing')} (rep "
                            f"{cmd.get_faction_rep('Fishing')})")

            # Reputation is the only progress this farm has: if it stops moving
            # altogether the casts are not being counted by the server, and
            # carrying on would just spend dynamite forever.
            rep = cmd.get_faction_rep("Fishing")
            if rep > last_rep:
                last_rep = rep
                quiet_casts = 0
            else:
                quiet_casts += 1
                if quiet_casts >= FISHING_QUIET_CASTS:
                    cmd.bot.log(f"[fish] {quiet_casts} casts without any "
                                f"reputation (still rank "
                                f"{cmd.get_faction_rank('Fishing')}); stopping "
                                f"instead of casting forever.")
                    return


async def _fishing_reply(cmd: Command, flag: str) -> bool:
    """Wait (bounded) for one of the fishing replies to land."""
    deadline = time.monotonic() + FISHING_REPLY_TIMEOUT_MS / 1000
    while cmd.is_still_connected() and time.monotonic() < deadline:
        if getattr(cmd.bot, flag, False):
            setattr(cmd.bot, flag, False)
            return True
        await cmd.sleep(100)
    return False


# ---------------------------------------------------------------------------
# Boosts
# ---------------------------------------------------------------------------
#: ``GetBoost``'s two quests: (quest, reward item id, boost name).
BOOST_XP = (1614, 10850, "XP Boost! (10 min)")
BOOST_REP = (1615, 10997, "REPUTATION Boost! (10 min)")
BOOST_REP_RANK = 2


async def get_fish(cmd: Command, item_id: int, quant: int,
                   quest: int) -> None:
    """``CoreFarms.GetFish``: dynamite-cast in /fishing until the drop lands.

    The fish themselves are turned in by the server under whichever quest is
    accepted, so this only drives the same three-packet exchange as
    :func:`fishing_rep` and waits for the count.
    """
    if await cmd.has_item_id(item_id, quant):
        return

    while (cmd.is_still_connected()
           and not await cmd.has_item_id(item_id, quant)):
        if not await cmd.has_item(FISHING_DYNAMITE):
            await get_bait_and_dynamite(cmd, 0, 20)
        if cmd.is_not_in_map(FISHING_MAP):
            await cmd.join_map(FISHING_MAP)

        while (cmd.is_still_connected()
               and await cmd.has_item(FISHING_DYNAMITE)
               and not await cmd.has_item_id(item_id, quant)):
            cmd.bot.fishing_cast_wait = False
            cmd.bot.fishing_caught = False
            # same last field as ``fishing_rep``: how much dynamite is held
            held = max(1, int(cmd.get_quant_item(FISHING_DYNAMITE) or 0))
            await cmd.send_packet(f"%xt%zm%FishCast%1%Dynamite%{held}%")
            if not await _fishing_reply(cmd, "fishing_cast_wait"):
                cmd.bot.log("Timed out waiting for castWait packet.")
                continue
            wait_ms = cmd.bot.fishing_wait_ms or FISHING_WAIT_MS
            await cmd.sleep(wait_ms)
            await cmd.send_packet("%xt%zm%getFish%1%false%")
            await _fishing_reply(cmd, "fishing_caught")


async def get_boost(cmd: Command, boost_type: str = "XP", quantity: int = 1,
                    do_once: bool = False) -> None:
    """``CoreFarms.GetBoost``: quests 1614 (XP) and 1615 (reputation).

    Deviation, reported: the reference's loop condition is
    ``!CheckInventory(name, quantity) || doOnce``, which never ends once
    ``doOnce`` is set.  Here ``do_once`` means "run at least one pass even when
    the stack is already full" and the loop still stops at ``quantity``.

    ``TrashCan`` on the leftover bait is skipped: this engine has no discard
    action (sell it instead).

    Args:
        cmd (Command): Facade to act through.
        boost_type (str): ``"XP"`` for 1614, anything else for 1615.
        quantity (int): How many boosts to end up with.
        do_once (bool): Farm one pass even when already stocked.
    """
    quest, item_id, boost_name = (BOOST_XP if boost_type.upper() == "XP"
                                  else BOOST_REP)

    if not do_once and await cmd.has_item(boost_name, quantity):
        return

    cmd.farming_logger(boost_name, quantity)
    cmd.add_drop([FISHING_DYNAMITE, boost_name])
    await equip_class(cmd)

    if cmd.get_faction_rank("Fishing") < BOOST_REP_RANK:
        cmd.bot.log("Fishing Rank 2 required for Boost farm quest.")
        await fishing_rep(cmd, BOOST_REP_RANK)

    if not await cmd.is_completed_before(1615):
        if await cmd.ensure_accept_quest(BOOST_XP[0]) is False:
            cmd.bot.log("[farm] quest 1614 could not be accepted; boost farm "
                        "stops here.")
            return
        await get_fish(cmd, BOOST_XP[1], 30, BOOST_XP[0])
        await hunt_item(cmd, "Slime Sauce", 1, "greenguardwest",
                        monster_name="Slime")
        if await cmd.ensure_turn_in_quest(BOOST_XP[0]) is False:
            return

    passes = 0
    while cmd.is_still_connected():
        if passes and await cmd.has_item(boost_name, quantity):
            break
        passes += 1

        if await cmd.ensure_accept_quest(quest) is False:
            cmd.bot.log(f"[farm] quest {quest} could not be accepted; boost "
                        f"farm stops here.")
            break
        await get_fish(cmd, item_id, 30 if quest == BOOST_XP[0] else 5, quest)
        if quest == BOOST_XP[0]:
            # ``KillMonster("greenguardwest", "West4", "Right", "Slime", ...)``
            await hunt_item(cmd, "Slime Sauce", 1, "greenguardwest",
                            cell="West4", pad="Right", monster_name="Slime")
        else:
            await hunt_item(cmd, "Greenguard Seal", 1, "greenguardwest",
                            monster_name="Frogzard")
        if await cmd.ensure_turn_in_quest(quest) is False:
            break


#: ``CoreFarms.SomniaREP``: the three quests of /somnia, one pass per item set.
SOMNIA_MAP = "somnia"
SOMNIA_QUESTS = (7665, 7666, 7669)
SOMNIA_HUNTS = (("Dream Truffle", "Nightspore", 8),
                ("Orphium Ore", "Orpheum Elemental", 8),
                ("Dreamsilk", "Dream Larva", 5))


async def somnia_rep(cmd: Command, rank: int = 10) -> None:
    """``CoreFarms.SomniaREP``: quests 7665/7666/7669 in /somnia.

    The reference pins a save state and toggles the reputation boost around this
    loop; this engine has neither, and both stay off here as they do by default
    there.  Its ``EnsureAcceptmultiple``/``EnsureComplete`` triple is the three
    quests accepted, fed and turned in per pass -- ``log: false`` on the hunts,
    which is this engine's default logger.
    """
    if cmd.get_faction_rank("Somnia") >= rank:
        return

    await equip_class(cmd)
    cmd.bot.log(f"Farming rank {rank}")
    saved_state(cmd, True, SOMNIA_MAP)
    while cmd.is_still_connected() and cmd.get_faction_rank("Somnia") < rank:
        if check_save_state(cmd):
            await execute_save_state(cmd)
        for quest_id in SOMNIA_QUESTS:
            await cmd.ensure_accept_quest(quest_id)
        for item, monster, qty in SOMNIA_HUNTS:
            await hunt_item(cmd, item, qty, SOMNIA_MAP, monster_name=monster,
                            is_temp=True)
        for quest_id in SOMNIA_QUESTS:
            await cmd.ensure_turn_in_quest(quest_id)
    saved_state(cmd, False)


# ---------------------------------------------------------------------------
# Glacera
# ---------------------------------------------------------------------------
GLACERA_FARM_QUESTS = (5597, 5598, 5599, 5600)
GLACERA_FARM_MAP = "icewindwar"
GLACERA_FARM_CELL, GLACERA_FARM_PAD = "r5", "Left"
#: ``IceWindPass``'s last quest: the farm quests only unlock after it.
GLACERA_UNLOCK_QUEST = 5601


async def glacera_rep(cmd: Command, rank: int = 10) -> None:
    """``CoreFarms.GlaceraREP``: the four war quests in /icewindwar.

    Args:
        cmd (Command): Facade to act through.
        rank (int): Reputation rank wanted.
    """
    if cmd.get_faction_rank("Glacera") >= rank:
        return

    if not await cmd.is_completed_before(GLACERA_UNLOCK_QUEST):
        cmd.bot.log("Farming Quests are not unlocked, run the Glacera story "
                    "first: bot.story.glacera (do_all).")
        return

    await equip_class(cmd)
    saved_state(cmd, True, GLACERA_FARM_MAP)
    cmd.bot.log(f"Farming rank {rank}")

    for quest_id in GLACERA_FARM_QUESTS:
        await cmd.register_quest(quest_id)

    while (cmd.is_still_connected()
           and cmd.get_faction_rank("Glacera") < rank):
        if check_save_state(cmd):
            await execute_save_state(cmd)
        await kill_once(cmd, GLACERA_FARM_MAP, GLACERA_FARM_CELL,
                        GLACERA_FARM_PAD)

    cmd.cancel_registered_quests()
    saved_state(cmd, False)


# ---------------------------------------------------------------------------
# SpellCrafting
# ---------------------------------------------------------------------------
SPELLCRAFTING = "SpellCrafting"
SPELLCRAFTING_START_QUEST = 2260
SPELLCRAFTING_QUILL_QUEST = 2299
SPELLCRAFTING_INK_QUEST = 2322
SPELLCRAFTING_SHOP = 549
SPELLCRAFTING_SHOP_MAP = "dragonrune"
SPELLCRAFTING_INK = "Ember Ink"
SPELLCRAFTING_HALLOW_INK = "Hallow Ink"


async def spellcrafting_rep(cmd: Command, rank: int = 10) -> None:
    """``CoreFarms.SpellCraftingREP``: quests 2260/2299/2322.

    The rank-4 band runs in /mobius, whose SWF the reference loads client-side;
    :func:`bot.nation.core_nation.join_swf` is the port's equivalent (join + the
    cell), which is all this engine can do with a retired map asset.
    """
    from bot.nation.core_nation import join_swf

    if cmd.get_faction_rank(SPELLCRAFTING) >= rank:
        return

    cmd.add_drop(["Mystic Quills", "Mystic Parchment"])
    await equip_class(cmd)
    cmd.bot.log(f"Farming rank {rank}")

    if cmd.get_faction_rank(SPELLCRAFTING) == 0:
        if check_save_state(cmd):
            await execute_save_state(cmd)
        if await cmd.ensure_accept_quest(SPELLCRAFTING_START_QUEST) is False:
            cmd.bot.log(f"[farm] quest {SPELLCRAFTING_START_QUEST} could not be "
                        f"accepted; SpellCrafting stops here.")
            return
        await cmd.join_map(SPELLCRAFTING_SHOP_MAP)
        await cmd.get_map_item(1920, 1)
        await hunt_item(cmd, "Arcane Parchment", 13, "castleundead",
                        monster_name="Skeletal Warrior")
        await cmd.ensure_turn_in_quest(SPELLCRAFTING_START_QUEST)

    if cmd.get_faction_rank(SPELLCRAFTING) < 4:
        await join_swf(cmd, "mobius", "Slugfit", "Bottom")
        await hunt_item(cmd, "Mystic Quills", 10, "mobius",
                        monster_name="Slugfit")
        await buy_item(cmd, SPELLCRAFTING_SHOP, SPELLCRAFTING_INK, 50,
                       map_name=SPELLCRAFTING_SHOP_MAP)
        while (cmd.is_still_connected()
               and await cmd.has_item(SPELLCRAFTING_INK)
               and cmd.get_faction_rank(SPELLCRAFTING) < 4):
            await chain_complete(cmd, SPELLCRAFTING_QUILL_QUEST)

    saved_state(cmd, True, "underworld")
    while (cmd.is_still_connected()
           and cmd.get_faction_rank(SPELLCRAFTING) < rank):
        if check_save_state(cmd):
            await execute_save_state(cmd)
        await hunt_item(cmd, "Mystic Parchment", 10, "underworld",
                        monster_name="Skull Warrior")
        await buy_item(cmd, SPELLCRAFTING_SHOP, SPELLCRAFTING_HALLOW_INK, 50,
                       map_name=SPELLCRAFTING_SHOP_MAP)
        while (cmd.is_still_connected()
               and await cmd.has_item(SPELLCRAFTING_HALLOW_INK)
               and cmd.get_faction_rank(SPELLCRAFTING) < rank):
            await chain_complete(cmd, SPELLCRAFTING_INK_QUEST)
    saved_state(cmd, False)

    for ink in (SPELLCRAFTING_INK, SPELLCRAFTING_HALLOW_INK):
        held = cmd.get_quant_item(ink)
        if held:
            await cmd.sell_item(ink, held)


# ---------------------------------------------------------------------------
# Arcangrove
# ---------------------------------------------------------------------------
ARCANGROVE = "Arcangrove"
ARCANGROVE_MAP = "arcangrove"
#: The eight rep quests the reference registers at once.
ARCANGROVE_QUESTS = (794, 795, 796, 797, 798, 799, 800, 801)
#: ``KillMonster("arcangrove", cell, "Left", "*")`` -- the two kill cells.
ARCANGROVE_CELLS = ("LeftBack", "RightBack")
#: Ten kills per cell per pass, as the source's own loop does.
ARCANGROVE_KILLS = 10


async def arcangrove_rep(cmd: Command, rank: int = 10) -> None:
    """``CoreFarms.ArcangroveREP``: the eight quests plus the two kill cells.

    The reference toggles a reputation boost around this; this engine has no
    boosts, so that part is left out (as in every other rep farm here).
    """
    if cmd.get_faction_rank(ARCANGROVE) >= rank:
        return

    await equip_class(cmd)
    saved_state(cmd, True, ARCANGROVE_MAP)
    cmd.bot.log(f"Farming {ARCANGROVE} rank {rank}")

    for quest_id in ARCANGROVE_QUESTS:
        await cmd.register_quest(quest_id)
    while (cmd.is_still_connected()
           and cmd.get_faction_rank(ARCANGROVE) < rank):
        for cell in ARCANGROVE_CELLS:
            for _ in range(ARCANGROVE_KILLS):
                await kill_once(cmd, ARCANGROVE_MAP, cell, "Left", "*")
        if check_save_state(cmd):
            await execute_save_state(cmd)
    cmd.cancel_registered_quests()
    saved_state(cmd, False)



# ---------------------------------------------------------------------------
# The next REP batch
# ---------------------------------------------------------------------------
#: ``while (!ShouldExit && FactionRank(f) < rank) { CheckSaveState(); body(); }``
#: -- the shape every one of these farms shares.
async def _rep_loop(cmd: Command, faction: str, rank: int, body) -> None:
    while (cmd.is_still_connected()
           and cmd.get_faction_rank(faction) < rank):
        if check_save_state(cmd):
            await execute_save_state(cmd)
        await body()


MYTHSONG = "Mythsong"
MYTHSONG_QUEST = 4829
MYTHSONG_MAP = "beehive"


async def mythsong_rep(cmd: Command, rank: int = 10) -> None:
    """``CoreFarms.MythsongREP``: quest 4829 in /beehive.

    ``Bot.Quests.IsUnlocked(4829)`` is the Kimberly gate; this engine has no client
    to ask, so the port checks the story quest itself (710, Kimberly's last) and
    says the reference's own line when it is missing.
    """
    if cmd.get_faction_rank(MYTHSONG) >= rank:
        return
    if not await cmd.is_completed_before(710):
        cmd.bot.log("Can't do farming quest (Do Lord of Chaos Kimberly)")
        return

    await equip_class(cmd)
    saved_state(cmd, True, MYTHSONG_MAP)
    cmd.bot.log(f"Farming rank {rank}")

    await cmd.register_quest(MYTHSONG_QUEST)

    async def hunt() -> None:
        await hunt_item(cmd, "Honey Gathered", 10, MYTHSONG_MAP,
                        monster_name="Stinger")

    await _rep_loop(cmd, MYTHSONG, rank, hunt)
    cmd.cancel_registered_quests()
    saved_state(cmd, False)


DOOMWOOD = "DoomWood"
DOOMWOOD_QUESTS = (1151, 1152, 1153)
DOOMWOOD_MAP = "shadowfallwar"


async def doomwood_rep(cmd: Command, rank: int = 10) -> None:
    """``CoreFarms.DoomWoodREP``: quests 1151-1153 in /shadowfallwar."""
    if cmd.get_faction_rank(DOOMWOOD) >= rank:
        return

    await equip_class(cmd)
    saved_state(cmd, True, DOOMWOOD_MAP)
    cmd.bot.log(f"Farming rank {rank}")

    for quest_id in DOOMWOOD_QUESTS:
        await cmd.register_quest(quest_id)

    async def kill() -> None:
        await kill_once(cmd, DOOMWOOD_MAP, "Garden1", "Left", "*")

    await _rep_loop(cmd, DOOMWOOD, rank, kill)
    cmd.cancel_registered_quests()
    saved_state(cmd, False)


EMBERSEA = "Embersea"
EMBERSEA_EASY_QUEST = 4080
EMBERSEA_HARD_QUEST = 4228
EMBERSEA_EASY_MAP = "Pyrewatch"
#: ``if (!TempInv.Contains(28575, 4)) Bot.Map.GetMapItem(3162)``.
EMBERSEA_MAP_ITEM = 3162
EMBERSEA_TEMP_ITEM = 28575
EMBERSEA_HARD_MAP = "fireforge"
#: ``HuntMonsterMapID("fireforge", 4)`` -- the Blazebinder's map id.
EMBERSEA_MONSTER_ID = 4


async def embersea_rep(cmd: Command, rank: int = 10) -> None:
    """``CoreFarms.EmberseaREP``: 4080 when the story allows it, 4228 otherwise.

    The fallback branch hunts by monster **map id** (``HuntMonsterMapID``), which
    ``hunt_item_by_id`` can target; the quest pays per kill rather than per item,
    so the loop kills ``*`` in that map and lets the registered quest do the rest.
    """
    if cmd.get_faction_rank(EMBERSEA) >= rank:
        return

    await equip_class(cmd)
    saved_state(cmd, True, EMBERSEA_HARD_MAP)
    cmd.bot.log(f"Farming rank {rank}")

    easy = await cmd.is_completed_before(EMBERSEA_EASY_QUEST)
    await cmd.register_quest(EMBERSEA_EASY_QUEST if easy else EMBERSEA_HARD_QUEST)

    if easy:
        async def easy_pass() -> None:
            if cmd.is_not_in_map(EMBERSEA_EASY_MAP):
                await cmd.join_map(EMBERSEA_EASY_MAP)
            held = cmd.bot.player.get_item_temp_inventory_by_id(EMBERSEA_TEMP_ITEM)
            if int(getattr(held, "qty", 0) or 0) < 4:
                await cmd.get_map_item(EMBERSEA_MAP_ITEM)
            await cmd.sleep(500)

        await _rep_loop(cmd, EMBERSEA, rank, easy_pass)
    else:
        cmd.bot.log("[farm] Embersea's easy method needs quest 4080; killing the "
                    "Blazebinders in /fireforge instead.")

        async def hard_pass() -> None:
            await kill_once(cmd, EMBERSEA_HARD_MAP, monster="*")

        await _rep_loop(cmd, EMBERSEA, rank, hard_pass)

    cmd.cancel_registered_quests()
    saved_state(cmd, False)


DWARFHOLD = "Dwarfhold"
DWARFHOLD_UNLOCK_QUEST = 319
DWARFHOLD_MAP_ITEM = 56
DWARFHOLD_MAP_ITEM_QTY = 7
DWARFHOLD_QUESTS = (320, 321)
DWARFHOLD_MAP = "pines"
DWARFHOLD_KILLS = (("Pine Grizzly", "Bear Skin"),
                   ("Red Shell Turtle", "Red Turtle Shell"))


async def dwarfhold_rep(cmd: Command, rank: int = 10) -> None:
    """``CoreFarms.DwarfholdREP``: quests 320/321 in /pines."""
    if cmd.get_faction_rank(DWARFHOLD) >= rank:
        return

    # ``if (!Bot.Quests.IsUnlocked(320))`` -- the unlock quest is 319.
    if not await cmd.is_completed_before(DWARFHOLD_UNLOCK_QUEST):
        if await cmd.ensure_accept_quest(DWARFHOLD_UNLOCK_QUEST) is not False:
            await cmd.join_map("tavern")
            await cmd.get_map_item(DWARFHOLD_MAP_ITEM, DWARFHOLD_MAP_ITEM_QTY)
            await cmd.ensure_turn_in_quest(DWARFHOLD_UNLOCK_QUEST)

    await equip_class(cmd)
    saved_state(cmd, True, DWARFHOLD_MAP)
    cmd.bot.log(f"Farming rank {rank}")

    async def pass_() -> None:
        # ``EnsureAcceptmultiple(320, 321)`` then one kill round, then both turn
        # in -- the quests are repeatable, so the pair is re-accepted each pass.
        for quest_id in DWARHFOLD_QUESTS:
            await cmd.ensure_accept_quest(quest_id)
        for monster, item in DWARHFOLD_KILLS:
            await hunt_item(cmd, item, 5, DWARFHOLD_MAP, cell="Enter",
                            pad="Right", monster_name=monster)
        for quest_id in DWARHFOLD_QUESTS:
            await cmd.ensure_turn_in_quest(quest_id)

    await _rep_loop(cmd, DWARFHOLD, rank, pass_)
    saved_state(cmd, False)


LYCAN = "Lycan"
LYCAN_QUEST = 537
LYCAN_MAP = "lycan"


async def lycan_rep(cmd: Command, rank: int = 10) -> None:
    """``CoreFarms.LycanREP``: quest 537 in /lycan (needs 537 completed first)."""
    if cmd.get_faction_rank(LYCAN) >= rank:
        return
    if not await cmd.is_completed_before(LYCAN_QUEST):
        cmd.bot.log("Can't do farming quest [Sanguine] (/lycan)")
        return

    await equip_class(cmd, solo=True)
    saved_state(cmd, True, LYCAN_MAP)
    cmd.bot.log(f"Farming rank {rank}")

    await cmd.register_quest(LYCAN_QUEST)

    async def hunt() -> None:
        await hunt_item(cmd, "Sanguine Mask", 1, LYCAN_MAP,
                        monster_name="Sanguine")

    await _rep_loop(cmd, LYCAN, rank, hunt)
    cmd.cancel_registered_quests()
    saved_state(cmd, False)


HORC = "Horc"
HORC_QUEST = 1265
HORC_MAP = "bloodtuskwar"
#: ``(monster, item, qty)`` for quest 1265's three drops.
HORC_DROPS = (("Chaotic Lemurphant", "Chaorrupted Eye", 3),
              ("Chaotic Horcboar", "Chaorrupted Tentacle", 5),
              ("Chaotic Chinchilizard", "Chaorrupted Tusk", 5))


async def horc_rep(cmd: Command, rank: int = 10) -> None:
    """``CoreFarms.HorcREP``: quest 1265 in /bloodtuskwar, accepted per pass."""
    if cmd.get_faction_rank(HORC) >= rank:
        return

    await equip_class(cmd)
    saved_state(cmd, True, HORC_MAP)
    cmd.bot.log(f"Farming rank {rank}")

    async def pass_() -> None:
        await cmd.ensure_accept_quest(HORC_QUEST)
        for monster, item, qty in HORC_DROPS:
            await hunt_item(cmd, item, qty, HORC_MAP, monster_name=monster)
        await cmd.ensure_turn_in_quest(HORC_QUEST)

    await _rep_loop(cmd, HORC, rank, pass_)
    saved_state(cmd, False)



#: Faction name -> the ported method, mirroring ``CoreFarms.<Name>REP``.
FACTION_FARMS = {
    "Good": good_rep,
    "Somnia": somnia_rep,
    "Sandsea": sandsea_rep,
    "Vampire": vampire_rep,
    "Yokai": yokai_rep,
    "Evil": evil_rep,
    "ChronoSpan": chronospan_rep,
    "CraggleRock": craggle_rock_rep,
    "Glacera": glacera_rep,
    "SpellCrafting": spellcrafting_rep,
    "Arcangrove": arcangrove_rep,
    "Mythsong": mythsong_rep,
    "DoomWood": doomwood_rep,
    "Embersea": embersea_rep,
    "Dwarfhold": dwarfhold_rep,
    "Lycan": lycan_rep,
    "Horc": horc_rep,
}

async def farm_faction(cmd: Command, faction: str, rank: int = 10) -> bool:
    """Farm ``faction`` to ``rank`` with the method for that name.

    The reference calls the method named after the faction; this is that
    mapping.  A faction that is not ported is reported along with the ones that
    are -- never a silent no-op.

    Returns:
        bool: True when a farm for ``faction`` ran, False when it is not ported.
    """
    farm = FACTION_FARMS.get(faction)
    if farm is None:
        cmd.bot.log(f"[farm] {faction!r} reputation is not ported yet. Ported: "
              f"{', '.join(sorted(FACTION_FARMS))}.")
        return False
    await farm(cmd, rank)
    return True


# ---------------------------------------------------------------------------
# Quest items the Nation cores ask for
# ---------------------------------------------------------------------------

#: ``CoreFarms.BlackKnightOrb`` -- quest 318's four pieces, one per map.
BLACK_KNIGHT_ORB = "Black Knight Orb"
BLACK_KNIGHT_ORB_QUEST = 318
BLACK_KNIGHT_ORB_PIECES = (
    ("well", "Gell Oh No", "Black Knight Leg Piece"),
    ("greendragon", "Greenguard Dragon", "Black Knight Chest Piece"),
    ("deathgazer", "Deathgazer", "Black Knight Shoulder Piece"),
    ("trunk", "GreenGuard Basilisk", "Black Knight Arm Piece"),
)


async def black_knight_orb(cmd: Command) -> None:
    """``CoreFarms.BlackKnightOrb``: quest 318, one piece in each of four maps.

    The reference closes with ``Bot.Wait.ForPickup``; the reward is waited for
    here too, through ``bot.core_bots.wait_for_item``.  Its ``EnsureAccept`` loops
    until the quest is active, so a refusal there never reaches the hunt; this
    engine's accept gives up and reports instead, which is why the guard below
    stops rather than killing for a quest that is not running.
    """
    if await cmd.has_item(BLACK_KNIGHT_ORB):
        return

    cmd.add_drop(BLACK_KNIGHT_ORB)
    if not await cmd.ensure_accept_quest(BLACK_KNIGHT_ORB_QUEST):
        cmd.bot.log(f"[farm] quest {BLACK_KNIGHT_ORB_QUEST} ({BLACK_KNIGHT_ORB}) "
              f"cannot be accepted; nothing farmed.")
        return
    total = len(BLACK_KNIGHT_ORB_PIECES)
    for index, (map_name, monster, piece) in enumerate(BLACK_KNIGHT_ORB_PIECES, 1):
        cmd.bot.log(f"[farm] {BLACK_KNIGHT_ORB} piece {index}/{total}: {piece} "
                    f"from {monster} in /{map_name}")
        await hunt_item(cmd, piece, 1, map_name, monster_name=monster,
                        is_temp=True)
    await cmd.ensure_turn_in_quest(BLACK_KNIGHT_ORB_QUEST)
    await wait_for_item(cmd, BLACK_KNIGHT_ORB)


# ---------------------------------------------------------------------------
# CoreFarms.BlacksmithingREP
# ---------------------------------------------------------------------------

BLACKSMITHING = "Blacksmithing"
BLACKSMITHING_GOLD_QUEST = 8737
BLACKSMITHING_GOLD_SHOP = 2036
BLACKSMITHING_GOLD_VOUCHER = "Gold Voucher 500k"
BLACKSMITHING_QUEST = 8736
BLACKSMITHING_STARTER_QUEST = 2777
BLACKSMITHING_STARTER_RANK = 4


def remaining_faction_xp(cmd: Command, faction: str) -> int:
    """Reputation still needed for the next rank of ``faction``.

    The reference asks its client for ``RemainingRep``; this engine reads the
    account's total reputation and takes it off the next threshold, which is the
    same number from data the server sends.

    Args:
        cmd (Command): Facade to act through.
        faction (str): Faction name, e.g. ``"Blacksmithing"``.

    Returns:
        int: Points to the next rank, or 302500 (rank 10's cost) when the faction
        is not tracked, which is the reference's own fallback.
    """
    if not faction or not faction.strip():
        return 302500
    rank = cmd.get_faction_rank(faction)
    if rank >= 10:
        return 0
    for threshold_rank, points in REP_THRESHOLDS:
        if threshold_rank == rank + 1:
            return max(0, points - cmd.get_faction_rep(faction))
    return 302500


async def blacksmithing_rep(cmd: Command, rank: int = 10, use_gold: bool = False,
                            bulk_farm_gold: bool = False) -> None:
    """``CoreFarms.BlacksmithingREP``: reputation by gold, or by three kills.

    Args:
        cmd (Command): Facade to act through.
        rank (int): Target rank.
        use_gold (bool): The reference's ``UseGold`` option: buy Gold Vouchers in
            /alchemyacademy and hand them over, instead of the slow route.
        bulk_farm_gold (bool): Accepted but unused, as it is in the source.

    Note:
        The gold branch buys the vouchers through ``CoreBots.BuyItem`` -- the plain
        one, not ``Adv.BuyItem`` -- and the source calls it **twice** in a row: once
        in the ``else`` of the "already have them" check and then again
        unconditionally, so a missing stack is paid for twice.  That is reproduced
        here rather than repaired; it is in the deviation register.
    """
    if cmd.get_faction_rank(BLACKSMITHING) >= rank:
        return

    await equip_class(cmd)
    cmd.bot.log(f"Farming rank {rank}")

    if use_gold:
        cmd.bot.log("Using Gold Method")
        saved_state(cmd, True, "alchemyacademy")
        while (cmd.is_still_connected()
               and cmd.get_faction_rank(BLACKSMITHING) < rank):
            if check_save_state(cmd):
                await execute_save_state(cmd)
            await cmd.ensure_accept_quest(BLACKSMITHING_GOLD_QUEST)

            remaining = remaining_faction_xp(cmd, BLACKSMITHING)
            items_needed = (remaining + 999) // 1000
            current = cmd.get_quant_item(BLACKSMITHING_GOLD_VOUCHER)

            cmd.bot.log(f"Remaining Reputation XP: {remaining}")
            cmd.bot.log(f"Current Gold Voucher Quantity: {current}")
            cmd.bot.log(f"Items Needed: {items_needed}")

            if remaining <= 0:
                cmd.bot.log("Already at max rank.")
                return

            items_to_buy = min(200, max(0, min(items_needed, 300 - current)))
            cmd.bot.log(f"Items to Buy in this Transaction: {items_to_buy}")

            gold_needed = items_to_buy * 500000
            cmd.bot.log(f"Gold Needed for {items_to_buy} vouchers: {gold_needed}")

            await farm_gold(cmd, gold_needed)

            if await cmd.has_item(BLACKSMITHING_GOLD_VOUCHER, items_to_buy):
                cmd.bot.log(f"Already have {items_to_buy} Gold Vouchers, "
                            f"skipping purchase.")
            else:
                await buy_item(cmd, BLACKSMITHING_GOLD_SHOP,
                               BLACKSMITHING_GOLD_VOUCHER, items_to_buy,
                               map_name="alchemyacademy")
            await buy_item(cmd, BLACKSMITHING_GOLD_SHOP,
                           BLACKSMITHING_GOLD_VOUCHER, items_to_buy,
                           map_name="alchemyacademy")
            await cmd.ensure_turn_in_quest(BLACKSMITHING_GOLD_QUEST,
                                           amount=items_needed)
        saved_state(cmd, False)
        return

    cmd.bot.log("Using Non-Gold Method")
    await cmd.register_quest(BLACKSMITHING_STARTER_QUEST)
    starter_guard = cmd.pass_guard(
        f"{BLACKSMITHING} rank {BLACKSMITHING_STARTER_RANK} "
        f"(quest {BLACKSMITHING_STARTER_QUEST})")
    saved_state(cmd, True, "greenguardwest")
    while (cmd.is_still_connected()
           and cmd.get_faction_rank(BLACKSMITHING) < BLACKSMITHING_STARTER_RANK
           and not use_gold):
        if check_save_state(cmd):
            await execute_save_state(cmd)
        await hunt_item(cmd, "Furry Lost Sock", 2, "greenguardeast",
                        monster_name="Wolf")
        await hunt_item(cmd, "Slimy Lost Sock", 5, "greenguardwest",
                        monster_name="Slime")
        if not await starter_guard.tick():
            break
    saved_state(cmd, False)
    cmd.cancel_registered_quests()

    await cmd.register_quest(BLACKSMITHING_QUEST)
    await equip_class(cmd, solo=True)
    guard = cmd.pass_guard(f"{BLACKSMITHING} rank {rank} "
                           f"(quest {BLACKSMITHING_QUEST})")
    saved_state(cmd, True, "hydrachallenge")
    while (cmd.is_still_connected()
           and cmd.get_faction_rank(BLACKSMITHING) < rank
           and not use_gold):
        if check_save_state(cmd):
            await execute_save_state(cmd)
        await hunt_item(cmd, "Hydra Scale Piece", 75, "hydrachallenge",
                        monster_name="Hydra Head 25", is_temp=False)
        await hunt_item(cmd, "Creature Shard", 1, "maul",
                        monster_name="Creature Creation", is_temp=False)
        await hunt_item(cmd, "Monster Trophy", 15, "towerofdoom",
                        monster_name="Dread Klunk", is_temp=False)
        if not await guard.tick():
            break
    saved_state(cmd, False)
    cmd.cancel_registered_quests()


# ---------------------------------------------------------------------------
# Blade of Awe
# ---------------------------------------------------------------------------
BLADE_OF_AWE = "Blade of Awe"
#: The weapon ``UnlockBoA``'s quests unlock; rank 6 is all the rep it needs.
BOA_ITEM = 17585
BOA_SHOP, BOA_SHOP_MAP = 631, "museum"
#: The rep quest the farm loop registers.
BOA_FARM_QUEST = 2935
BOA_MAP, BOA_CELL, BOA_PAD = "castleundead", "Enter", "Left"
BOA_MONSTER = "Skeletal Viking"
#: ``UnlockBoA``'s first four quests: (quest, map, monster, item, solo).
BOA_UNLOCKS = (
    (2933, "j6", "Sketchy Dragon", "Stonewrit Found!", True),
    (2934, "gilead", "Fire Elemental", "Handle Found!", True),
    (2935, "castleundead", "Skeletal Viking", "Hilt Found!", False),
    (2936, "hydra", "Hydra Head", "Blade Found!", False),
)
BOA_RUNES_QUEST = 2937
BOA_RUNES_ITEM = "Runes Found!"


async def unlock_boa(cmd: Command) -> None:
    """``CoreFarms.UnlockBoA``: quests 2933-2937, the Blade of Awe's unlocks.

    Note:
        The reference calls ``Core.ResetQuest(2937)`` first -- accept, abandon,
        accept again -- to shake off a stuck run.  This engine has no abandon
        packet, so that one step is the accept alone; every other quest here is
        one hunt and one turn-in, as in the source.
    """
    if await cmd.is_completed_before(BOA_RUNES_QUEST):
        return

    for quest_id, map_name, monster, item, solo in BOA_UNLOCKS:
        if await cmd.is_completed_before(quest_id):
            cmd.bot.log(f"Already Completed: [{quest_id}]")
            continue

        cmd.bot.log(f'Doing Quest: [{quest_id}] - "{item}"')
        await equip_class(cmd, solo=solo)
        if await cmd.ensure_accept_quest(quest_id) is False:
            cmd.bot.log(f"[farm] quest {quest_id} could not be accepted; the "
                        f"Blade of Awe unlock stops here.")
            return
        await hunt_item(cmd, item, 1, map_name, monster_name=monster,
                        is_temp=False)
        if await cmd.ensure_turn_in_quest(quest_id) is False:
            cmd.bot.log(f"[farm] quest {quest_id} could not be turned in; the "
                        f"Blade of Awe unlock stops here.")
            return
        cmd.bot.log(f"Completed Quest: [{quest_id}]")

    if await cmd.is_completed_before(BOA_RUNES_QUEST):
        cmd.bot.log(f"Already Completed: [{BOA_RUNES_QUEST}]")
        return

    from bot.nation.core_nation import kill_escherion

    cmd.bot.log(f'Doing Quest: [{BOA_RUNES_QUEST}] - "{BOA_RUNES_ITEM}"')
    await equip_class(cmd, solo=True)
    if await cmd.ensure_accept_quest(BOA_RUNES_QUEST) is False:
        cmd.bot.log(f"[farm] quest {BOA_RUNES_QUEST} could not be accepted.")
        return
    await kill_escherion(cmd, BOA_RUNES_ITEM)
    if await cmd.ensure_turn_in_quest(BOA_RUNES_QUEST) is False:
        cmd.bot.log(f"[farm] quest {BOA_RUNES_QUEST} could not be turned in.")
        return
    cmd.bot.log(f"Completed Quest: [{BOA_RUNES_QUEST}]")


async def blade_of_awe_rep(cmd: Command, rank: int = 10,
                           farm_boa: bool = True) -> None:
    """``CoreFarms.BladeofAweREP``: rank the faction in /castleundead.

    Args:
        cmd (Command): Facade to act through.
        rank (int): Reputation rank wanted.
        farm_boa (bool): Also unlock and buy the Blade of Awe itself.
    """
    await unlock_boa(cmd)

    target = 6 if farm_boa and not await cmd.has_item_id(BOA_ITEM) else rank
    current = cmd.get_faction_rank(BLADE_OF_AWE)
    if current < target or (farm_boa and current < rank):
        saved_state(cmd, True, BOA_MAP)
        await equip_class(cmd)
        cmd.bot.log(f"Farming rank {target if current < target else rank}")

        await cmd.register_quest(BOA_FARM_QUEST)
        while (cmd.is_still_connected()
               and (cmd.get_faction_rank(BLADE_OF_AWE) < target
                    or (farm_boa
                        and cmd.get_faction_rank(BLADE_OF_AWE) < target))):
            if check_save_state(cmd):
                await execute_save_state(cmd)
            await kill_once(cmd, BOA_MAP, BOA_CELL, BOA_PAD, BOA_MONSTER)
        cmd.cancel_registered_quests()
        saved_state(cmd, False)

    if farm_boa and not await cmd.has_item_id(BOA_ITEM):
        await buy_item(cmd, BOA_SHOP, BOA_ITEM, map_name=BOA_SHOP_MAP)
