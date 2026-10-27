"""``Mazumi`` -- quests 90-92, the Ninja shop's prerequisite chain.

Port of ``Story/Mazumi.MazumiQuests``.  Quest 92 is the one the Joe kit cares
about: the /classhalla Ninja shop refuses to sell until it is done.
"""
from bot.core_bots import equip_class
from bot.core_story import CustomError, kill_quest, quest_progression
from core.command import Command
from templates.hunt import hunt_item
from bot.script_log import ScriptLog
TAG = "Mazumi"

MAZUMI_LAST = 92
MAZUMI_MAP = "greenguardwest"


async def _quest(cmd: Command, quest_id: int, body) -> None:
    """``if (!Story.QuestProgression(q)) { accept; body; complete; }``."""
    if await quest_progression(cmd, quest_id):
        return
    if await cmd.ensure_accept_quest(quest_id) is False:
        raise CustomError(f"quest {quest_id} could not be accepted")
    await body()
    if await cmd.ensure_turn_in_quest(quest_id) is False:
        raise CustomError(f"quest {quest_id} could not be turned in")


async def mazumi_quests(cmd: Command) -> None:
    """``Mazumi.MazumiQuests``: quests 90, 91 and 92."""
    if await cmd.is_completed_before(MAZUMI_LAST):
        return

    # 90 - Ninja Grudge
    await kill_quest(cmd, 90, "pirates", "Fishman Soldier")

    # 91 - Without a Trace
    async def q91() -> None:
        await hunt_item(cmd, "Kittarian's Wallet", 2, MAZUMI_MAP,
                        monster_name="Kittarian")
        await hunt_item(cmd, "River Fishman's Wallet", 2, MAZUMI_MAP,
                        monster_name="River Fishman")
        await hunt_item(cmd, "Slime-Soaked Wallet", 2, MAZUMI_MAP,
                        monster_name="Slime")
        # West1 holds an extra Frogzard the source does not want, hence West3.
        await hunt_item(cmd, "Frogzard's Lint Hoard", 2, MAZUMI_MAP,
                        cell="West3", pad="Up", monster_name="Frogzard")
        await hunt_item(cmd, "Big Bad Boar's Wallet", 1, MAZUMI_MAP,
                        cell="West12", pad="Up", monster_name="Big Bad Boar")

    await _quest(cmd, 91, q91)

    # 92 - Hit Job
    await equip_class(cmd, solo=True)

    async def q92() -> None:
        await hunt_item(cmd, "Breken the Vile's Sword", 1, MAZUMI_MAP,
                        monster_name="Breken the Vile")
        await hunt_item(cmd, "Ogug Stoneaxe's Helmet", 1, MAZUMI_MAP,
                        monster_name="Ogug Stoneaxe")

    await _quest(cmd, 92, q92)


async def main(cmd: Command):
    await mazumi_quests(cmd)
