from core.bot import Bot
from core.command import Command
from templates.hunt import hunt_item

async def main(bot: Bot):
    cmd = Command(bot)

    await cmd.join_map("frozenqueen")

    # await cmd.load_shop(2507)
    # await cmd.sleep(2000)

    # shop = cmd.get_loaded_shop(2507)
    # if not shop:
    #     cmd.stop_bot(f"shop id 2507 not loaded")
    #     return
    # print("LOADED")
    # for item in shop.items:
    #     for turnin in item.turnin:
    #         print(turnin.item_name)
    
    await FrozenSpiderSilk(bot, cmd, 130)
    await IceVapor(bot, cmd, 32)

    cmd.stop_bot("DONE FARMING 130 Frozen SpiderSilk and 32 Ice Vapor")

async def FrozenSpiderSilk(bot: Bot, cmd: Command, qty: int):
    item_name = "Frozen SpiderSilk"
    await cmd.bank_to_inv(item_name)
    cmd.add_drop(item_name)

    if bot.soloClass:
        await cmd.equip_item(bot.soloClass)

    await cmd.register_quest(10018)

    guard = cmd.pass_guard(item_name)
    while cmd.is_still_connected():
        if cmd.is_in_inventory(item_name, qty, ">="):
            break

        await hunt_item(
            cmd,
            item_name=item_name,
            item_qty=qty,
            map_name="frozenqueen",
            cell="r2",
            pad="Left",
            monster_name="*",
            farming_logger=True
        )
        if not await guard.tick():
            break

async def IceVapor(bot: Bot, cmd: Command, qty: int):
    item_name = "Ice Vapor"
    await cmd.bank_to_inv(item_name)
    cmd.add_drop(item_name)

    if bot.farmClass:
        await cmd.equip_item(bot.farmClass)

    guard = cmd.pass_guard(item_name)
    while cmd.is_still_connected():
        if cmd.is_in_inventory(item_name, qty, ">="):
            break

        await hunt_item(
            cmd,
            item_name=item_name,
            item_qty=qty,
            map_name="lair",
            room_number=9999999,
            cell="Enter",
            pad="Spawn",
            monster_name="*",
            farming_logger=True
        )
        if not await guard.tick():
            break
    
