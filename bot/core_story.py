"""The reference bot's ``CoreStory``: the helpers every story script leans on.

Port of ``CoreStory.cs``, kept in ``bot/`` beside the other root cores because
that is where the reference keeps it.  The parts the ported stories call:

======================  ==================================================
``map_item_quest``      ``CoreStory.MapItemQuest``, one item or several
``kill_quest``          ``CoreStory.KillQuest``, one monster or several
``quest_progression``   ``CoreStory.QuestProgression``, the gate every story
                        quest runs through
``try_complete``        ``CoreStory.TryComplete``
``quest_complete``      ``CoreStory.QuestComplete``
``buy_quest``           ``CoreStory.BuyQuest``
``chain_quest``         ``CoreStory.ChainQuest``
======================  ==================================================

How a kill quest is driven is the reference's own trick: the accepted quest's
requirements are read from its payload, the ones already held are dropped, and
what is left is mapped **by index** onto the monsters the caller named -- the last
monster taking any requirement beyond the end of the list.  The names are not in
``turnin`` (ids only), so they come from the quest's ``oItems``.

Not portable, and not reproduced:

* ``QuestProgression``'s unlock-recovery loop reads the quest's slot value out of
  Flash and re-completes the previous quest to repair a chain.  The server-side
  half is what is kept: a quest that ``is_completed_before`` is done, and a
  locked one answers at ``EnsureAccept`` instead.
* ``PreLoad`` reads the script's own compiled source to find the quests its class
  uses and preloads their data.  Nothing here needs it: the payload of an accepted
  quest carries what these routines read.
* ``LegacyQuestManager`` needs the whole quest tree plus the reward-to-requirement
  mapping the reference builds from it; it is a separate job.
"""
from typing import Dict, List, Optional, Sequence, Tuple, Union

from bot.core_advanced import buy_item
from core.command import Command
from core.bot import CustomError
from templates.hunt import (DEFAULT_SKILL_LIST, hunt_item,
                            kill_quest as _kill_quest, move_to_cell)


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


