"""Assisting Oblivion Blade -- quest 5818, members only.

Port of ``Nation/Various/AssistingOblivionBlade.cs``.

Gated behind ``The Secret 2`` and the Tendurrr pet, then every reward quest 5818
offers is farmed to its own max stack -- one pass each of the Secret 4, essence,
approval, cubes, fiend seals and a BattleUnderB run.
"""
from core.command import Command
from bot.core_farms import battle_under_b, the_secret4
from bot.nation.core_nation import (all_owned, approval_and_favor,
                                    essence_of_nulgath)
from templates.hunt import hunt_item

#: Quest whose rewards this farms.
QUEST_ID = 5818

#: What the reference requires before it starts, and the pet it needs.
GATE_ITEM = "The Secret 2"
PET = "Tendurrr The Assistant"
PET_MAP = "tercessuinotlim"
PET_CELL = "m2"
PET_PAD = "Left"

#: The two kills one pass needs, as ``(item, qty, map, cell, pad)``.
KILLS = (
    ("Cubes", 50, "boxes", "Fort2", "Left"),
    ("Fiend Seal", 10, "shadowblast", "r13", "Left"),
)

#: What else one pass spends.
ESSENCE = 20
APPROVAL = 50
BATTLE_UNDER_B_QUANT = 200


async def main(cmd: Command):
    if not cmd.get_player().is_member or not await cmd.has_item(GATE_ITEM):
        cmd.bot.log(f"[nation] {GATE_ITEM} (and membership) is required for quest "
              f"{QUEST_ID}; nothing farmed.")
        return

    if not await cmd.has_item(PET):
        await hunt_item(cmd, PET, 1, PET_MAP, cell=PET_CELL, pad=PET_PAD,
                        monster_name="*", is_temp=False)

    await cmd.ensure_accept_quest(QUEST_ID)      # accepts, so rewards load
    entries = cmd.get_quest_reward_entries(QUEST_ID)
    if not entries:
        cmd.bot.log(f"[nation] quest {QUEST_ID} did not load; nothing farmed.")
        return
    cmd.add_drop([name for _, name, _ in entries])

    await cmd.register_quest(QUEST_ID)
    for item_id, name, stack in entries:
        if await cmd.has_item(name, stack):
            cmd.bot.log(f"[nation] {name} is at max stack; next reward.")
            continue
        cmd.farming_logger(name, stack)
        while cmd.is_still_connected() and not await cmd.has_item(name, stack):
            await the_secret4(cmd)
            await essence_of_nulgath(cmd, ESSENCE)
            await approval_and_favor(cmd, APPROVAL, APPROVAL)
            for item, qty, map_name, cell, pad in KILLS:
                await hunt_item(cmd, item, qty, map_name, cell=cell, pad=pad,
                                monster_name="*", is_temp=False)
            await battle_under_b(cmd, quant=BATTLE_UNDER_B_QUANT)

    cmd.cancel_registered_quests()
