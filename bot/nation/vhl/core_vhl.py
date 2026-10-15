"""``CoreVHL`` -- the Void Highlord class, its challenge and its void crystals.

Port of ``Nation/VHL/CoreVHL.cs``: ``get_vhl`` is what ``0VoidHighlord`` runs,
and ``vhl_challenge`` / ``vhl_crystals`` are what the two single-purpose scripts
and the other Nation files call.

Where this engine cannot follow the reference, the gap is reported rather than
guessed at:

* ``Adv.RankUpClass`` is ``CoreAdvanced`` work, and it needs the class *rank*,
  which this engine cannot read.  ``bot/core_farms`` reports the same gap for its
  own ``rank_up_class`` argument, and the step is skipped the same way here.
* ``Daily.EldersBlood`` is ported (``bot/core_dailies``), but its daily gate is
  the server refusing the accept, not a client-side flag.
* ``farm_extra`` reads one reward name off quest 7551's payload, which this
  engine only has once the quest is accepted.  It accepts it first -- which
  ``swindle_return`` does in the same breath -- and reports if the reward is
  still not there.
"""
from typing import Optional

from bot.core_bots import buy_item, dynamic_quant, wait_for_item
from bot.core_dailies import elders_blood
from bot.core_farms import black_knight_orb, farm_experience
from bot.nation.core_nation import (BAG_DROPS, CRAG_PET, all_owned,
                                    approval_and_favor,
                                    assisting_crag_and_bamboozle,
                                    emblem_of_nulgath, essence_of_nulgath,
                                    farm_blood_gem, farm_dark_crystal_shard,
                                    farm_diamond_of_nulgath,
                                    farm_gem_of_nulgath, farm_tainted_gem,
                                    farm_totem_of_nulgath, farm_uni10,
                                    farm_uni13_quest, farm_voucher,
                                    swindle_return)
from core.command import Command
from templates.hunt import hunt_item

#: [Can Change] Reference default: use Assisting Crag & Bamboozle for one more
#: Elders' Blood a day.  Members only, and needs the Crag & Bamboozle pet.
#: ``CoreVHL``'s own option ("SparrowMethod"), which all three scripts expose.
USE_SPARROW_METHOD = True

#: ``GetVHL`` asks for level 80 before the challenge starts.
VHL_LEVEL = 80

ROENTGENIUM = "Roentgenium of Nulgath"
CHALLENGE_QUEST = 5660
CHALLENGE_REWARDS = ("Void Highlord Armor", "Helm of the Highlord",
                     "Highlord's Void Wrap")
CHALLENGE_SHADOW = ("Shadow of Nulgath", "Hadean Onyx of Nulgath")
CHALLENGE_CELL = "m4"
CHALLENGE_PAD = "Right"

VOID_HIGHLORD = "Void Highlord"
VOID_HIGHLORD_MAP = "tercessuinotlim"
VOID_HIGHLORD_SHOP = 1355

#: The one purchase the reference names by item id instead of by name.
CITADEL_MAP = "citadel"
CITADEL_SHOP = 44
CITADEL_ITEM_ID = 38316
CITADEL_SHOP_ITEM_ID = 22367

AELITA = "Aelita's Emerald"
AELITA_MAP = "yulgar"
AELITA_SHOP = 16

ELDERS_BLOOD = "Elders' Blood"
#: ``AssistingCragAndBamboozle.Rewards.Elders_Blood``.
SPARROW_ELDERS_BLOOD_ID = 5586

VOID_CRYSTAL_A = "Void Crystal A"
VOID_CRYSTAL_B = "Void Crystal B"

#: ``FarmExtra``'s own count: 17 for VHL, 8 for the crystals, 10 for the
#: Fiend Shard's final quest.
FARM_EXTRA_QUANT = 25
SWINDLE_QUEST = 7551
SWINDLE_REWARD_ID = 57446
UNIDENTIFIED_19 = "Unidentified 19"
UNIDENTIFIED_19_SHOP = 1951


async def get_vhl(cmd: Command, rank_up_class: bool = True) -> None:
    """``CoreVHL.GetVHL``: the class, challenge tokens and crystals included."""
    if await cmd.has_item(VOID_HIGHLORD):
        _rank_up(cmd, rank_up_class)
        return

    await vhl_challenge(cmd, 15)
    await vhl_crystals(cmd)

    if (await cmd.has_item(ROENTGENIUM, 15)
            and await all_owned(cmd, [(VOID_CRYSTAL_A, 1),
                                      (VOID_CRYSTAL_B, 1)])):
        await buy_item(cmd, VOID_HIGHLORD_SHOP, VOID_HIGHLORD,
                       map_name=VOID_HIGHLORD_MAP)
        _rank_up(cmd, rank_up_class)


