"""Clear the Lair chain that unlocks the Nation materials (quests 165-169).

Port of ``Nation/DragonSlayerReward.cs``.
"""
from core.command import Command
from bot.nation.core_nation import dragon_slayer_reward


async def main(cmd: Command):
    await dragon_slayer_reward(cmd)
