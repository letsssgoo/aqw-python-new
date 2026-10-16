from core.command import Command
from core.task import FarmTask, do_farm_tasks
from colorama import Fore

async def main(cmd: Command):
    map_name = "thelimacity"    
    item_to_farm: list[FarmTask] = [
        FarmTask(
            item_name="Ferrum Blood", 
            qty=12, 
            map_name=map_name,
            cell="r9", 
            pad="Right"
        ),
        FarmTask(
            item_name="Elemental Ferrum", 
            qty=3, 
            map_name=map_name, 
            cell="r10", 
            pad="Right"
        ),
        FarmTask(
            item_name="Maleno Flicker", 
            qty=1, 
            map_name=map_name, 
            cell="r11", 
            pad="Right", 
            is_solo=True
        ),
    ]
    complete_count = 0

    # await cmd.register_quest(10357)
    await cmd.register_quest(10358)

    while cmd.is_still_connected():
        await do_farm_tasks(cmd, item_to_farm)
        complete_count = complete_count + 1
        cmd.bot.log(Fore.GREEN + f"Complete count : {complete_count}" + Fore.RESET)