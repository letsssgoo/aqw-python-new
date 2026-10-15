from core.bot import Bot
from core.command import Command
import json

is_locked_zone = False

#: Set by ``main``: a subscriber only receives the message, so the listener logs
#: through this instead.
_bot = None

async def main(cmd: Command):
    global is_locked_zone, _bot

    await cmd.join_map("whitemap")

    await cmd.equip_item("Legion Revenant")

    skill_list = [0,1,2,0,3,4]
    skill_index = 0

    list_maps = [
        "shadowrealmpast"
    ]
    index_count = 0

    _bot = cmd.bot
    cmd.bot.subscribe(message_handler)

    while cmd.is_still_connected():
        if is_locked_zone:
            await cmd.join_map(list_maps[index_count])
            is_locked_zone = False
            index_count = (index_count + 1) % len(list_maps)
            await cmd.sleep(1000)
        if cmd.bot.follow_player != "" and cmd.bot.followed_player_cell != cmd.bot.player.CELL:
            await cmd.goto_player(cmd.bot.follow_player)
            await cmd.sleep(1000)
            continue 
        await cmd.use_skill(skill_list[skill_index])
        skill_index += 1
        if skill_index >= len(skill_list):
            skill_index = 0
        await cmd.sleep(100)

def message_handler(message):
    global is_locked_zone
    if message:
        if message.startswith("%") and message.endswith("%"):
            if "locked zone" in message.lower():
                msg = message.split('%')
                text = msg[4]
                if _bot is not None:
                    _bot.log(f"[follower] server warning: {text}")
                is_locked_zone = True

def is_valid_json(s):
    try:
        json.loads(s)
        return True
    except json.JSONDecodeError:
        return False