def item_id_by_name(cmd: Command, quest_id: int, item_name: str) -> Optional[int]:
    """The ItemID a loaded quest gives ``item_name``, or None.

    ``HuntMonsterMapID`` names its item but this engine farms by id, and the
    quest's own payload is what carries both -- ``turnin`` has the ids and
    ``oItems`` the names.  The quest has to be accepted first (that is what puts
    it in ``loaded_quest_datas``), which is the order the reference's own
    ``EnsureAccept`` + ``HuntMonsterMapID`` pair already has.

    Args:
        cmd (Command): Facade to act through.
        quest_id (int): Quest whose payload names the item.
        item_name (str): Item to resolve.

    Returns:
        int | None: The item's id, or None when the quest is not loaded or does
        not name the item.
    """
    quest = cmd.get_loaded_quest(quest_id)
    if quest is None:
        return None
    for item_id, name in _item_names(quest).items():
        if name == item_name:
            return int(item_id)
    return None


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
            cmd.bot.log(f"[story] quest {quest.quest_id}: a requirement has no name in "
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

    if await cmd.ensure_accept_quest(quest_id) is False:
        cmd.bot.log(f"[story] quest {quest_id} could not be accepted; nothing "
                    f"is farmed for it.")
        raise CustomError(f"quest {quest_id} could not be accepted")
    # ``QuestProgression(GetReward: true)`` whitelists the quest's rewards so the
    # turn-in's item is picked up; the quest has to be loaded for its payload to
    # name them, which the accept above does.
    cmd.add_quest_rewards(quest_id)
    while cmd.is_still_connected() and cmd.is_not_in_map(map_name):
        await cmd.join_map(map_name)
    for item_id, count in wanted:
        await cmd.get_map_item(item_id, count)
    if await cmd.ensure_turn_in_quest(quest_id) is False:
        quest = cmd.bot.get_loaded_quest(quest_id)
        if quest is not None:
            for name, count, _ in pending_requirements(cmd, quest):
                cmd.bot.log(f"[story] quest {quest_id}: still missing "
                            f"{name} x{count}")
        raise CustomError(f"quest {quest_id} could not be turned in")


async def kill_quest(cmd: Command, quest_id: int, map_name: str,
                     monster_names: Union[str, Sequence[str]],
                     skill_list: Optional[Sequence[int]] = None) -> None:
    """``CoreStory.KillQuest``: accept, hunt the monster(s), turn the quest in.

    The engine's ``templates.hunt.kill_quest`` is the same loop for a single
    monster; this adds the guard the reference has (a quest that is already done
    is skipped, because a one-time quest cannot be accepted twice) and the
    requirement-to-monster mapping of its array overload.  ``skill_list`` is the
    rotation to cast, for fights that want a specific one.
    """
    if await cmd.is_completed_before(quest_id):
        return

    names = _as_names(monster_names)
    if len(names) == 1:
        if skill_list is None:
            await _kill_quest(cmd, quest_id, map_name, names[0])
        else:
            await _kill_quest(cmd, quest_id, map_name, names[0],
                              skill_list=list(skill_list))
        return

    if await cmd.ensure_accept_quest(quest_id) is False:
        cmd.bot.log(f"[story] quest {quest_id} could not be accepted; nothing "
                    f"is hunted for it.")
        raise CustomError(f"quest {quest_id} could not be accepted")
    cmd.add_quest_rewards(quest_id)
    quest = cmd.get_loaded_quest(quest_id)
    if quest is None:
        cmd.bot.log(f"[story] quest {quest_id} did not load; nothing farmed.")
        return

    for index, (item, qty, is_temp) in enumerate(pending_requirements(cmd, quest)):
        monster = names[index] if index < len(names) else names[-1]
        await hunt_item(cmd, item, qty, map_name, monster_name=monster,
                        is_temp=is_temp,
                        skill_list=skill_list or DEFAULT_SKILL_LIST)
    if await cmd.ensure_turn_in_quest(quest_id) is False:
        raise CustomError(f"quest {quest_id} could not be turned in")


# ---------------------------------------------------------------------------
# QuestProgression / TryComplete / the three quest shapes
# ---------------------------------------------------------------------------
def _quest_label(cmd: Command, quest_id: int) -> str:
    """``[id] "name"`` when the payload is loaded, else just the id."""
    quest = cmd.get_loaded_quest(quest_id)
    if quest is None:
        return f"[{quest_id}]"
    return f'[{quest_id}] - "{quest.name}"'


async def quest_progression(cmd: Command, quest_id: int,
                            get_reward: bool = True,
                            reward: str = "All",
                            log: bool = True) -> bool:
    """``CoreStory.QuestProgression``: skip a quest that needs nothing.

    The reference's unlock-recovery loop -- reading the quest's slot value out of
    Flash and re-completing the previous quest to repair a chain -- is not here;
    a locked quest answers at ``EnsureAccept`` instead, which every caller checks
    and reports.

    Args:
        cmd (Command): Facade to act through.
        quest_id (int): Quest to check.
        get_reward (bool): Whitelist the reward so the turn-in's item is picked up.
        reward (str): The one reward to want, or ``"All"`` for every reward name.
        log (bool): Report the skip or the start.

    Returns:
        bool: True when the quest needs nothing (done, or its reward is owned),
        False when the caller should run it.
    """
    if quest_id <= 0:
        return False

    if await cmd.is_completed_before(quest_id):
        if log:
            cmd.bot.log(f"Already Completed: {_quest_label(cmd, quest_id)}")
        return True

    if get_reward:
        if reward != "All":
            if await cmd.has_item(reward):
                cmd.bot.log(f'Already have reward "{reward}", skipping quest.')
                return True
            cmd.add_drop(reward)
        else:
            cmd.add_drop(cmd.get_quest_rewards(quest_id))

    if log:
        cmd.bot.log(f"Doing Quest: {_quest_label(cmd, quest_id)}")
    return False


async def try_complete(cmd: Command, quest, auto_complete: bool = True) -> bool:
    """``CoreStory.TryComplete``: turn a quest in, or say what is missing.

    The reference's ``autoCompleteQuest`` is accepted and never read -- the body
    always accepts and completes -- so this keeps that quirk rather than
    inventing a meaning for it.

    Args:
        cmd (Command): Facade to act through.
        quest: The loaded quest object.
        auto_complete (bool): Unused, as in the source.

    Returns:
        bool: True when the quest was turned in.
    """
    if quest is None:
        cmd.bot.log("[story] QuestData is null, cannot complete quest")
        return False

    quest_id = int(quest.quest_id)
    missing = pending_requirements(cmd, quest)
    if missing:
        listed = ", ".join(f"{name} x{qty}" for name, qty, _ in missing)
        cmd.bot.log(f'Missing items for quest {_quest_label(cmd, quest_id)}: '
                    f"{listed}")
        return False

    if await cmd.ensure_accept_quest(quest_id) is False:
        cmd.bot.log(f"[story] quest {quest_id} could not be accepted; nothing "
                    f"is turned in.")
        raise CustomError(f"quest {quest_id} could not be accepted")
    if await cmd.ensure_turn_in_quest(quest_id) is False:
        raise CustomError(f"quest {quest_id} could not be turned in")

    cmd.bot.log(f"Completed Quest: {_quest_label(cmd, quest_id)}")
    return True


async def quest_complete(cmd: Command, quest_id: int) -> bool:
    """``CoreStory.QuestComplete``: accept a quest and complete it at once."""
    if await cmd.ensure_accept_quest(quest_id) is False:
        cmd.bot.log(f"[story] quest {quest_id} could not be accepted; nothing "
                    f"is turned in.")
        raise CustomError(f"quest {quest_id} could not be accepted")
    return await try_complete(cmd, cmd.get_loaded_quest(quest_id))


async def buy_quest(cmd: Command, quest_id: int, map_name: str, shop_id: int,
                    item_name: str, amount: int = 1, get_reward: bool = True,
                    reward: str = "All",
                    auto_complete: bool = True) -> None:
    """``CoreStory.BuyQuest``: accept, buy the quest's item, turn it in.

    Args:
        cmd (Command): Facade to act through.
        quest_id (int): Quest to run.
        map_name (str): Map the shop is on.
        shop_id (int): Shop to buy from.
        item_name (str): Item the quest wants.
        amount (int): How many.
        get_reward (bool): Whitelist the reward.
        reward (str): The one reward to want, or ``"All"``.
        auto_complete (bool): Forwarded to :func:`try_complete`.
    """
    if await quest_progression(cmd, quest_id, get_reward, reward):
        return
    if await cmd.ensure_accept_quest(quest_id) is False:
        cmd.bot.log(f"[story] quest {quest_id} could not be accepted; nothing "
                    f"is bought.")
        raise CustomError(f"quest {quest_id} could not be accepted")
    await buy_item(cmd, shop_id, item_name, amount, map_name=map_name)
    await try_complete(cmd, cmd.get_loaded_quest(quest_id), auto_complete)


async def chain_quest(cmd: Command, quest_id: int, get_reward: bool = True,
                      reward: str = "All", auto_complete: bool = True) -> None:
    """``CoreStory.ChainQuest``: accept a no-requirement quest and turn it in."""
    if await quest_progression(cmd, quest_id, get_reward, reward):
        return
    if await cmd.ensure_accept_quest(quest_id) is False:
        cmd.bot.log(f"[story] quest {quest_id} could not be accepted; nothing "
                    f"is turned in.")
        raise CustomError(f"quest {quest_id} could not be accepted")
    await try_complete(cmd, cmd.get_loaded_quest(quest_id), auto_complete)
