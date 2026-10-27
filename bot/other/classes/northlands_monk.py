"""Northlands Monk -- the Frostvale class from /frozensoul.

Port of ``Seasonal/Frostvale/NorthlandsMonk.GetNlMonk``.  It is a seasonal class:
the map only exists during Frostvale, so the reference bails out when
``isSeasonalMapActive("frozensoul")`` is false.  This engine has no client to ask,
so "seasonal" is decided by trying to enter the map -- if the character never
arrives, the class is reported unavailable and the run moves on, which is what
the reference does with its check.
"""
from bot.core_advanced import rank_up_class as advance_class
from bot.core_bots import equip_class
from bot.script_log import ScriptLog
from core.command import Command
from templates.hunt import hunt_item

TAG = "Northlands Monk"
MONK = "Northlands Monk"
MONK_ITEM = 52413
MAP = "frozensoul"
CELL, PAD = "r4", "Left"
MONSTER = "Frozensoul Queen"


async def get_nl_monk(cmd: Command, rank_up_class: bool = True) -> bool:
    """``NorthlandsMonk.GetNlMonk``.

    Args:
        cmd: Facade to act through.
        rank_up_class (bool): Carry the class to rank 10 afterwards.

    Returns:
        bool: True when the class is owned at the end.
    """
    log = ScriptLog(cmd, TAG)

    if await cmd.has_item_id(MONK_ITEM):
        if rank_up_class:
            await advance_class(cmd, MONK)
        return True

    # ``isSeasonalMapActive``: a join that does not land means the map is not
    # available right now (out of season), so the class is skipped.
    await cmd.join_map(MAP)
    await cmd.sleep(1000)
    if cmd.is_not_in_map(MAP):
        log.warning(f"/{MAP} is not available (out of season); {MONK} skipped.")
        return False

    cmd.add_drop([str(MONK_ITEM)])
    await equip_class(cmd, solo=True)
    await hunt_item(cmd, MONK, 1, MAP, cell=CELL, pad=PAD,
                    monster_name=MONSTER, is_temp=False)

    if rank_up_class and await cmd.has_item(MONK):
        await advance_class(cmd, MONK)
    return await cmd.has_item(MONK)


async def main(cmd: Command):
    await get_nl_monk(cmd)


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
