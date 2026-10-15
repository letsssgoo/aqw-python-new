from core.bot import Bot
from core.command import Command
from templates.hunt import hunt_item

async def main(cmd: Command):

    if cmd.bot.soloClass:
        await cmd.equip_item(cmd.bot.soloClass)
    
    await cmd.equip_enhancement("Valiance")
    await cmd.equip_enhancement("Vainglory")
    await cmd.equip_enhancement("Wizard Helm Enhancement")
    
    while cmd.is_not_in_map("hydrachallenge"):
        await cmd.join_map("hydrachallenge", 9909)
        await cmd.sleep(1000)
    
    await cmd.jump_cell("h90", "Left")

    await cmd.register_quest(555)
    cmd.add_drop("Relic of Chaos")
    cmd.add_drop([
        "Voucher of Nulgath",
        "Voucher of Nulgath (non-mem)",
        "Tainted Gem",
        "Dark Crystal Shard",
        "Diamond of Nulgath",
        "Gem of Nulgath",
        "Totem of Nulgath",
        "Essence of Nulgath",
        "Blood Gem of the Archfiend",
        "Receipt of Swindle"
    ])

    await cmd.bank_to_inv("Essence of Nulgath")

    swindles_items = [
        "Unidentified 1",
        "Unidentified 6",
        "Unidentified 9",
        "Unidentified 16",
        "Unidentified 20",
    ]

    await cmd.bank_to_inv(swindles_items)
    cmd.add_drop(swindles_items)

    skill_list = [0,1,2,0,3,4]
    skill_index = 0

    cmd.start_aggro_by_cell("h90")
    
    while cmd.is_still_connected():

        await cmd.use_skill(skill_list[skill_index], target_monsters="id.32,id.33,id.34")
        skill_index += 1
        if skill_index >= len(skill_list):
            skill_index = 0
        await cmd.sleep(100)

        # if cmd.is_in_inventory("Relic of Chaos"):
        #     await cmd.turn_in_quest(555)
        #     await cmd.sleep(500)
        #     await cmd.accept_quest(555)

        if cmd.bot.player.GOLD < 100_000_000 and cmd.is_in_inventory("Voucher of Nulgath"):
            await stop_aggro_enter(cmd)
            await cmd.sell_item("Voucher of Nulgath")
            await cmd.jump_cell("h90", "Left")
            cmd.start_aggro_by_cell("h90")
        
        if cmd.is_in_inventory("Voucher of Nulgath (non-mem)"):
            if cmd.is_in_inventory("Essence of Nulgath", 60):
                print("trying do voucher quest")
                await stop_aggro_enter(cmd)
                await cmd.ensure_accept_quest(4778)
                if not cmd.is_in_inventory_or_bank("Gem of Nulgath", 1000):
                    await cmd.ensure_turn_in_quest(4778, 6136)
                elif not cmd.is_in_inventory_or_bank("Totem of Nulgath", 1000):
                    await cmd.ensure_turn_in_quest(4778, 5357)
                await cmd.jump_cell("h90", "Left")
                cmd.start_aggro_by_cell("h90")
        
        if check_swindles(cmd, swindles_items):
            print("trying do swindles")
            await stop_aggro_enter(cmd)
            await cmd.ensure_accept_quest(7551)
            await cmd.join_map("evilmarsh", 999999)
            await cmd.sleep(1000)
            await cmd.jump_cell("Field1", "Left")
            while not cmd.is_in_inventory("Dark Makai Rune", isTemp=True) and cmd.is_still_connected():
                await cmd.use_skill(skill_list[skill_index], target_monsters="Dark Makai")
                skill_index += 1
                if skill_index >= len(skill_list):
                    skill_index = 0
                await cmd.sleep(100)
            # dark crystal shard 4770 : 1000
            # tainted gem 4769 : 1000
            # Diamond of Nulgath 4771 : 1000
            # Blood Gem of the Archfiend 22332 : 100
            # Gem of Nulgath 6136 : 1000

            if not cmd.is_in_inventory_or_bank("Dark Crystal Shard", 1000):
                await cmd.ensure_turn_in_quest(7551, 4770)
            elif not cmd.is_in_inventory_or_bank("Tainted Gem", 1000):
                await cmd.ensure_turn_in_quest(7551, 4769)
            elif not cmd.is_in_inventory_or_bank("Diamond of Nulgath", 1000):
                await cmd.ensure_turn_in_quest(7551, 4771)
            elif not cmd.is_in_inventory_or_bank("Blood Gem of the Archfiend", 1000):
                await cmd.ensure_turn_in_quest(7551, 22332)
            elif not cmd.is_in_inventory_or_bank("Gem of Nulgath", 1000):
                await cmd.ensure_turn_in_quest(7551, 6136)
            await cmd.join_map("hydrachallenge", 9909, True)
            await cmd.sleep(1000)
            await cmd.jump_cell("h90", "Left")
            cmd.start_aggro_by_cell("h90")



async def stop_aggro_enter(cmd : Command):
    cmd.stop_aggro()
    await cmd.sleep(1000)
    await cmd.jump_cell("Enter", "Spawn")
    await cmd.sleep(500)

def check_swindles(cmd: Command, item_list) -> bool:
    for item in item_list:
        if not cmd.is_in_inventory(item):
            return False
    return True