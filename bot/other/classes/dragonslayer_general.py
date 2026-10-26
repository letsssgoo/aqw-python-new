"""Dragonslayer General -- item 35996 from the /dragontown shop 1286.

Port of ``Other/Classes/DragonslayerGeneral.GetDSGeneral``: the /lair chain
(quests 165-168), the Dragonslayer class if it is missing or below rank 10, then
75 Enchanted Scale and 100 Dragon Claw for the purchase.
"""
from bot.core_advanced import buy_item, gear_store
from bot.core_advanced import rank_up_class as advance_class
from bot.core_bots import check_class_rank, equip_class
from bot.core_farms import farm_gold
from bot.core_story import kill_quest
from core.command import Command
from templates.hunt import hunt_item

DS_GENERAL_NAME = "Dragonslayer General"
#: ``Adv.BuyItem("dragontown", 1286, 35996, shopItemID: 3937)``.
DS_GENERAL_MAP = "dragontown"
DS_GENERAL_SHOP = 1286
DS_GENERAL_ITEM = 35996
DS_GENERAL_SHOP_ITEM_ID = 3937

#: ``Core.CheckInventory(582)`` -- the Dragonslayer class, bought in /lair.
DRAGONSLAYER_ITEM = 582
DRAGONSLAYER_MAP = "lair"
DRAGONSLAYER_SHOP = 38
DRAGONSLAYER_NAME = "Dragonslayer"

SCALE, CLAW = "Enchanted Scale", "Dragon Claw"
SCALE_QUEST = 5294
SCALE_QTY, CLAW_QTY = 75, 100
DROP_MAP = "dragontown"
DROP_CELL, DROP_PAD = "r4", "Right"
DROP_MONSTER = "Tempest Dracolich"

#: ``LairStory``: (quest, monster) in the source's order.
LAIR_CHAIN = ((165, "Wyvern"), (166, "Bronze Draconian"),
              (167, "Dark Draconian"), (168, "Red Dragon"))


async def lair_story(cmd: Command) -> None:
    """``LairStory``: the four /lair quests the drops need unlocked."""
    for quest_id, monster in LAIR_CHAIN:
        await kill_quest(cmd, quest_id, DRAGONSLAYER_MAP, monster)


async def enchanted_scale_and_claw(cmd: Command, scale_qty: int = SCALE_QTY,
                                   claw_qty: int = CLAW_QTY) -> None:
    """``EnchantedScaleandClaw``: Dragonslayer ranked, then the two drops.

    Args:
        cmd (Command): Facade to act through.
        scale_qty (int): Enchanted Scale wanted; zero skips its quest.
        claw_qty (int): Dragon Claw wanted.
    """
    await lair_story(cmd)

    await gear_store(cmd)
    if not await cmd.has_item_id(DRAGONSLAYER_ITEM) \
            and check_class_rank(cmd, DRAGONSLAYER_NAME) < 10:
        await buy_item(cmd, DRAGONSLAYER_SHOP, DRAGONSLAYER_NAME,
                       map_name=DRAGONSLAYER_MAP)
        await advance_class(cmd, DRAGONSLAYER_NAME)
    await gear_store(cmd, restore=True, enh_after=True)

    if scale_qty <= 0 and claw_qty <= 0:
        return

    cmd.add_drop([SCALE, CLAW])
    cmd.bot.log(f"Farming {scale_qty} Scale / {claw_qty} Claw")
    if scale_qty > 0:
        await cmd.register_quest(SCALE_QUEST)

    await equip_class(cmd)
    await hunt_item(cmd, SCALE, scale_qty, DROP_MAP, cell=DROP_CELL,
                    pad=DROP_PAD, monster_name=DROP_MONSTER, is_temp=False)
    await hunt_item(cmd, CLAW, claw_qty, DROP_MAP, cell=DROP_CELL,
                    pad=DROP_PAD, monster_name=DROP_MONSTER, is_temp=False)
    cmd.cancel_registered_quests()


async def get_ds_general(cmd: Command, rank_up_class: bool = True) -> None:
    """``DragonslayerGeneral.GetDSGeneral``.

    Args:
        cmd (Command): Facade to act through.
        rank_up_class (bool): Carry the class to rank 10 after buying it.
    """
    await gear_store(cmd)
    if await cmd.has_item_id(DS_GENERAL_ITEM):
        if rank_up_class:
            await advance_class(cmd, DS_GENERAL_NAME)
        return

    await farm_gold(cmd, 30000)
    await enchanted_scale_and_claw(cmd)
    await buy_item(cmd, DS_GENERAL_SHOP, DS_GENERAL_ITEM,
                   map_name=DS_GENERAL_MAP,
                   shop_item_id=DS_GENERAL_SHOP_ITEM_ID)

    if rank_up_class:
        await advance_class(cmd, DS_GENERAL_NAME)


async def main(cmd: Command):
    await get_ds_general(cmd)
