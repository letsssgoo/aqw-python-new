"""Vim -- quest 8824, the first helm special.

Port of ``Enhancement/UnlockForgeEnhancements.Vim``: the forge helm unlock, rank
7 Blacksmithing, then Rogue ranked up and 250 Ethereal Essence.

``UseGold`` is the reference's reputation option (default ``False``) and
``SellQuestClass`` its "sell the class back" option (default ``False``); both are
parameters here, as the source reads them from its config.
"""
from bot.core_advanced import buy_item, gear_store, rank_up_class
from bot.core_bots import equip_class
from bot.core_farms import blacksmithing_rep
from bot.enhancements.forge_helm import forge_helm_enhancement
from core.command import Command
from templates.hunt import hunt_item

USE_GOLD = False
#: ``SellQuestClass``: sell the class back once the quest is done.
SELL_QUEST_CLASS = False

VIM_QUEST = 8824
ESSENCE = "Ethereal Essence"
ESSENCE_MAP = "Towerofdoom10"
ESSENCE_CELL, ESSENCE_PAD = "r8", "Left"


async def rank_class_and_farm_essence(cmd: Command, shop_id: int,
                                      class_name: str,
                                      essence_qty: int) -> None:
    """The tail every helm quest shares: rank the class, then the essence.

    ``Vim``/``Examen``/``Anima``/``Pneuma`` differ only in which class they rank
    and how much essence they need, so the steps are here once, in the source's
    order: save the gear, buy and rank the class, put the gear back, then farm.

    Args:
        cmd (Command): Facade to act through.
        shop_id (int): Classhalla shop the class is bought from.
        class_name (str): Class to buy and rank to 10.
        essence_qty (int): How much Ethereal Essence this quest wants.
    """
    await gear_store(cmd)
    await buy_item(cmd, shop_id, class_name, map_name="Classhalla")
    await rank_up_class(cmd, class_name)
    await gear_store(cmd, restore=True, enh_after=True)

    await equip_class(cmd)
    await hunt_item(cmd, ESSENCE, essence_qty, ESSENCE_MAP,
                    cell=ESSENCE_CELL, pad=ESSENCE_PAD, monster_name="*",
                    is_temp=False)


async def vim(cmd: Command, use_gold: bool = USE_GOLD,
              sell_quest_class: bool = SELL_QUEST_CLASS) -> None:
    """``UnlockForgeEnhancements.Vim``.

    Args:
        cmd (Command): Facade to act through.
        use_gold (bool): The reference's ``UseGold``, passed to both of the
            reputation farm's own flags.
        sell_quest_class (bool): The reference's ``SellQuestClass``.
    """
    if await cmd.is_completed_before(VIM_QUEST):
        return

    await forge_helm_enhancement(cmd, use_gold)
    cmd.bot.log("Unlocking Enhancement: Vim")

    await blacksmithing_rep(cmd, 7, use_gold, use_gold)
    await cmd.ensure_accept_quest(VIM_QUEST)

    await rank_class_and_farm_essence(cmd, 172, "Rogue", 250)

    await cmd.ensure_turn_in_quest(VIM_QUEST)
    if sell_quest_class:
        await cmd.sell_item("Rogue")
    cmd.bot.log("Enhancement Unlocked: Vim")


async def main(cmd: Command):
    await vim(cmd)
