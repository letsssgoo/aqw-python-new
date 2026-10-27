from core.bot import Bot
from core.command import Command
from bot.potion.core_potion import PotentDestructionElixir, PotentHonorMalice, PotentMalevolence, PotentRevitalizeElixir, PotentBattleElixir, SageTonic, FateTonic, BodyTonic, MightTonic

# get the maxiumum quant of potions
async def main(cmd: Command):

    await PotentHonorMalice(cmd)
    await PotentMalevolence(cmd)
    await SageTonic(cmd)
    await PotentDestructionElixir(cmd)
    await PotentRevitalizeElixir(cmd)
    await PotentBattleElixir(cmd)
    await FateTonic(cmd)
    await BodyTonic(cmd)
    await MightTonic(cmd)

    cmd.stop_bot("MAX ALL POTIONS DONE")
