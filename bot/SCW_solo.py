from core.bot import Bot
from core.command import Command
from templates.hunt import hunt_item

async def main(cmd: Command):
    # cmd = Command(bot)

    if cmd.bot.farmClass:
        await cmd.equip_item(cmd.bot.farmClass)
    
    while cmd.is_not_in_map("sevencircleswar"):
        await cmd.join_map("sevencircleswar", 9909)
        await cmd.sleep(1000)

    await cmd.register_quest(7980)
    await cmd.register_quest(7981)

    cell = "Enter"
    pad = "Spawn"
    await cmd.jump_cell(cell, pad)

    skill_list = [0,1,2,0,3,4]
    skill_index = 0

    while cmd.is_still_connected():

        await cmd.use_skill(skill_list[skill_index])
        skill_index += 1
        if skill_index >= len(skill_list):
            skill_index = 0
        await cmd.sleep(100)

        if cmd.bot.player.EXPFARMED > 100_000:
            cmd.bot.log("EXPFARMED > 100.000, saving state..")
            await cmd.jump_cell("r4", "Left")
            await cmd.sleep(1000)
            await cmd.jump_cell(cell, pad)
            cmd.bot.player.EXPFARMED = 0
        
        if cmd.bot.player.GOLDFARMED > 500_000:
            cmd.bot.log("GOLDFARMED > 500.000, saving state..")
            await cmd.jump_cell("r4", "Left")
            await cmd.sleep(1000)
            await cmd.jump_cell(cell, pad)
            cmd.bot.player.GOLDFARMED = 0