def _rank_up(cmd: Command, rank_up_class: bool) -> None:
    """``Adv.RankUpClass``, which this engine cannot do (no class rank)."""
    if not rank_up_class:
        return
    print(f'[vhl] "{VOID_HIGHLORD}" would be ranked up here, but rank-up-class '
          f"work needs the class rank, which this engine cannot read; "
          f"skipping it. The class itself is unaffected.")


async def vhl_challenge(cmd: Command, quant: int, farmextra: bool = False) -> None:
    """``CoreVHL.VHLChallenge``: ``quant`` Roentgenium of Nulgath tokens.

    The reference loops until it holds ``quant`` of them, one per turn-in of
    quest 5660, and stops when the Elders' Blood supply runs out -- that daily is
    the throttle.  Its ``goto Continue`` lands on the loop's own first statement,
    so a plain ``continue`` is the same jump.
    """
    if await cmd.has_item(ROENTGENIUM, quant):
        return

    print("[vhl] Getting Void HighLord Challenge prerequisites")
    await farm_experience(cmd, VHL_LEVEL)
    cmd.add_drop(BAG_DROPS)
    if not await all_owned(cmd, [(reward, 1) for reward in CHALLENGE_REWARDS]):
        cmd.add_drop(list(CHALLENGE_REWARDS))
    cmd.add_drop(ROENTGENIUM)

    cmd.farming_logger(ROENTGENIUM, quant)
    while cmd.is_still_connected() and not await cmd.has_item(ROENTGENIUM, quant):
        if not await cmd.ensure_accept_quest(CHALLENGE_QUEST):
            print(f"[vhl] quest {CHALLENGE_QUEST} cannot be accepted, so no "
                  f"{ROENTGENIUM} can be made. Stopping.")
            return
        await hunt_item(cmd, CHALLENGE_SHADOW[1], 1, VOID_HIGHLORD_MAP,
                        cell=CHALLENGE_CELL, pad=CHALLENGE_PAD,
                        monster_name=CHALLENGE_SHADOW[0], is_temp=False)

        # how many more Elders' Blood this run still needs, capped at 5
        needed = min(5, quant - dynamic_quant(cmd, ELDERS_BLOOD))
        if not await cmd.has_item(ELDERS_BLOOD, needed):
            await elders_blood(cmd)
            await _sparrow_method(
                cmd, min(5, quant - dynamic_quant(cmd, ELDERS_BLOOD)))

        await farm_voucher(cmd, False)
        await black_knight_orb(cmd)
        await buy_item(cmd, CITADEL_SHOP, CITADEL_ITEM_ID, map_name=CITADEL_MAP,
                       shop_item_id=CITADEL_SHOP_ITEM_ID)
        if not await cmd.has_item(AELITA):
            await buy_item(cmd, AELITA_SHOP, AELITA, map_name=AELITA_MAP)
        await farm_uni13_quest(cmd, 1)
        await farm_gem_of_nulgath(cmd, 20)
        await emblem_of_nulgath(cmd, 20)
        await essence_of_nulgath(cmd, 50)
        await farm_tainted_gem(cmd, 100)
        await approval_and_favor(cmd, 300, 300)

        await cmd.ensure_turn_in_quest(CHALLENGE_QUEST)
        await wait_for_item(cmd, ROENTGENIUM)
        await cmd.inv_to_bank(list(CHALLENGE_REWARDS))

        if (await cmd.has_item(ELDERS_BLOOD)
                and not await cmd.has_item(ROENTGENIUM, quant)):
            continue
        if (not await cmd.has_item(ELDERS_BLOOD)
                and not await cmd.has_item(ROENTGENIUM, quant)):
            left = 2 - dynamic_quant(cmd, ELDERS_BLOOD)
            print(f'[vhl] Not enough "{ELDERS_BLOOD}", please do the daily '
                  f"{left} more times (not today)")
            if farmextra:
                await farm_extra(cmd)
            return


