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
from typing import Awaitable, Callable, Optional, Sequence

from bot.core_bots import (Alignment, can_we_aggro, change_alignment,
                           equip_class)
from core.command import Command
from templates.hunt import DEFAULT_SKILL_LIST, hunt_item

#: Gold the reference asks for when a caller does not say.
DEFAULT_GOLD = 100_000_000

#: Levels below this are farmed through the story chain, not the arena.
_ICESTORM_FROM = 20

#: The monster ``CoreFarms.CraggleRockREP`` hunts in /wanders, by its own id.
CRAGGLE_ROCK_ID = 560


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
        print("[farm] the client is not connected; nothing farmed.")
        return False

    await equip_class(cmd, solo=solo)

    if cmd.is_not_in_map(map_name):
        print(f"[farm] {map_name}: travelling")
    while cmd.is_still_connected() and cmd.is_not_in_map(map_name):
        await cmd.join_map(map_name)
        await cmd.sleep(500)
    if not cmd.is_still_connected():
        print(f"[farm] disconnected while joining {map_name}.")
        return False

    if cell:
        while cmd.is_still_connected() and cmd.is_not_in_cell(cell):
            await cmd.jump_cell(cell, pad)
            await cmd.sleep(500)
    else:
        await cmd.jump_to_monster(monster)
    if not cmd.is_still_connected():
        print(f"[farm] disconnected while moving to {cell or monster}.")
        return False

    if quests:
        # The reference registers its quests and hopes; a quest whose story or
        # level requirement is missing then farms forever for a turn-in that can
        # never come.  Ask the server once, and report instead of spinning.
        if not await cmd.ensure_accept_quest(quests[0], max_attempts=3):
            print(f"[farm] quest {quests[0]} cannot be accepted, so its story or "
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
        print(f"[farm] disconnected before {map_name} was done.")
        return False
    return True


async def _sell_all(cmd: Command, item_name: str) -> None:
    """Sell every copy held (the reference's ``Core.SellItem(name, all: true)``)."""
    have = cmd.get_quant_item(item_name)
    if have:
        await cmd.sell_item(item_name, have)


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
        print(f"[farm] gold farm stopped at {gold} of {quant}: no method could "
              f"take it further (HonorHall needs membership and level 61, "
              f"BattleGroundE level 61, BerserkerBunny the /greenguardwest farm).")
        return False
    return True


async def honor_hall(cmd: Command, gold_quant: int = DEFAULT_GOLD) -> None:
    """``CoreFarms.HonorHall``: quests 3992+3993 on Ice Demons, members, 61+."""
    player = cmd.get_player()
    if not player.is_member or player.LEVEL < 61 or player.GOLD >= gold_quant:
        return
    print(f"[farm] honorhall: farming to {gold_quant} gold on Ice Demons")
    await farm_until(cmd, lambda: cmd.get_player().GOLD >= gold_quant,
                     "honorhall", cell="r1", pad="Center", monster="Ice Demon",
                     quests=(3992, 3993))


async def battle_ground_e(cmd: Command, gold_quant: int = DEFAULT_GOLD) -> None:
    """``CoreFarms.BattleGroundE``: quests 3991+3992 in /battlegrounde, 61+."""
    player = cmd.get_player()
    if player.LEVEL < 61 or player.GOLD >= gold_quant:
        return
    print(f"[farm] battlegrounde: farming to {gold_quant} gold")
    await farm_until(cmd, lambda: cmd.get_player().GOLD >= gold_quant,
                     "battlegrounde", cell="r2", pad="center", monster="*",
                     quests=(3991, 3992))


async def berserker_bunny(cmd: Command, gold_quant: int = DEFAULT_GOLD,
                          sell: bool = True) -> None:
    """``CoreFarms.BerserkerBunny``: quest 236 in /greenguardwest, selling drops."""
    if cmd.get_player().GOLD >= gold_quant:
        return
    print(f"[farm] greenguardwest: farming to {gold_quant} gold on Berserker "
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
    print(f"[farm] darkwarlegion: farming to {gold_quant} gold")
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
        print("[farm] rank-up-class farming needs the class rank, which this "
              f"engine cannot read; farming to level {level} instead.")

    await equip_class(cmd)
    # the reference toggles its experience boost here; this engine has no boosts

    if cmd.get_player().LEVEL < 10:
        print('[farm] oaklore: "Bone Berserker" up to level 10')
        await farm_until(cmd, lambda: cmd.get_player().LEVEL >= min(10, level),
                         "oaklore", cell="r3", pad="Left",
                         monster="Bone Berserker", quests=(4007, 6257))

    if cmd.get_player().LEVEL >= level and not rank_up_class:
        return

    if cmd.get_player().LEVEL < 20:
        await undead_giant_unlock(cmd)
        print('[farm] swordhavenundead: "Undead Giant" up to level 20')
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
    print("[farm] unlocking the Undead Giant farm quest (183, 176, 177)")

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
        print(f"[farm] {map_name} {cell}: levels {start}-{end}")
        await farm_until(
            cmd,
            lambda end=end: cmd.get_player().LEVEL >= min(end, level),
            map_name, cell=cell, pad=pad, monster="*", quests=quests)
        if cmd.get_player().LEVEL >= level and not rank_up_class:
            return

    current = cmd.get_player().LEVEL
    if 61 <= current < 75 and (current < level or rank_up_class):
        if rank_up_class:
            print("[farm] icestormarena r17: levels 61-75 (ranking the class)")
            await farm_until(cmd, lambda: cmd.get_player().LEVEL >= min(75, level),
                             "icestormarena", cell="r17", pad="Left",
                             monster="*")
        else:
            print("[farm] battlegrounde: levels 61-75")
            await farm_until(cmd, lambda: cmd.get_player().LEVEL >= min(75, level),
                             "battlegrounde", cell="r2", pad="center",
                             monster="*", quests=(3991, 3992))
        if cmd.get_player().LEVEL >= level and not rank_up_class:
            return

    if cmd.get_player().LEVEL < level or rank_up_class:
        print("[farm] icestormunder r2: levels 75-100")
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
    print(f"[farm] farming Good reputation to rank {rank}")

    if await cmd.is_completed_before(1955):
        await farm_until(cmd, _rep_done(cmd, "Good", rank), "poisonforest",
                         monster="Burning Loyalist", quests=(1952,))
        return

    print("[farm] the /PoisonForest story (quest 1955) is not complete: farming "
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
        print("[farm] quest 522 (Twisted Paw) cannot be accepted, so the "
              "/safiria story is not done. Nothing farmed.")
        return

    await equip_class(cmd, solo=True)
    print(f"[farm] farming Vampire reputation to rank {rank}")
    cmd.remove_drop("Old Moon")
    await farm_until(cmd, _rep_done(cmd, "Vampire", rank), "safiria",
                     monster="Twisted Paw", quests=(522,),
                     drops=["Twisted Paw's Head"])


async def yokai_rep(cmd: Command, rank: int = 10) -> None:
    """``CoreFarms.YokaiREP``: quest 383 in /dragonkoiz."""
    if cmd.get_faction_rank("Yokai") >= rank:
        return
    print(f"[farm] farming Yokai reputation to rank {rank}")
    await farm_until(cmd, _rep_done(cmd, "Yokai", rank), "dragonkoiz",
                     monster="Pockey Chew", quests=(383,),
                     drops=["Piece of Pockey"])


async def evil_rep(cmd: Command, rank: int = 10) -> None:
    """``CoreFarms.EvilREP``: quest 364 to rank 4, then 367 (366 for members)."""
    if cmd.get_faction_rank("Evil") >= rank:
        return

    await change_alignment(cmd, Alignment.EVIL)
    print(f"[farm] farming Evil reputation to rank {rank}")

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

    print(f"[farm] farming ChronoSpan reputation to rank {rank}")
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
    """The map monster whose definition id is ``mon_id``.

    Skua's ``Monster.ID`` is the monster's own id; ``MapID`` is the per-map one
    (``z_CompiledScript.cs`` compares against both).  This engine keeps them as
    ``mon_id`` and ``mon_map_id``.
    """
    for monster in cmd.bot.monsters:
        if str(monster.mon_id) == str(mon_id):
            return monster
    return None


async def craggle_rock_rep(cmd: Command, rank: int = 10) -> None:
    """``CoreFarms.CraggleRockREP``: quest 7277, chasing one monster id."""
    if cmd.get_faction_rank("CraggleRock") >= rank:
        return

    print(f"[farm] farming CraggleRock reputation to rank {rank}")
    cmd.add_drop("Empowered Voidstone")
    await cmd.register_quest(7277)
    await equip_class(cmd, solo=True)

    while (cmd.is_still_connected()
           and cmd.get_faction_rank("CraggleRock") < rank):
        monster = monster_by_definition_id(cmd, CRAGGLE_ROCK_ID)
        if monster is None:
            print(f"[farm] monster id {CRAGGLE_ROCK_ID} is not in /wanders, so "
                  f"CraggleRock cannot be farmed. Stopping.")
            cmd.cancel_registered_quests()
            return
        while cmd.is_still_connected() and cmd.is_not_in_cell(monster.frame):
            await cmd.jump_cell(monster.frame, "Left")
            await cmd.sleep(500)
        await cmd.use_next_skill(DEFAULT_SKILL_LIST,
                                f"id.{monster.mon_map_id}")

    cmd.cancel_registered_quests()


#: Faction name -> the ported method, mirroring ``CoreFarms.<Name>REP``.
FACTION_FARMS = {
    "Good": good_rep,
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
        print(f"[farm] {faction!r} reputation is not ported yet. Ported: "
              f"{', '.join(sorted(FACTION_FARMS))}.")
        return False
    await farm(cmd, rank)
    return True
