"""DragonSoul Shinobi -- quest 7924's token, then the class from /shadowfortress.

Port of ``Other/Classes/DragonShinobi.GetDSS``: the Yokai story, 300 Dragon
Shinobi Tokens off the Orochi heads, then the purchase and its rank-up.
"""
from bot.core_advanced import buy_item
from bot.core_advanced import rank_up_class as advance_class
from bot.core_bots import equip_class, kill_once
from bot.story.yokai import do_quests as yokai_quests
from core.command import Command

DRAGON_SHINOBI = "DragonSoul Shinobi"
#: ``Core.CheckInventory(59476)`` -- the class itself.
CLASS_ITEM = 59476
#: ``Core.AddDrop(20561)`` / ``HuntMonster("shadowfortress", "1st Head of Orochi")``.
TOKEN, TOKEN_ITEM = "Dragon Shinobi Token", 20561
TOKEN_QTY = 300
TOKEN_QUEST = 7924
MAP = "shadowfortress"
#: ``Adv.BuyItem("shadowfortress", 1968, 59476, shopItemID: 8078)``.
SHOP_ID = 1968
SHOP_ITEM_ID = 8078


async def get_dss(cmd: Command, rank_up_class: bool = True) -> None:
    """``DragonShinobi.GetDSS``.

    Args:
        cmd (Command): Facade to act through.
        rank_up_class (bool): Carry the class to rank 10 afterwards.
    """
    if await cmd.has_item_id(CLASS_ITEM):
        if rank_up_class:
            await advance_class(cmd, DRAGON_SHINOBI)
        return

    await yokai_quests(cmd)
    cmd.add_drop(TOKEN)

    await equip_class(cmd, solo=True)
    cmd.farming_logger(TOKEN, TOKEN_QTY)
    await cmd.register_quest(TOKEN_QUEST)

    guard = cmd.pass_guard(f'"{TOKEN}" x{TOKEN_QTY} (quest {TOKEN_QUEST})')
    while (cmd.is_still_connected()
           and not await cmd.has_item(TOKEN, TOKEN_QTY, isTemp=True)):
        await kill_once(cmd, MAP, monster="1st Head of Orochi")
        if not await guard.tick():
            cmd.bot.log(f"[shinobi] {TOKEN} stopped at "
                        f"{cmd.get_quant_item(TOKEN)}/{TOKEN_QTY}; nothing "
                        f"changed for too many passes.")
            break
    cmd.cancel_registered_quests()

    await buy_item(cmd, SHOP_ID, CLASS_ITEM, map_name=MAP,
                   shop_item_id=SHOP_ITEM_ID)

    if rank_up_class:
        await advance_class(cmd, DRAGON_SHINOBI)


async def main(cmd: Command):
    await get_dss(cmd)
