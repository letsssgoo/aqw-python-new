"""Shaman -- class 5765 from /arcangrove 214, then rank 10.

Port of ``Other/Classes/REP-based/Shaman.GetShaman``.  The whole script is the
purchase: the reputation gate lives on the shop entry, which
:func:`bot.core_advanced.buy_item` farms through ``GetItemReq``.
"""
from bot.core_advanced import buy_item
from bot.core_advanced import rank_up_class as advance_class
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Shaman"
SHAMAN = "Shaman"
SHOP_MAP = "arcangrove"
SHOP_ID = 214
SHAMAN_ITEM = 5765
SHOP_ITEM_ID = 4799


async def get_shaman(cmd: Command, rank_up_class: bool = True) -> None:
    """``Shaman.GetShaman``.

    Args:
        cmd (Command): Facade to act through.
        rank_up_class (bool): Carry the class to rank 10 afterwards.
    """
    log = ScriptLog(cmd, TAG)
    if await cmd.has_item(SHAMAN):
        if rank_up_class:
            await advance_class(cmd, SHAMAN)
        return

    log.info(f"Buying {SHAMAN} from /{SHOP_MAP} {SHOP_ID}...")
    await buy_item(cmd, SHOP_ID, SHAMAN_ITEM, map_name=SHOP_MAP,
                   shop_item_id=SHOP_ITEM_ID)
    if await cmd.has_item(SHAMAN):
        log.success(f"{SHAMAN} bought.")
    else:
        log.warning(f"{SHAMAN} was not bought; the shop entry needs Arcangrove "
                    f"rank 10.")

    if rank_up_class:
        await advance_class(cmd, SHAMAN)


async def main(cmd: Command):
    await get_shaman(cmd)


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
