"""Enough DOOM for an Archfiend -- the ArchFiend DoomLord set (quest 5260).

Port of ``AFDL/EnoughDOOMforanArchfiend.cs``.  Its ``AFDL`` is also what
``0DoAll.cs`` calls, so it is a function here as well as a script body.

Note:
    The reference checks ownership with ``toInv: false`` -- its inventory only.
    The bank-aware check the rest of this port uses is used here instead.
"""
from core.command import Command
from bot.core_bots import buy_item
from bot.core_farms import battle_under_b, farm_experience
from bot.nation.afdl.nulgath_demands_work import ndw_quest
from bot.nation.core_nation import (BAG_DROPS, approval_and_favor,
                                    essence_of_nulgath, farm_blood_gem,
                                    farm_uni13_quest, farm_voucher,
                                    equip_class)
from templates.hunt import hunt_item

#: What the set is, and the quest that hands it over.
ITEM = "ArchFiend DoomLord"
QUEST_ID = 5260

#: The four items quest 5260's accept requirements need.
NDW_REQUIRED = ("DoomLord's War Mask", "ShadowFiend Cloak",
                "Locks of the DoomLord", "Doomblade of Destruction")

#: The set's own turn-in items, in the reference's order.
UNI_35 = "Unidentified 35"
UNDEAD_ESSENCE = ("Undead Essence", 1000)
CHAORRUPTION = ("Chaorruption Essence", 75, "orecavern",
                "Chaorrupted Good Soldier")
LIVING_STAR = ("Living Star Essence", 100, "starsinc", "Living Star")
KLUNK = ("Essence of Klunk", 1, "evilwardage", "Klunk")

#: The two shop runs before the last turn-in.
EMERALD = ("Aelita's Emerald", 16, "yulgar")
ESSENCE_POTION = ("Essence Potion", 2115, "alchemyacademy", 5)

#: Level the reference farms first.
LEVEL = 75

#: Everything the run picks up.
DROPS = list(BAG_DROPS) + [ITEM, "Undead Essence", "Chaorruption Essence",
                           "Essence Potion", "Essence of Klunk",
                           "Living Star Essence", "Bone Dust",
                           "Undead Energy", "Aelita's Emerald"] \
    + list(NDW_REQUIRED) + [UNI_35]


async def afdl(cmd: Command) -> None:
    """The whole set, in the reference's own order."""
    if await cmd.has_item(ITEM):
        cmd.bot.log(f'[afdl] "{ITEM}" is already owned; nothing to do.')
        return

    cmd.add_drop(DROPS)
    cmd.bot.log(f"[afdl] 1/10 levelling to {LEVEL}")
    await farm_experience(cmd, LEVEL)

    cmd.bot.log("[afdl] 2/10 farming an Unidentified 13")
    await farm_uni13_quest(cmd, 1)
    cmd.bot.log("[afdl] 3/10 Approval and Favor")
    await approval_and_favor(cmd, 0, 1)

    cmd.bot.log("[afdl] 4/10 " + ", ".join(NDW_REQUIRED))
    await ndw_quest(cmd, NDW_REQUIRED)

    cmd.bot.log(f"[afdl] 5/10 {UNI_35}")
    await ndw_quest(cmd, (UNI_35,))
    cmd.bot.log("[afdl] 6/10 Blood Gems x10")
    await farm_blood_gem(cmd, 10)
    cmd.bot.log("[afdl] 7/10 vouchers")
    await farm_voucher(cmd, False)
    cmd.bot.log("[afdl] 8/10 Essence of Nulgath x100")
    await essence_of_nulgath(cmd, 100)
    cmd.bot.log(f"[afdl] 9/10 {UNDEAD_ESSENCE[0]} x{UNDEAD_ESSENCE[1]}")
    await battle_under_b(cmd, UNDEAD_ESSENCE[0], UNDEAD_ESSENCE[1])

    cmd.bot.log(f"[afdl] 10/10 quest {QUEST_ID}: {CHAORRUPTION[0]} "
                f"x{CHAORRUPTION[1]} (/orecavern), {LIVING_STAR[0]} "
                f"x{LIVING_STAR[1]} (/starsinc), {EMERALD[0]}, "
                f"{ESSENCE_POTION[0]} x{ESSENCE_POTION[3]}, then {KLUNK[0]}")
    await cmd.ensure_accept_quest(QUEST_ID)
    await equip_class(cmd)
    await hunt_item(cmd, CHAORRUPTION[0], CHAORRUPTION[1], CHAORRUPTION[2],
                    monster_name=CHAORRUPTION[3], is_temp=False)
    await hunt_item(cmd, LIVING_STAR[0], LIVING_STAR[1], LIVING_STAR[2],
                    monster_name=LIVING_STAR[3], is_temp=False)

    if not await cmd.has_item(EMERALD[0]):
        await buy_item(cmd, EMERALD[1], EMERALD[0], map_name=EMERALD[2])
    await buy_item(cmd, ESSENCE_POTION[1], ESSENCE_POTION[0],
                   ESSENCE_POTION[3], map_name=ESSENCE_POTION[2])

    await approval_and_favor(cmd, 0, 5000)
    await equip_class(cmd, solo=True)
    await hunt_item(cmd, KLUNK[0], KLUNK[1], KLUNK[2], monster_name=KLUNK[3],
                    is_temp=False)
    await cmd.ensure_turn_in_quest(QUEST_ID)
    cmd.bot.log(f'[afdl] quest {QUEST_ID} turned in; "{ITEM}" is '
                f'{"in the inventory" if await cmd.has_item(ITEM) else "not in the inventory yet"}.')


async def main(cmd: Command):
    await afdl(cmd)
