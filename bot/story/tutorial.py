"""``Tutorial`` -- the ten starter badges in /oaklore.

Port of ``Story/Tutorial.Badges``.  The reference reads each badge back with
``Core.HasAchievement`` (a client-side ``world.getAchievement`` call) and skips
the whole run when badge 31 is already set; this engine has no client to ask, so
the ``setAchievement`` packet is sent for every badge instead.  The server keeps
the ones already earned, which makes the repeat harmless.
"""
from bot.core_bots import set_achievement
from core.command import Command
from bot.script_log import ScriptLog
TAG = "Tutorial"

TUTORIAL_MAP = "oaklore"
#: ``achievements`` in the source, badges 22..31 in this order.
TUTORIAL_BADGES = ("Combat", "Interact", "Quest", "Skill", "Shop", "Enhance",
                   "Rest", "World", "Emotes", "Travel")
TUTORIAL_FIRST_BADGE = 22
#: ``Bot.Wait.ForActionCooldown(GameActions.DoIA)`` is followed by this sleep.
BADGE_GAP_MS = 1500


async def badges(cmd: Command) -> None:
    """``Tutorial.Badges``: set badges 22-31."""
    ScriptLog(cmd, TAG).info('Doing `Tutorial Badges` to look a bit more "~legit~".')

    await cmd.join_map(TUTORIAL_MAP)

    for offset in range(len(TUTORIAL_BADGES)):
        await set_achievement(cmd, TUTORIAL_FIRST_BADGE + offset)
        await cmd.sleep(BADGE_GAP_MS)


async def main(cmd: Command):
    await badges(cmd)
