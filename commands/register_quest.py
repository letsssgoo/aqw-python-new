from core.bot import Bot
from core.command import Command
from abstracts.base_command import BaseCommand
from model import normalize_quest_id

class RegisterQuestCmd(BaseCommand):
    
    def __init__(self, questId: int):
        self.questId = questId
    
    async def execute(self, bot: Bot, cmd: Command):
        quest_id = normalize_quest_id(self.questId)
        if quest_id not in bot.registered_auto_quest_ids:
            bot.registered_auto_quest_ids.append(quest_id)
            bot.accept_quest(quest_id)
        
    def to_string(self):
        return f"Register quest : {self.questId}"