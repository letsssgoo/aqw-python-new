"""Gold (The Game of Gemstones) -- quest 5815, members only.

Port of ``Nation/Various/TheGameofGemstones(Gold[Members]).cs``.

Five gemstones per turn-in, one of which (``Yoshino's Citrine``) comes out of the
Bludrut Brawl, so the brawl route runs with everything else.

Note:
    The reference writes quest slot 597 before registering 5815, which is
    client-side state this engine has no equivalent for; the quest is registered
    directly, which is what that write unlocks.
"""
from core.command import Command
from bot.core_farms import bludrut_brawl_boss
from bot.nation.core_nation import (approval_and_favor, farm_uni13_quest)
from templates.hunt import hunt_item

#: Gold to farm.
QUANT = 100_000_000

#: Quest whose turn-in pays the gold.
QUEST_ID = 5815

#: The pet quest 5815 needs.
PET = "Tendurrr The Assistant"
PET_MAP = "tercessuinotlim"
PET_CELL = "m2"
PET_PAD = "Left"

#: The four hunt steps, as ``(item, map, cell, pad, monster)`` -- the brawl step
#: sits between the second and the third.
HUNTS = (
    ("Archfiend's Amber", "Lavarun", None, "Left", "Mega Tyndarius"),
    ("Phantasmia's Charoite", "Catacombs", "Boss2", "Left", "Dr. De'Sawed"),
    ("Tendou's Moonstone", "Wolfwing", None, "Left", "Wolfwing"),
    # the reference hunts this one by its map id
    ("Asuka's Ruby", "baconcatyou", None, "Left", "id.1"),
)


async def main(cmd: Command):
    if not cmd.get_player().is_member:
        return

    await farm_uni13_quest(cmd, 1)
    if not await cmd.has_item(PET):
        await hunt_item(cmd, PET, 1, PET_MAP, cell=PET_CELL, pad=PET_PAD,
                        monster_name="*", is_temp=False)

    cmd.add_drop([item for item, *_ in HUNTS] + ["Yoshino's Citrine"])
    await cmd.register_quest(QUEST_ID)

    while cmd.is_still_connected() and cmd.get_player().GOLD < QUANT:
        await approval_and_favor(cmd, 1, 0)
        await hunt_item(cmd, HUNTS[0][0], 1, HUNTS[0][1], cell=HUNTS[0][2],
                        pad=HUNTS[0][3], monster_name=HUNTS[0][4],
                        is_temp=False)
        await hunt_item(cmd, HUNTS[1][0], 1, HUNTS[1][1], cell=HUNTS[1][2],
                        pad=HUNTS[1][3], monster_name=HUNTS[1][4],
                        is_temp=False)
        await bludrut_brawl_boss(cmd, "Yoshino's Citrine", 1)
        for item, map_name, cell, pad, monster in HUNTS[2:]:
            await hunt_item(cmd, item, 1, map_name, cell=cell, pad=pad,
                            monster_name=monster, is_temp=False)

    cmd.cancel_registered_quests()
