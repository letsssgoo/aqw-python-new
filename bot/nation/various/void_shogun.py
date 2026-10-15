"""Void Shogun -- the twelve rewards of quest 6484, or one of them.

Port of ``Nation/Various/VoidShogun.cs``.

Set ``ITEM`` to one of the names below, or leave it ``None`` to work through them
all.  The Void Monk pet and Yokai reputation come first, exactly as the reference
orders it.

Note:
    The reference checks ownership with ``toInv: false`` -- its inventory only --
    and turns in with the reward's id.  The ownership check is the bank-aware one
    the rest of this port uses; the ids come from the quest's live payload.
"""
from core.command import Command
from bot.core_bots import buy_item
from bot.core_farms import yokai_rep
from bot.nation.core_nation import (equip_class, farm_blood_gem,
                                    farm_uni13_quest, farm_voucher,
                                    the_assistant)
from templates.hunt import hunt_item

#: Quest whose rewards this farms.
QUEST_ID = 6484

#: ``None`` for all twelve, or one of:
#: ``"Void Shogun"``, ``"Void Shogun Mask"``, ``"Void Shogun Helm"``,
#: ``"Void Shogun Masked Helm"``, ``"Void Shogun Banner"``, ``"Void Shogun
#: Runes"``, ``"Void Shogun Katana"``, ``"Void Shogun Naginata"``,
#: ``"Mini Void Shogun"``, ``"Mini Void Shogun Battlepet"``,
#: ``"Void Shogun Katanas on your Hip"``, ``"Dual Void Shogun Katanas"``.
ITEM = None

#: The pet quest 6484 needs, and the vouchers it costs.
MONK = "Void Monk of Nulgath"
MONK_MAP = "quibblehunt"
MONK_SHOP_ID = 1421
VOUCHER = "Void Voucher"
VOUCHER_QTY = 500

#: The three monster drops one turn-in needs, as ``(item, map, monster)``.
HUNTS = (
    ("Dai Tengu Blade of Wind", "hachiko", "Dai Tengu"),
    ("Orochi's Shadow", "shogunwar", "Orochi"),
    ("ShadowStone Rune", "necrocavern", "Shadowstone Support"),
)


async def main(cmd: Command):
    if ITEM is not None and await cmd.has_item(ITEM):
        return

    if not await cmd.has_item(MONK):
        cmd.add_drop(VOUCHER)
        await hunt_item(cmd, VOUCHER, VOUCHER_QTY, MONK_MAP, cell="r2",
                        pad="Left", monster_name="*", is_temp=False)
        await buy_item(cmd, MONK_SHOP_ID, MONK)

    await yokai_rep(cmd)
    await farm_voucher(cmd, False)

    await cmd.ensure_accept_quest(QUEST_ID)      # accepts, so rewards load
    entries = cmd.get_quest_reward_entries(QUEST_ID)
    if not entries:
        print(f"[nation] quest {QUEST_ID} did not load; nothing farmed.")
        return
    cmd.add_drop([name for _, name, _ in entries]
                 + [VOUCHER, "Dai Tengu Blade of Wind", "Orochi's Shadow"])

    targets = [(item_id, name) for item_id, name, _ in entries
               if ITEM is None or name == ITEM]
    if not targets:
        names = ", ".join(name for _, name, _ in entries)
        print(f"[nation] {ITEM!r} is not one of quest {QUEST_ID}'s rewards "
              f"({names}).")
        return

    for item_id, name in targets:
        if await cmd.has_item(name):
            print(f"[nation] {name} already held; next.")
            continue
        cmd.farming_logger(name, 1)
        while cmd.is_still_connected() and not await cmd.has_item(name):
            await cmd.ensure_accept_quest(QUEST_ID)
            await farm_uni13_quest(cmd, 1)
            await farm_blood_gem(cmd, 7)
            await the_assistant(cmd, "Unidentified 24")
            await equip_class(cmd, solo=True)
            for hunt, map_name, monster in HUNTS:
                await hunt_item(cmd, hunt, 1, map_name, monster_name=monster,
                                is_temp=False)
            await cmd.ensure_turn_in_quest(QUEST_ID, item_id)
