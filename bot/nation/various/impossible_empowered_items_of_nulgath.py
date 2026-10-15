"""Impossible Empowered Items of Nulgath -- quest 571 for the SoulReaper.

Port of ``Nation/Various/ImpossibleEmpoweredItemsofNulgath.cs``, which gathers a
step from several Nation routines (and the Leery Contract) and turns them into
one quest.

Members only.  The Tainted Gem step follows the reference's own choice: the Forge
route when the Gemstone of Nulgath is held, the ordinary farm otherwise.
"""
from core.command import Command
from bot.nation.core_nation import (dragon_slayer_reward,
                                    farm_dark_crystal_shard,
                                    farm_diamond_of_nulgath, farm_tainted_gem,
                                    farm_uni13_quest, forge_tainted_gems,
                                    GEMSTONE_OF_NULGATH)
from bot.nation.various.the_leery_contract import quest_items
from templates.hunt import hunt_item

#: Quest and its reward.
QUEST_ID = 571
ITEM = "SoulReaper of Nulgath"

#: What the Leery Contract step hands over.
LEERY_REWARD = "Godly Golden Dragon Axe"

#: The hunt quest 571 needs.
TERROR = "Abaddon's Terror"
TERROR_MONSTER = "Abaddon"
TERROR_MAP = "twilight"


async def main(cmd: Command):
    if await cmd.has_item(ITEM) or not cmd.get_player().is_member:
        return

    cmd.bot.log(f"[nation] gathering quest {QUEST_ID} for {ITEM}")
    await dragon_slayer_reward(cmd)
    await cmd.ensure_accept_quest(QUEST_ID)

    await farm_diamond_of_nulgath(cmd, 10)
    await farm_dark_crystal_shard(cmd, 5)
    if await cmd.has_item(GEMSTONE_OF_NULGATH) and cmd.get_player().is_member:
        await forge_tainted_gems(cmd, 5)
    else:
        await farm_tainted_gem(cmd, 5)
    await farm_uni13_quest(cmd, 1)
    await hunt_item(cmd, TERROR, 1, TERROR_MAP, monster_name=TERROR_MONSTER,
                    is_temp=False)
    await quest_items(cmd, LEERY_REWARD)

    await cmd.ensure_turn_in_quest(QUEST_ID)
