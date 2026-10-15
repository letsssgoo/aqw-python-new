"""Void Spartan -- the eleven rewards of quest 5982, or one of them.

Port of ``Nation/Various/VoidSpartan.cs``.

Set ``ITEM`` to one of the names below to farm just that one, or leave it
``None`` to work through all eleven.

Two notes on the reference's mechanics:
  * it loads quest 5982 with ``EnsureLoad``, which a client can do without
    accepting it; the live payload only carries the rewards once the quest is
    accepted, so this accepts first and reads them after.
  * with no item named it turns the quest in with ``EnsureCompleteChoose``.  That
    is a plain choice here, and it picks the first reward that is still missing,
    so the eleven actually fill up instead of looping on one.
"""
from core.command import Command
from bot.core_bots import buy_item
from bot.core_farms import farm_gold
from bot.nation.core_nation import (all_owned, farm_blood_gem,
                                    farm_gem_of_nulgath, farm_uni13_quest,
                                    first_missing)
from templates.hunt import hunt_item

#: Quest whose rewards this farms.
QUEST_ID = 5982

#: ``None`` for all eleven, or one of:
#: ``"Void Spartan"``, ``"Void Spartan Daggers"``, ``"Void Spartan Blade and
#: Shield"``, ``"Void Spartan Spear"``, ``"Void Spartan Blade"``, ``"Void Spartan
#: Banners"``, ``"Void Spartan Cape"``, ``"Void Spartan Shielded Cape"``,
#: ``"Void Spartan Spear and Shield"``, ``"Void Spartan Helm"``,
#: ``"Void Spartan Helm and Scarf"``.
ITEM = None

#: Shop and item the loop buys each pass.
CLOAK_SHOP_ID = 68
CLOAK = "Fiend Cloak of Nulgath"

#: Gold the reference farms each pass, and what it hands over with it.
GOLD = 500_000


async def main(cmd: Command):
    await cmd.ensure_accept_quest(QUEST_ID)      # accepts, so rewards load
    entries = cmd.get_quest_reward_entries(QUEST_ID)
    if not entries:
        print(f"[nation] quest {QUEST_ID} did not load; nothing farmed.")
        return

    cmd.add_drop([name for _, name, _ in entries]
                 + ["Zee's Red Jasper", CLOAK])

    if ITEM is None:
        targets = [(name, 1) for _, name, _ in entries]
        reward_id = None
    else:
        match = next(((item_id, name) for item_id, name, _ in entries
                      if name == ITEM), None)
        if match is None:
            names = ", ".join(name for _, name, _ in entries)
            print(f"[nation] {ITEM!r} is not one of quest {QUEST_ID}'s rewards "
                  f"({names}).")
            return
        targets = [(match[1], 1)]
        reward_id = match[0]

    while cmd.is_still_connected() and not await all_owned(cmd, targets):
        await cmd.ensure_accept_quest(QUEST_ID)
        await farm_uni13_quest(cmd, 1)
        await farm_blood_gem(cmd, 5)
        await farm_gem_of_nulgath(cmd, 10)
        # the reference writes quest slot 4055 here, which is client-side only
        await hunt_item(cmd, "Zee's Red Jasper", 1, "pyrewatch",
                        monster_name="Flame Soldier", is_temp=False)
        await cmd.jump_cell("Enter", "Spawn")
        await farm_gold(cmd, GOLD)
        await buy_item(cmd, CLOAK_SHOP_ID, CLOAK, map_name="tercessuinotlim")

        if reward_id is not None:
            await cmd.ensure_turn_in_quest(QUEST_ID, reward_id)
        else:
            chosen = await first_missing(
                cmd, [(i, n, 1) for i, n, _ in entries])
            await cmd.ensure_turn_in_quest(QUEST_ID,
                                           chosen[0] if chosen else -1)
