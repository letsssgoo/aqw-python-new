"""The reference bot's ``CoreStory``: the helpers every story script leans on.

Port of ``CoreStory.cs``, kept in ``bot/`` beside the other root cores because
that is where the reference keeps it.  Only the parts the ported stories call are
here so far:

======================  ==================================================
``map_item_quest``      ``CoreStory.MapItemQuest``
``kill_quest``          ``CoreStory.KillQuest``, guard included
======================  ==================================================

Two things it does are not portable:

* ``QuestProgression`` decides whether there is anything to do from the quest's
  *client-side* data -- it reads quest slot values out of Flash and re-completes
  earlier quests to repair a chain.  What is reproduced here is the server-side
  half: a quest that ``is_completed_before`` is done and skipped.
* ``PreLoad`` fills a client-side quest cache before a chain runs.  Nothing here
  needs it: the payload of an accepted quest carries what the routines read.
"""
from core.command import Command
from templates.hunt import hunt_item, kill_quest as _kill_quest


async def map_item_quest(cmd: Command, quest_id: int, map_name: str,
                         item_id: int, qty: int = 1) -> None:
    """``CoreStory.MapItemQuest``: accept, pick map items up, turn the quest in.

    Args:
        cmd (Command): Facade to act through.
        quest_id (int): Quest to run.
        map_name (str): Map the item sits in -- the character is moved there
            first, because ``getMapItem`` only works where the item is.
        item_id (int): The map item's id.
        qty (int): How many to pick up.
    """
    await cmd.ensure_accept_quest(quest_id)
    while cmd.is_still_connected() and cmd.is_not_in_map(map_name):
        await cmd.join_map(map_name)
    for _ in range(qty):
        await cmd.get_map_item(item_id)
    await cmd.ensure_turn_in_quest(quest_id)


async def kill_quest(cmd: Command, quest_id: int, map_name: str,
                     monster_name: str) -> None:
    """``CoreStory.KillQuest``: accept, hunt the monster, turn the quest in.

    The engine's ``templates.hunt.kill_quest`` is the same loop; this adds the
    guard the reference has, which skips a quest that is already done -- a
    one-time quest cannot be accepted a second time.
    """
    if await cmd.is_completed_before(quest_id):
        return
    await _kill_quest(cmd, quest_id, map_name, monster_name)
