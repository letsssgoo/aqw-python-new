import asyncio
from datetime import datetime
from typing import TYPE_CHECKING
from colorama import Fore

if TYPE_CHECKING:
    from core.bot import Bot
    
async def death_handler_task(bot: 'Bot'):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Running death handler...")
    for i in range(11):
        print(f"Respawn in {11 - i} seconds...")
        await asyncio.sleep(1)
    bot.debug(Fore.MAGENTA + "respawned" + Fore.WHITE)
    bot.write_message(f"%xt%zm%resPlayerTimed%{bot.areaId}%{bot.user_id}%")
    # ``player.CELL`` is read *after* the respawn request, so by then the
    # server has usually put the character back on the map's spawn cell
    # ("Enter") -- jumping to it is what left farms standing there.  Use the
    # place the player died in, when it was the same map.
    died_at = getattr(bot, "death_cell_pad", None)
    if died_at and died_at[0] == bot.strMapName:
        cell, pad = died_at[1], died_at[2]
    elif bot.respawn_cell_pad:
        cell, pad = bot.respawn_cell_pad[0], bot.respawn_cell_pad[1]
    else:
        cell, pad = bot.player.CELL, bot.player.PAD
    bot.jump_cell(cell, pad)
    bot.player.ISDEAD = False
    bot.player.IS_IN_COMBAT = False
    bot.player.CURRENT_HP = bot.player.MAX_HP
    bot.player.MANA = 100
    bot.player.removeAllAuras()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Spawned at cell:", bot.player.CELL, "pad:", bot.player.PAD)