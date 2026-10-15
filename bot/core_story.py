"""The reference bot's ``CoreStory``: the helpers every story script leans on.

Port of ``CoreStory.cs``, kept in ``bot/`` beside the other root cores because
that is where the reference keeps it.  The parts the ported stories call:

======================  ==================================================
``map_item_quest``      ``CoreStory.MapItemQuest``, one item or several
``kill_quest``          ``CoreStory.KillQuest``, one monster or several
======================  ==================================================

How a kill quest is driven is the reference's own trick: the accepted quest's
requirements are read from its payload, the ones already held are dropped, and
what is left is mapped **by index** onto the monsters the caller named -- the last
monster taking any requirement beyond the end of the list.  The names are not in
``turnin`` (ids only), so they come from the quest's ``oItems``.

Not portable, and not reproduced:

* ``QuestProgression`` reads quest slot values out of Flash and re-completes
  earlier quests to repair a chain.  The server-side half is what is kept: a quest
  that ``is_completed_before`` is done.
* ``PreLoad`` reads the script's own compiled source to find the quests its class
  uses and preloads their data.  Nothing here needs it: the payload of an accepted
  quest carries what these routines read.
"""
from typing import Dict, List, Sequence, Tuple, Union

from core.command import Command
from templates.hunt import hunt_item, kill_quest as _kill_quest


def _as_names(value: Union[str, Sequence[str]]) -> List[str]:
    """The monster names, one or many, in the order given."""
    return [value] if isinstance(value, str) else list(value)


def _item_names(quest) -> Dict[str, str]:
    """``{ItemID: sName}`` from the quest's ``oItems`` block."""
    names: Dict[str, str] = {}
    for entry in quest.items:
        item_id = str(entry.get("ItemID", ""))
        name = entry.get("sName")
        if item_id and name:
            names[item_id] = name
    return names


def pending_requirements(cmd: Command, quest) -> List[Tuple[str, int, bool]]:
    """``(name, qty, is_temp)`` for each requirement not held yet, in payload order.

    ``turnin`` carries ids and quantities only; the name comes from ``oItems``,
    and a requirement the quest marks ``bTemp`` lives in the temp inventory.
    Rows whose name cannot be resolved are reported and skipped rather than
    farming an item by id.
    """
    names = _item_names(quest)
    temp_ids = {item.item_id for item in cmd.bot.player.TEMPINVENTORY}
    pending: List[Tuple[str, int, bool]] = []

    for entry in quest.turn_in_requirements:
        item_id = str(entry.get("ItemID", ""))
        if not item_id or item_id not in names:
            print(f"[story] quest {quest.quest_id}: a requirement has no name in "
                  f"the payload (ItemID {item_id or '?'}); skipping it.")
            continue
        qty = int(entry.get("iQty") or 1)
        is_temp = item_id in temp_ids
        held = (cmd.bot.player.get_item_temp_inventory_by_id(item_id) if is_temp
                else cmd.bot.player.get_item_inventory_by_id(item_id))
        if held is not None and int(held.qty) >= qty:
            continue
        pending.append((names[item_id], qty, is_temp))
    return pending


async def map_item_quest(cmd: Command, quest_id: int, map_name: str,
                         item_ids: Union[int, Sequence[int], Sequence[Tuple[int, int]]],
                         qty: int = 1) -> None:
    """``CoreStory.MapItemQuest``: accept, pick map items up, turn the quest in.

    The reference has three overloads and all three shapes are accepted here:

    * one id, picked up ``qty`` times;
    * a list of ids, each picked up ``qty`` times;
    * a list of ``(id, qty)`` pairs, each with its own amount.

    Every map item's own map column is not reproduced: the reference groups by map
    and joins each; every caller ported so far stays in one map, and a caller that
    needs another can call this twice.

    Args:
        cmd (Command): Facade to act through.
        quest_id (int): Quest to run.
        map_name (str): Map the items sit in -- the character is moved there
            first, because ``getMapItem`` only works where they are.
        item_ids (int | Sequence[int] | Sequence[Tuple[int, int]]): See above.
        qty (int): How many of each id to pick up, for the first two shapes.
    """
    # the reference guards this one with QuestProgression too, so a quest that is
    # already done is skipped rather than accepted a second time
    if await cmd.is_completed_before(quest_id):
        return

    if isinstance(item_ids, int):
        wanted: List[Tuple[int, int]] = [(item_ids, qty)]
    else:
        entries = list(item_ids)
        wanted = [tuple(entry) if isinstance(entry, (tuple, list)) else (entry, qty)
                  for entry in entries]

    await cmd.ensure_accept_quest(quest_id)
    while cmd.is_still_connected() and cmd.is_not_in_map(map_name):
        await cmd.join_map(map_name)
    for item_id, count in wanted:
        for _ in range(count):
            await cmd.get_map_item(item_id)
    await cmd.ensure_turn_in_quest(quest_id)


async def kill_quest(cmd: Command, quest_id: int, map_name: str,
                     monster_names: Union[str, Sequence[str]]) -> None:
    """``CoreStory.KillQuest``: accept, hunt the monster(s), turn the quest in.

    The engine's ``templates.hunt.kill_quest`` is the same loop for a single
    monster; this adds the guard the reference has (a quest that is already done
    is skipped, because a one-time quest cannot be accepted twice) and the
    requirement-to-monster mapping of its array overload.
    """
    if await cmd.is_completed_before(quest_id):
        return

    names = _as_names(monster_names)
    if len(names) == 1:
        await _kill_quest(cmd, quest_id, map_name, names[0])
        return

    await cmd.ensure_accept_quest(quest_id)
    quest = cmd.get_loaded_quest(quest_id)
    if quest is None:
        print(f"[story] quest {quest_id} did not load; nothing farmed.")
        return

    for index, (item, qty, is_temp) in enumerate(pending_requirements(cmd, quest)):
        monster = names[index] if index < len(names) else names[-1]
        await hunt_item(cmd, item, qty, map_name, monster_name=monster,
                        is_temp=is_temp)
    await cmd.ensure_turn_in_quest(quest_id)
