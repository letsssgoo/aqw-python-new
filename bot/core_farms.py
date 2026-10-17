"""The reference bot's ``CoreFarms``: gold, experience and faction reputation.

Port of ``CoreFarms.cs``.  It sits in ``bot/`` beside the other root cores
because that is where the reference keeps it; the runnable ``Farm/`` scripts
that wrap it are mirrored under ``bot/farm/``.

Both cores are driven the same way: register the quests the reference registers
and let the auto-quest task (``handlers/register_quest.py``) accept and turn them
in between kills, which is what its own auto-quest task does.  What differs is
noted where it happens:

* ``Core.SavedState`` / ``CheckSaveState`` / ``ExecuteSaveState`` are not ported.
  They exist in the reference to put the character back after a death; this
  engine's ``check_alive`` waits for the respawn and its ``death_handler`` owns
  it, so there is nothing for a save state to repair.
* Boosts are not available: ``CoreFarms.ToggleBoost`` drives Skua's boost
  items, which this engine has no support for.  The reference keeps every boost
  switched **off** by default, so leaving the calls out changes nothing today --
  the sites that would toggle one carry a comment saying so.
* ``ClassType`` has no "unset" case in the reference.  Here an unconfigured
  class is reported and the farm continues, rather than stopping a long run
  over a settings gap.
"""
import random
from typing import Awaitable, Callable, Optional, Sequence, Tuple

from bot.core_bots import (Alignment, REP_THRESHOLDS, buy_item, can_we_aggro,
                           change_alignment,
                           equip_class, wait_for_item)
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
#: and one ``(…, monster map id)`` per boss.
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

    while cmd.is_still_connected() and not done():
        can_we_aggro(cmd)
        await cmd.use_next_skill(DEFAULT_SKILL_LIST, monster, hunt)
        if each is not None:
            await each()

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
                         rank_up_class: bool = False) -> None:
    """``CoreFarms.IcestormArena``: one cell per level band, up to level 100.

    Levels 61-75 follow BattleGroundE instead of the arena -- except for a
    rank-up run, which stays in the arena -- and 75+ moves to /icestormunder.
    """
    if cmd.get_player().LEVEL >= level and not rank_up_class:
        return

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

    while (cmd.is_still_connected()
           and cmd.get_faction_rank("ChronoSpan") < rank):
        await hunt_item(cmd, "Tin of Ghost Dust", 2, "thespan", cell="r6",
                        pad="Left", monster_name="Moglin Ghost", is_temp=False)
        await hunt_item(cmd, "8 oz Fairy Glitter", 3, "thespan", cell="r4",
                        pad="Left", monster_name="Minx Fairy", is_temp=False)
        await hunt_item(cmd, "Tog Fang", 4, "thespan", cell="r4", pad="Left",
                        monster_name="Tog", is_temp=False)

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

    while (cmd.is_still_connected()
           and cmd.get_faction_rank("CraggleRock") < rank):
        monster = monster_by_definition_id(cmd, CRAGGLE_ROCK_ID)
        if monster is None:
            cmd.bot.log(f"[farm] monster id {CRAGGLE_ROCK_ID} is not in /wanders, so "
                  f"CraggleRock cannot be farmed. Stopping.")
            cmd.cancel_registered_quests()
            return
        while cmd.is_still_connected() and cmd.is_not_in_cell(monster.frame):
            await cmd.jump_cell(monster.frame, "Left")
            await cmd.sleep(500)
        await cmd.use_next_skill(DEFAULT_SKILL_LIST,
                                f"id.{monster.mon_map_id}")

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


#: Faction name -> the ported method, mirroring ``CoreFarms.<Name>REP``.
FACTION_FARMS = {
    "Good": good_rep,
    "Sandsea": sandsea_rep,
    "Vampire": vampire_rep,
    "Yokai": yokai_rep,
    "Evil": evil_rep,
    "ChronoSpan": chronospan_rep,
    "CraggleRock": craggle_rock_rep,
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
        while (cmd.is_still_connected()
               and cmd.get_faction_rank(BLACKSMITHING) < rank):
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
        return

    cmd.bot.log("Using Non-Gold Method")
    await cmd.register_quest(BLACKSMITHING_STARTER_QUEST)
    while (cmd.is_still_connected()
           and cmd.get_faction_rank(BLACKSMITHING) < BLACKSMITHING_STARTER_RANK
           and not use_gold):
        await hunt_item(cmd, "Furry Lost Sock", 2, "greenguardeast",
                        monster_name="Wolf")
        await hunt_item(cmd, "Slimy Lost Sock", 5, "greenguardwest",
                        monster_name="Slime")
    cmd.cancel_registered_quests()

    await cmd.register_quest(BLACKSMITHING_QUEST)
    await equip_class(cmd, solo=True)
    while (cmd.is_still_connected()
           and cmd.get_faction_rank(BLACKSMITHING) < rank
           and not use_gold):
        await hunt_item(cmd, "Hydra Scale Piece", 75, "hydrachallenge",
                        monster_name="Hydra Head 25", is_temp=False)
        await hunt_item(cmd, "Creature Shard", 1, "maul",
                        monster_name="Creature Creation", is_temp=False)
        await hunt_item(cmd, "Monster Trophy", 15, "towerofdoom",
                        monster_name="Dread Klunk", is_temp=False)
    cmd.cancel_registered_quests()
