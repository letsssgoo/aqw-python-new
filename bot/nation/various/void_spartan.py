"""Void Spartan -- ``Nation/Various/VoidSpartan.cs``.

``GetSpartan(item)`` repeats quest **5982** until the wanted reward (or the
whole set) is in hand.  One pass is:

* Uni 13 x1, Blood Gem x5, Gem of Nulgath x10;
* ``Zee's Red Jasper`` from ``/pyrewatch`` Flame Soldier (inventory, not temp);
* 500,000 gold and the ``Fiend Cloak of Nulgath`` from shop 68 in
  ``/tercessuinotlim``;
* turn in 5982 with the chosen reward.

The reference also writes ``Bot.Quests.UpdateQuest(4055)`` before hunting --
a client-side quest-slot write this engine has no packet for; the quest is
accepted instead and that difference is said out loud.
"""
from typing import Optional

from bot.core_bots import buy_item, quest_rewards
from bot.core_farms import farm_gold
from bot.nation.core_nation import (farm_blood_gem, farm_gem_of_nulgath,
                                    farm_uni13_quest)
from core.command import Command
from templates.hunt import hunt_item

QUEST = 5982
MAP = "pyrewatch"
MONSTER = "Flame Soldier"
DROP = "Zee's Red Jasper"
CLOAK_SHOP = 68
CLOAK_MAP = "tercessuinotlim"
CLOAK = "Fiend Cloak of Nulgath"
GOLD = 500_000


async def _reward_id(cmd: Command, name: str) -> int:
    loaded = cmd.get_loaded_quest(QUEST)
    if loaded is None:
        return 0
    for entry in getattr(loaded, "items", []) or []:
        if str(entry.get("sName") or "").strip().lower() == name.lower():
            return int(entry.get("ItemID") or 0)
    return 0


async def get_spartan(cmd: Command, item: Optional[str] = None) -> None:
    """``VoidSpartan.GetSpartan``."""
    rewards = quest_rewards(cmd, QUEST)
    target = item or ""
    cmd.add_drop([DROP, CLOAK, *rewards])
    cmd.bot.log(f"[spartan] farming {target or 'the Void Spartan set'}.")
    while cmd.is_still_connected():
        if target:
            if await cmd.has_item(target):
                return
        else:
            owned = True
            for reward in rewards:
                if not await cmd.has_item(reward):
                    owned = False
                    break
            if owned:
                return

        if not await cmd.ensure_accept_quest(QUEST):
            cmd.bot.log(f"[spartan] quest {QUEST} cannot be accepted.")
            return
        await farm_uni13_quest(cmd, 1)
        await farm_blood_gem(cmd, 5)
        await farm_gem_of_nulgath(cmd, 10)
        cmd.bot.log("[spartan] Bot.Quests.UpdateQuest(4055) has no packet "
                    "here; the quest is accepted instead.")
        await hunt_item(cmd, DROP, 1, MAP, monster_name=MONSTER,
                        is_temp=False)
        # ``Core.JumpWait()``: jump to the pane's own cell so the auto-aggro
        # cell is entered rather than spawn.
        await cmd.jump_cell(cmd.bot.player.CELL, cmd.bot.player.PAD)
        await farm_gold(cmd, GOLD)
        await buy_item(cmd, CLOAK_SHOP, CLOAK, 1, map_name=CLOAK_MAP)

        if target:
            reward_id = await _reward_id(cmd, target)
            if not await cmd.ensure_turn_in_quest(QUEST, item_id=reward_id):
                return
        elif not await cmd.ensure_turn_in_quest(QUEST):
            return


async def main(cmd: Command) -> None:
    """Standalone entry (``python -m bot.nation.various.void_spartan``)."""
    await get_spartan(cmd)
