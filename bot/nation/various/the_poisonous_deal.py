"""The Poisonous Deal -- quest 4776, for Tainted Gems and Dark Crystal Shards.

Port of ``Nation/Various/ThePoisonousDeal.cs``.

Needs the Crag pet, runs the Tainted Claymore chain first (the reference calls
that script's own ``DoAll``), then turns quest 4776 in once per reward -- id 4769
for the tainted gems and 4770 for the shards.

Note:
    Both quantities default to 0 in the reference, and 0 means "already done", so
    with the defaults this only prepares the prerequisites.
"""
from core.command import Command
from bot.nation.core_nation import (BAG_DROPS, CRAG_PET, dragon_slayer_reward,
                                    farm_blood_gem, farm_uni10, supplies)
from bot.nation.various import tainted_claymore

#: Quest and its two reward ids.
QUEST_ID = 4776
REWARD_IDS = {"Tainted Gem": 4769, "Dark Crystal Shard": 4770}

#: How many of each (the reference's own defaults).
TAINTED_QUANTITY = 0
SHARD_QUANTITY = 0

#: Bank the Nation drops when it finishes (the reference's ``BankItems``).
BANK_ITEMS = False

#: What one pass spends, in the reference's order.
PASS_SUPPLIES = "Unidentified 3"
BLOOD_GEMS = 2
UNI_10 = 30


async def main(cmd: Command):
    if not await cmd.has_item(CRAG_PET):
        print(f"[nation] {CRAG_PET} is missing; stopping.")
        return

    await dragon_slayer_reward(cmd)
    await tainted_claymore.main(cmd)

    cmd.add_drop(list(REWARD_IDS))
    for reward, quantity in (("Tainted Gem", TAINTED_QUANTITY),
                             ("Dark Crystal Shard", SHARD_QUANTITY)):
        cmd.farming_logger(reward, quantity)
        while cmd.is_still_connected() and not await cmd.has_item(reward,
                                                                  quantity):
            await cmd.ensure_accept_quest(QUEST_ID)
            await supplies(cmd, PASS_SUPPLIES)
            await farm_blood_gem(cmd, BLOOD_GEMS)
            await farm_uni10(cmd, UNI_10)
            await cmd.ensure_turn_in_quest(QUEST_ID, REWARD_IDS[reward])

    if BANK_ITEMS:
        await cmd.inv_to_bank(list(BAG_DROPS))
