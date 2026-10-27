import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.bot import Bot

async def register_quest_task(bot: 'Bot'):
    print("Running registered quests...")
    while bot.is_client_connected:
        for registered_quest_id in list(bot.registered_auto_quest_ids):
            if registered_quest_id in getattr(bot, "missing_badge_questid", []):
                # "Missing Badge" is the server saying this daily is not
                # available right now; drop it instead of asking the server once
                # every two seconds for the rest of the run.
                bot.registered_auto_quest_ids.remove(registered_quest_id)
                print(f"[quest] {registered_quest_id} is not available right "
                      f"now (\"Missing Badge\"); unregistered.")
                continue
            if bot.quest_not_in_progress(registered_quest_id):
                bot.accept_quest(registered_quest_id)
            if bot.can_turn_in_quest(registered_quest_id):
                bot.turn_in_quest(registered_quest_id)
                await asyncio.sleep(1)
                bot.accept_quest(registered_quest_id)
            await asyncio.sleep(1)
        await asyncio.sleep(2)
    print("Stopping registered quests...")