async def vhl_crystals(cmd: Command) -> None:
    """``CoreVHL.VHLCrystals``: Void Crystal A and B, from /tercessuinotlim.

    Void Crystal B is gated on two Elders' Blood as well, and when they are not
    there the reference banks the materials and waits for the next reset rather
    than buying -- that branch is kept.
    """
    if (await cmd.has_item(VOID_CRYSTAL_A)
            and await cmd.has_item(VOID_CRYSTAL_B)):
        return

    cmd.add_drop(BAG_DROPS)
    await farm_uni13_quest(cmd, 1)

    if not await cmd.has_item(VOID_CRYSTAL_A):
        print("[vhl] Obtaining Void Crystal A ")
        await farm_uni10(cmd, 200)
        await farm_tainted_gem(cmd, 200)
        await farm_dark_crystal_shard(cmd, 200)
        await farm_gem_of_nulgath(cmd, 150)
        await buy_item(cmd, VOID_HIGHLORD_SHOP, VOID_CRYSTAL_A,
                       map_name=VOID_HIGHLORD_MAP)

    if not await cmd.has_item(VOID_CRYSTAL_B):
        print("[vhl] Obtaining Void Crystal B")
        if not await cmd.has_item(ELDERS_BLOOD, 2):
            await elders_blood(cmd)
        await _sparrow_method(cmd, 2)

        if not await cmd.has_item(ELDERS_BLOOD, 2):
            print(f'[vhl] Not enough "{ELDERS_BLOOD}", please do the daily '
                  f"{2 - dynamic_quant(cmd, ELDERS_BLOOD)} more times "
                  f"(not today)")
            print("[vhl] Gathering Materials for Void Crystal B")
            await farm_totem_of_nulgath(cmd, 15)
            await farm_diamond_of_nulgath(cmd, 200)
            await farm_blood_gem(cmd, 30)
            print("[vhl] Mats are all preped for Void Crystal B")
        else:
            await farm_totem_of_nulgath(cmd, 15)
            await farm_diamond_of_nulgath(cmd, 200)
            await farm_blood_gem(cmd, 30)
            await buy_item(cmd, VOID_HIGHLORD_SHOP, VOID_CRYSTAL_B,
                           map_name=VOID_HIGHLORD_MAP)


async def farm_extra(cmd: Command, quant: int = FARM_EXTRA_QUANT) -> None:
    """``CoreVHL.FarmExtra``: max the materials out for tomorrow's run.

    Only reached from ``vhl_challenge(..., farmextra=True)``, which no script in
    the reference passes; it is here because the core has it.
    """
    if await cmd.has_item(ROENTGENIUM, quant):
        return

    print(f"[vhl] {ROENTGENIUM}: {dynamic_quant(cmd, ROENTGENIUM)}/{quant} "
          f"Not Enough Roent")
    print("[vhl] Not enough \"Roentgenium of Nulgath\", maxing mats so it's "
          "easier tomorrow. You can just leave this running!")

    await black_knight_orb(cmd)
    await buy_item(cmd, CITADEL_SHOP, CITADEL_ITEM_ID, map_name=CITADEL_MAP,
                   shop_item_id=CITADEL_SHOP_ITEM_ID)
    if not await cmd.has_item(AELITA):
        await buy_item(cmd, AELITA_SHOP, AELITA, map_name=AELITA_MAP)
    await farm_uni13_quest(cmd, 13)
    await farm_gem_of_nulgath(cmd, 1000)
    await emblem_of_nulgath(cmd, 500)
    await essence_of_nulgath(cmd, 60)
    await farm_tainted_gem(cmd, 1000)
    await approval_and_favor(cmd, 5000, 5000)
    await farm_blood_gem(cmd)

    if not await cmd.has_item(UNIDENTIFIED_19):
        reward = await _swindle_reward_name(cmd)
        if reward is None:
            print(f"[vhl] quest {SWINDLE_QUEST}'s reward with item id "
                  f"{SWINDLE_REWARD_ID} could not be read, so {UNIDENTIFIED_19!r} "
                  f"was not swapped for or bought.")
        else:
            await swindle_return(cmd, reward, 6)
            await buy_item(cmd, UNIDENTIFIED_19_SHOP, UNIDENTIFIED_19,
                           map_name=VOID_HIGHLORD_MAP)

    await farm_totem_of_nulgath(cmd, 15)
    await farm_voucher(cmd, False)
    await farm_voucher(cmd, True)
    print("[vhl] Materials max out! You should be good for tomorrow.")


async def _sparrow_method(cmd: Command, elders_blood_quant: int) -> None:
    """``CoreVHL._SparrowMethod``: the Crag & Bamboozle pass for one more Blood."""
    if (not USE_SPARROW_METHOD
            or not cmd.get_player().is_member
            or not await cmd.has_item(CRAG_PET)
            or await cmd.has_item(ELDERS_BLOOD, elders_blood_quant)):
        return
    await assisting_crag_and_bamboozle(cmd, SPARROW_ELDERS_BLOOD_ID)


async def _swindle_reward_name(cmd: Command) -> Optional[str]:
    """The name of quest 7551's reward ``SWINDLE_REWARD_ID``, or None.

    The reference reads this off its client-side quest cache before accepting
    anything.  This engine only receives a quest's payload once it is accepted
    (the ``acceptQuest`` reply is what asks for the ``getQuests`` payload), so the
    quest is accepted first -- which ``swindle_return`` does anyway -- and the
    reward is read from there.
    """
    await cmd.ensure_accept_quest(SWINDLE_QUEST)
    if cmd.get_loaded_quest(SWINDLE_QUEST) is None:
        return None
    for entry in cmd.get_quest_reward_entries(SWINDLE_QUEST):
        if str(entry[0]) == str(SWINDLE_REWARD_ID):
            return entry[1]
    return None
