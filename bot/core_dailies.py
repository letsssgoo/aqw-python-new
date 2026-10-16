"""``CoreDailies`` -- the dailies the Nation cores ask for.

Port of ``CoreDailies.cs``, kept in ``bot/`` beside the other root cores because
that is where the reference keeps it.  Only ``EldersBlood`` is ported so far: it
is what ``CoreVHL`` cannot finish the Void Highlord challenge without.  The
runnable ``Dailies/`` scripts that wrap this get mirrored under ``bot/dailies/``
as they are ported.

Note:
    The reference gates a daily on its own client-side flag
    (``Bot.Quests.IsDailyComplete``, reached through ``DailyRoutine`` and
    ``CheckDailyv2``).  This engine keeps no such flag, so the gate here is the
    server's answer to the accept -- a daily that is already done is refused --
    which :meth:`Command.ensure_accept_quest` reports.  Nothing is farmed in that
    case, and the call says why.
"""
from bot.core_bots import equip_class, wait_for_item
from core.command import Command
from templates.hunt import hunt_item

#: Quest 802 in /arcangrove: 50 Slain Gorillaphant for one Elders' Blood.
ELDERS_BLOOD = "Elders' Blood"
ELDERS_BLOOD_QUEST = 802
ELDERS_BLOOD_MAP = "arcangrove"
ELDERS_BLOOD_CELL = "LeftBack"
ELDERS_BLOOD_PAD = "Left"
ELDERS_BLOOD_MONSTER = "Gorillaphant"
ELDERS_BLOOD_KILLS = 50

#: The reference stops here, which is the item's max stack.
ELDERS_BLOOD_MAX = 20


async def elders_blood(cmd: Command) -> None:
    """``CoreDailies.EldersBlood``: the one-a-day Elders' Blood, quest 802.

    Returns nothing, as the reference does: its callers check the item for
    themselves afterwards, and both ``CoreVHL`` sites do.  A daily that cannot be
    accepted -- already done today, or its prerequisite missing -- is reported
    rather than retried against a quest that refuses.
    """
    if await cmd.has_item(ELDERS_BLOOD, ELDERS_BLOOD_MAX):
        return

    if not await cmd.ensure_accept_quest(ELDERS_BLOOD_QUEST):
        cmd.bot.log(f"[dailies] {ELDERS_BLOOD} (quest {ELDERS_BLOOD_QUEST}) cannot be "
              f"accepted right now: the daily is done for today. "
              f"Nothing farmed.")
        return

    cmd.add_drop(ELDERS_BLOOD)
    cmd.bot.log("Daily: Elders' Blood")
    await equip_class(cmd)
    await hunt_item(cmd, "Slain Gorillaphant", ELDERS_BLOOD_KILLS,
                    ELDERS_BLOOD_MAP, cell=ELDERS_BLOOD_CELL,
                    pad=ELDERS_BLOOD_PAD, monster_name=ELDERS_BLOOD_MONSTER,
                    is_temp=True)
    await cmd.ensure_turn_in_quest(ELDERS_BLOOD_QUEST)
    await wait_for_item(cmd, ELDERS_BLOOD)
