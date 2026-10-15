"""Nulgath Demands Work -- quest 5259, for its four NDW items and Uni 35.

Port of ``AFDL/NulgathDemandsWork.cs``.  Its ``NDWQuest`` is also what
``EnoughDOOMforanArchfiend`` calls for the four accept requirements, so it is a
function here rather than only a script body.

Note:
    For ``Unidentified 35`` the reference buys with ``Archfiend Essence
    Fragment`` (nine per one) *before* turning the quest in, and only when its
    own ``CanCompleteFullCheck`` says the quest is ready; ``can_turnin_quest`` is
    the same test here.
"""
from typing import Optional, Sequence

from core.command import Command
from bot.core_bots import buy_item
from bot.nation.afdl.willpower_extraction import unidentified_34
from bot.nation.core_nation import (all_owned, dark_makai_item,
                                    farm_blood_gem, farm_gem_of_nulgath,
                                    farm_uni13_quest, farm_voucher,
                                    first_missing, supplies)
from bot.nation.various.golden_hanzo_void import main as ghv
from templates.hunt import hunt_item

#: Quest and the four items its accept requirements need.
QUEST_ID = 5259
NDW_ITEMS = ("DoomLord's War Mask", "ShadowFiend Cloak",
             "Locks of the DoomLord", "Doomblade of Destruction")

#: The two items the quest also pays out, and what one Uni 35 costs in fragments.
UNI_35 = "Unidentified 35"
FRAGMENT = "Archfiend Essence Fragment"
FRAGMENTS_PER_UNI_35 = 9

#: Where Uni 35 is bought with those fragments.
SHOP_ID = 1951
SHOP_MAP = "tercessuinotlim"

#: Uni 35's own farm quantity, and the Uni 27 quest's steps.
UNI_35_QUANT = 300
UNI_27 = "Unidentified 27"
UNI_27_QUEST = 584
UNI_27_SUPPLY = ("Unidentified 26", 1)


async def ndw_quest(cmd: Command, item_names: Optional[Sequence[str]] = None,
                    quant: int = 1) -> None:
    """Complete quest 5259 until ``item_names`` are held."""
    names = tuple(item_names) if item_names else NDW_ITEMS
    if not names or await all_owned(cmd, [(name, quant) for name in names]):
        return

    await cmd.ensure_accept_quest(QUEST_ID)      # accepts, so rewards load
    entries = cmd.get_quest_reward_entries(QUEST_ID)
    if not entries:
        print(f"[nation] quest {QUEST_ID} did not load; nothing farmed.")
        return
    cmd.add_drop([name for _, name, _ in entries])

    for name in names:
        entry = next((e for e in entries if e[1] == name), None)
        if entry is None:
            print(f"[nation] {name!r} is not one of quest {QUEST_ID}'s "
                  f"rewards; skipping it.")
            continue
        item_id = entry[0]
        if await cmd.has_item(name, quant):
            print(f"[nation] {name} x{quant} owned; next.")
            continue
        cmd.farming_logger(name, quant)

        while cmd.is_still_connected() and not await cmd.has_item(name, quant):
            await cmd.ensure_accept_quest(QUEST_ID)

            await unidentified_34(cmd, 10)
            # one for the accept, one for the quest
            await farm_uni13_quest(cmd, 2)
            await uni_27(cmd)
            await farm_voucher(cmd, True)
            await farm_gem_of_nulgath(cmd, 15)
            await farm_blood_gem(cmd, 2)
            await ghv(cmd)

            if name == UNI_35:
                to_buy = min(quant - cmd.get_quant_item(UNI_35),
                             cmd.get_quant_item(FRAGMENT) // FRAGMENTS_PER_UNI_35)
                if to_buy > 0:
                    await buy_item(cmd, SHOP_ID, UNI_35, to_buy, map_name=SHOP_MAP)
                    if await cmd.has_item(UNI_35, quant):
                        print(f"[nation] {UNI_35} x{quant} reached by buying with "
                              f"fragments; next.")
                        break
                if cmd.can_turnin_quest(QUEST_ID):
                    await cmd.ensure_turn_in_quest(QUEST_ID, item_id)
            else:
                # pick the first NDW reward that is not at its max stack yet
                chosen = await first_missing(
                    cmd, [(i, n, s) for i, n, s in entries if n in NDW_ITEMS])
                if chosen is not None:
                    await cmd.ensure_turn_in_quest(QUEST_ID, chosen[0])
                else:
                    print("[nation] every NDW item is at max stack; turning the "
                          "quest in without picking one.")
                    await cmd.ensure_turn_in_quest(QUEST_ID)


async def uni_27(cmd: Command) -> None:
    """The reference's ``Uni27``: quest 584, for Unidentified 27."""
    if await cmd.has_item(UNI_27):
        return

    cmd.add_drop(UNI_27)
    await supplies(cmd, UNI_27_SUPPLY[0], UNI_27_SUPPLY[1])
    await cmd.ensure_accept_quest(UNI_27_QUEST)
    # the reference calls ResetQuest(7551) here, which sends no packet of its own
    await cmd.ensure_accept_quest(7551)
    await dark_makai_item(cmd, "Dark Makai Sigil")
    await cmd.ensure_turn_in_quest(UNI_27_QUEST)


async def main(cmd: Command):
    await ndw_quest(cmd, NDW_ITEMS)
    await ndw_quest(cmd, (UNI_35,), UNI_35_QUANT)
