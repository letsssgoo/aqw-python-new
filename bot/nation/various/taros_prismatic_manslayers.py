"""Taro's Prismatic Manslayers -- quest 8496 (A Test of Temptation).

Port of ``Nation/Various/TarosPrismaticManslayers.cs``.

Members only, level 80 and Good reputation first, and it needs Taro's Manslayer
in hand -- which is why the reference includes that script and calls it.

Note:
    The reference walks its reward list *reversed*, "so the battlepet is last",
    and skips the ones already held with an inventory-only check.  The order is
    kept; the ownership check is the bank-aware one the rest of this port uses.
"""
from core.command import Command
from bot.core_farms import farm_experience, farm_faction
from bot.nation.core_nation import (all_owned, farm_blood_gem,
                                    farm_dark_crystal_shard,
                                    farm_diamond_of_nulgath,
                                    farm_gem_of_nulgath, farm_tainted_gem)
from bot.nation.various.taros_manslayer import MAN_SLAYER
from bot.nation.various import taros_manslayer

#: Quest whose rewards this farms.
QUEST_ID = 8496

#: Level and reputation the reference asks for before the quest.
LEVEL = 80

#: What the five material steps need, in the reference's order.
MATERIALS = (
    ("Tainted Gem", 200),
    ("Dark Crystal Shard", 125),
    ("Diamond of Nulgath", 300),
    ("Gem of Nulgath", 75),
    ("Blood Gem of the Archfiend", 35),
)

_FARMS = {
    "Tainted Gem": farm_tainted_gem,
    "Dark Crystal Shard": farm_dark_crystal_shard,
    "Diamond of Nulgath": farm_diamond_of_nulgath,
    "Gem of Nulgath": farm_gem_of_nulgath,
    "Blood Gem of the Archfiend": farm_blood_gem,
}


async def main(cmd: Command):
    if not cmd.get_player().is_member:
        cmd.bot.log("[nation] quest 8496 is members only; nothing farmed.")
        return

    await cmd.ensure_accept_quest(QUEST_ID)      # accepts, so rewards load
    entries = cmd.get_quest_reward_entries(QUEST_ID)
    if not entries:
        cmd.bot.log(f"[nation] quest {QUEST_ID} (A Test of Temptation) did not load; "
              f"nothing farmed.")
        return

    if await all_owned(cmd, [(name, 1) for _, name, _ in entries]):
        cmd.bot.log("[nation] every quest 8496 reward is already held.")
        return
    cmd.add_drop([name for _, name, _ in entries])

    await farm_experience(cmd, LEVEL)
    await farm_faction(cmd, "Good")

    if not await cmd.has_item(MAN_SLAYER):
        await taros_manslayer.main(cmd)

    # reversed, so the battlepet is turned in for last
    for item_id, name, _ in reversed(entries):
        if await cmd.has_item(name):
            cmd.bot.log(f"[nation] {name} already held; next.")
            continue
        cmd.farming_logger(name, 1)
        await cmd.ensure_accept_quest(QUEST_ID)
        for material, qty in MATERIALS:
            await _FARMS[material](cmd, qty)
        await cmd.ensure_turn_in_quest(QUEST_ID, item_id)
