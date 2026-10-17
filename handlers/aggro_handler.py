import asyncio
from typing import TYPE_CHECKING
from colorama import Fore

if TYPE_CHECKING:
    from core.bot import Bot


async def aggro_handler_task(bot: 'Bot'):
    """Keep re-sending ``aggroMon`` for the monsters of the current cell.

    One task per bot: ``Command.start_aggro`` replaces the task instead of adding
    another (see its docstring), and the loop leaves as soon as aggro is switched
    off or the connection ends.
    """
    print("Running aggro handler...")
    while bot.is_client_connected and bot.is_aggro_handler_task_running:
        if bot.aggro_mons_id:
            aggroMon = f"%xt%zm%aggroMon%{bot.areaId}%{'%'.join(map(str, bot.aggro_mons_id))}%"
            bot.write_message(aggroMon)
        await asyncio.sleep(max(0.1, bot.aggro_delay_ms / 1000))
    print("Stopping aggro handler...")
