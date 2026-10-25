"""Burning Blade -- item 31058, a drop in /lostruinswar.

Port of ``Other/Weapons/BurningBlade.GetBurningBlade``: one kill on the
Diabolical Warlord at ``r7/Left``.

Note:
    The reference passes ``publicRoom: true``.  This engine has no private-room
    mode -- ``join_map`` only pins a room number when it is given one, which these
    hunts never do -- so the normal join is already the public one.
"""
from bot.core_bots import equip_class, wait_for_item
from core.command import Command
from templates.hunt import hunt_item

BURNING_BLADE = "Burning Blade"
BURNING_BLADE_ITEM = 31058
DROP_MAP = "lostruinswar"
DROP_CELL, DROP_PAD = "r7", "Left"
DROP_MONSTER = "Diabolical Warlord"


async def get_burning_blade(cmd: Command) -> None:
    """``BurningBlade.GetBurningBlade``: farm the drop, then wait for pickup."""
    if await cmd.has_item_id(BURNING_BLADE_ITEM):
        return

    await equip_class(cmd, solo=True)
    await hunt_item(cmd, BURNING_BLADE, 1, DROP_MAP, cell=DROP_CELL,
                    pad=DROP_PAD, monster_name=DROP_MONSTER, is_temp=False)
    await wait_for_item(cmd, BURNING_BLADE)


async def main(cmd: Command):
    await get_burning_blade(cmd)
