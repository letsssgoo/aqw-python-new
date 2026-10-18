import time

from core.bot import Bot
import commands as cmd
from core.command import Command

# The standard rotation. Order only matters for the paths that replay it
# literally (the chrono branch and the non-async command list); the scheduler in
# Command.use_next_skill collapses the duplicate slot on entry.
DEFAULT_SKILL_LIST: list[int] = [0, 1, 2, 0, 3, 4]

#: How many times a hunt will ask for its map before giving up.  ``join_map``
#: already waits out a transfer that is still in flight, so more than a couple
#: of passes means the map itself cannot be reached -- and reporting that beats
#: retrying for the rest of the run.
JOIN_ATTEMPTS: int = 5

#: How many times a hunt will ask for its cell before giving up.  ``jump_cell``
#: lands in a second when the cell exists; a cell that is not there (or a
#: character stuck in the wrong instance) never will, and looping on it forever
#: is the "bot is stuck and never comes back" case.
CELL_ATTEMPTS: int = 5

#: How often a hunt re-looks for its monster while nothing is dropping, in
#: seconds, and how long it keeps that up before reporting and stopping.
STALL_CHECK_S: float = 60.0
STALL_GIVE_UP_S: float = 15 * 60.0


def _held_count(cmd: Command, item_name: str, is_temp: bool) -> int:
    """How many of ``item_name`` the account holds, temp bag included."""
    total = cmd.get_quant_item(item_name)
    player = getattr(cmd.bot, "player", None)
    get_temp = getattr(player, "get_item_temp_inventory", None)
    if get_temp is not None:
        found = get_temp(item_name)
        if found is not None:
            total = max(total, int(getattr(found, "qty", 0) or 0))
    return total


def _has_target(cmd: Command, monster_name: str) -> bool:
    """Whether the map's own monster list carries something to attack.

    ``jump_to_monster`` returns silently when it finds nothing, which is what
    leaves a hunt standing still; this is the same match, asked separately.
    """
    names = [t.strip().lower() for t in str(monster_name or "*").split(',')
             if t.strip()] or ["*"]
    for mon in cmd.bot.monsters:
        if "*" in names:
            return True
        mon_name = (mon.mon_name or "").lower()
        mon_id = str(mon.mon_map_id)
        for target in names:
            if target.startswith("id.") and target.split(".")[1] == mon_id:
                return True
            if target in (mon_id, mon_name):
                return True
    return False


async def move_to_cell(cmd: Command, cell: str, pad: str,
                        item_name: str = "") -> bool:
    """Stand in ``cell``/``pad``, bounded and reported.

    Args:
        cmd (Command): Facade to act through.
        cell (str): Cell the hunt needs.
        pad (str): Pad within that cell.
        item_name (str): What would have been farmed, for the message.

    Returns:
        bool: True once the cell is reached; False when it cannot be, after
        saying so -- the caller then skips the hunt instead of looping.
    """
    attempts = 0
    while cmd.is_not_in_cell(cell):
        attempts += 1
        if attempts > CELL_ATTEMPTS:
            cmd.bot.log(f"[hunt] cell {cell} was not reached after "
                        f"{CELL_ATTEMPTS} tries (in {cmd.bot.strMapName} at "
                        f"{cmd.bot.player.CELL}); {item_name or 'the item'} was "
                        f"not farmed.")
            return False
        if attempts > 1:
            cmd.bot.log(f"[hunt] {cmd.bot.strMapName}/{cell}: still not there, "
                        f"trying again ({attempts}/{CELL_ATTEMPTS})")
        await cmd.jump_cell(cell, pad)
        await cmd.sleep(1000)
    return not cmd.is_not_in_cell(cell)


async def _join_for_hunt(cmd: Command, map_name: str, room_number: int = None,
                         item_name: str = "") -> bool:
    """Join ``map_name`` for a hunt, bounded and reported.

    Args:
        cmd (Command): Facade to act through.
        map_name (str): Map the hunt needs.
        room_number (int | None): Room to ask for, or None for any.
        item_name (str): What would have been farmed, for the message.

    Returns:
        bool: True once the map is reached; False when it cannot be, after
        saying so -- the caller then skips the hunt instead of looping.
    """
    attempts = 0
    while cmd.is_not_in_map(map_name):
        attempts += 1
        if attempts > JOIN_ATTEMPTS:
            cmd.bot.log(f"[hunt] {map_name} could not be reached after "
                        f"{JOIN_ATTEMPTS} tries (still in "
                        f"{cmd.bot.strMapName}); {item_name or 'the item'} was "
                        f"not farmed.")
            return False
        if attempts > 1:
            cmd.bot.log(f"[hunt] {map_name}: join did not land, retrying "
                        f"({attempts}/{JOIN_ATTEMPTS})")
        await cmd.join_map(map_name, room_number)
        await cmd.sleep(1000)
    return True

async def hunt_item(
        cmd: Command,
        item_name: str, 
        item_qty: int, 
        map_name: str, 
        cell: str = None, 
        pad: str = "Left", 
        room_number: int = None, 
        monster_name: str = "*",
        most_monster: bool = False,
        farming_logger: bool = False,
        hunt: bool = False,
        skill_list: list[int] = DEFAULT_SKILL_LIST,
        is_temp: bool = False,
    ):
    if cmd.is_in_bank(item_name):
        await cmd.bank_to_inv(item_name)

    if (cmd.is_in_inventory(item_name, item_qty, operator=">=") or cmd.is_in_inventory(item_name, item_qty, operator=">=", isTemp=True)):
        return

    cmd.add_drop(item_name)
    
    if not await _join_for_hunt(cmd, map_name, room_number, item_name):
        return

    if cell:
        hunt = False
        if not await move_to_cell(cmd, cell, pad, item_name):
            return
    else:
        await cmd.jump_to_monster(monster_name, most_monster)

    if farming_logger:
        cmd.farming_logger(item_name, item_qty, is_temp)

    skill_list = skill_list
    skill_index = 0

    #: The loop below only stops on the item.  A bot that never reaches the
    #: monster -- standing at Enter because the map's monster list has no match,
    #: the case /shadowblast shows -- keeps casting at nothing and never says so.
    #: So: every STALL_CHECK_S without a single item gained, look for the target
    #: again (a fresh moveToArea is what refreshes the monster list), and after
    #: STALL_GIVE_UP_S of that, report and let the caller (or the session's stall
    #: watchdog) take over.
    last_progress = time.monotonic()
    last_count = _held_count(cmd, item_name, is_temp)
    last_look = last_progress

    while cmd.is_still_connected():
        if cmd.is_in_inventory(item_name, item_qty, operator=">=") or cmd.is_in_inventory(item_name, item_qty, operator=">=", isTemp=True):
            await cmd.leave_combat()
            break
        now = time.monotonic()
        held = _held_count(cmd, item_name, is_temp)
        if held != last_count:
            last_count = held
            last_progress = now
        elif now - last_progress >= STALL_GIVE_UP_S:
            cmd.bot.log(f"[hunt] {item_name}: no progress for "
                        f"{STALL_GIVE_UP_S / 60:.0f} min in {map_name} "
                        f"(cell {cmd.bot.player.CELL}); stopping the hunt.")
            return
        elif now - last_look >= STALL_CHECK_S:
            # Look for the target again: re-join if the map carries no matching
            # monster at all (its cell list is built from the area packet), then
            # walk to whichever cell does have it.
            last_look = now
            cmd.bot.log(f"[hunt] {item_name}: still at "
                        f"{cmd.bot.player.CELL} with {held}/{item_qty}; "
                        f"looking for {monster_name} again")
            if not _has_target(cmd, monster_name):
                await cmd.join_map(map_name, room_number)
            await cmd.jump_to_monster(monster_name, most_monster)
            continue
        playerclass = cmd.get_equipped_class()
        playerclass = playerclass.item_name if playerclass else ""
        if "chrono shadow" in playerclass.lower():
            # Chrono rotations are order-sensitive, so keep the fixed sequence.
            await cmd.wait_use_skill(skill_list[skill_index])
            skill_index += 1
            if skill_index >= len(skill_list):
                skill_index = 0
            await cmd.sleep(100)
        else:
            # Readiness scheduler: casts whichever listed slot is ready and
            # sleeps internally until the next one comes up. The old round-robin
            # plus a blind sleep(100) after every attempt wasted 1096 attempts
            # and 110 s of the baseline run (SKILL_ANALYSIS.md 3.1/3.2).
            await cmd.use_next_skill(skill_list, monster_name, hunt)
    return

async def hunt_item_by_id(
        cmd: Command,
        item_id: int,
        item_qty: int,
        map_name: str,
        cell: str = None,
        pad: str = "Left",
        monster_map_id: int = 0,
        is_temp: bool = True,
    ):
    """Kill a monster *by its map id* until the item *by its id* is held.

    ``Core.KillMonster`` has an overload that names both by id rather than by
    name -- ``fiendshard``'s quest 7898 is one -- and ``hunt_item`` matches by
    name only.  The item is looked for in the temp bag when ``is_temp``, which is
    where quest progress items land.
    """
    def held() -> bool:
        item = (cmd.bot.player.get_item_temp_inventory_by_id(item_id)
                if is_temp else None)
        item = item or cmd.bot.player.get_item_inventory_by_id(item_id)
        return bool(item and int(item.qty) >= item_qty)

    if held():
        return

    if not await _join_for_hunt(cmd, map_name, None, f"item {item_id}"):
        return

    if cell:
        if not await move_to_cell(cmd, cell, pad, f"item {item_id}"):
            return

    target = f"id.{monster_map_id}" if monster_map_id else "*"
    while cmd.is_still_connected():
        if held():
            await cmd.leave_combat()
            break
        await cmd.use_next_skill(DEFAULT_SKILL_LIST, target)


async def kill_quest(
        cmd: Command,
        quest_id: int,
        map_name: str, 
        monster_name: str = "*",
        room_number: int = None, 
        hunt: bool = False,
        skill_list: list[int] = DEFAULT_SKILL_LIST
    ):
    await cmd.ensure_accept_quest(quest_id)
    
    if cmd.can_turnin_quest(quest_id):
        await cmd.ensure_turn_in_quest(quest_id)
        return
    
    if cmd.is_not_in_map(map_name):
        await cmd.join_map(map_name, room_number)
    
    await cmd.jump_to_monster(monster_name)

    while cmd.is_still_connected():
        if cmd.can_turnin_quest(quest_id):
            await cmd.leave_combat()
            await cmd.ensure_turn_in_quest(quest_id)
            return
        
        await attack_script(cmd, monster_name, hunt, skill_list)
        await cmd.sleep(200)

async def quest_item_req(cmd: Command, map_name: str, item_name: str, qty: int = 1, monster: str = "*", is_temp: bool = True):    
    if cmd.is_not_in_map(map_name):
        await cmd.join_map(map_name)

    while cmd.is_still_connected():
        if cmd.is_in_inventory(item_name, qty, operator=">=", isTemp=is_temp):
            cmd.leave_combat()
            return
        await attack_script(cmd, monster)

        
async def attack_script(cmd: Command, monster_name: str = "*", hunt: bool = False,
                        skill_list: list[int] = DEFAULT_SKILL_LIST):
    """One scheduler tick: cast whichever listed skill is ready.

    Callers already loop on this, so it deliberately performs a single cast
    instead of replaying the whole fixed rotation each pass -- replaying it
    meant every pass re-attempted skills that were still on cooldown.

    ``skill_list`` is the rotation to cast; the reference's advanced ``"1 | 4"``,
    for instance, is ``[0, 1, 4]`` here -- slot 0 is mandatory.
    """
    await cmd.use_next_skill(skill_list, monster_name, hunt)


def hunt_item_cmds(
        item_name: str, 
        item_qty: int, 
        map_name: str, 
        cell: str = None, 
        pad: str = "Left", 
        room_number: int = None, 
        monster_name: str = "*",
        most_monster: bool = False,
    ):
    label_done = f"Hunt for {item_name} [{item_qty}x] is done"
    lebel_farming = f"Farming for {item_name} [{item_qty}x]"
    if cell:
        jumpcmd = cmd.JumpCmd(cell, pad)
    else:
        jumpcmd = cmd.HuntMonsterCmd(monster_name, most_monster)
    return [
        # Check is item in bank
        cmd.IsInBankCmd(item_name),
        cmd.BankToInvCmd(item_name),
        
        # Check is item qty already fullfiled
        cmd.IsInInvCmd(item_name, item_qty, operator=">="),
        cmd.ToLabelCmd(label_done),
        cmd.IsInInvCmd(item_name, item_qty, operator=">=", isTemp=True),
        cmd.ToLabelCmd(label_done),
        
        # Farming items
        cmd.IsNotInMapCmd(map_name),
        cmd.JoinMapCmd(map_name, room_number),
        jumpcmd,
        cmd.LabelCmd(lebel_farming),
        cmd.IsInInvCmd(item_name, item_qty, operator=">="),
        cmd.ToLabelCmd(label_done),
        cmd.IsInInvCmd(item_name, item_qty, operator=">=", isTemp=True),
        cmd.ToLabelCmd(label_done),
        *attack(monster_name),
        cmd.ToLabelCmd(lebel_farming),
        
        cmd.LabelCmd(label_done),
        cmd.SleepCmd(1000)
    ]

def hunt_monster_quest_temp_item(
        quest_id: int,
        map_name: str, 
        room_number: int = None, 
        monster_name: str = "*",
        most_monster: bool = False,
    ):
    """this function is used to do a quest required only one kind of temp item"""
    label_done = f"Hunt for quest [{quest_id}] is done"
    lebel_farming = f"Hunt for quest [{quest_id}]"
    label_stop = f"stopping quest {quest_id}"
    return [
        cmd.AcceptQuestCmd(quest_id),
        cmd.SleepCmd(1000),
        cmd.QuestNotInProgressCmd(quest_id),
        cmd.ToLabelCmd(label_stop),
        
        # Check is item qty already fullfiled
        cmd.CanTurnInQuestCmd(quest_id),
        cmd.ToLabelCmd(label_done),
        
        # Farming items
        cmd.IsNotInMapCmd(map_name),
        cmd.JoinMapCmd(map_name, room_number),
        cmd.HuntMonsterCmd(monster_name, most_monster),
        cmd.LabelCmd(lebel_farming),
        cmd.CanTurnInQuestCmd(quest_id),
        cmd.ToLabelCmd(label_done),
        *attack(monster_name),
        cmd.ToLabelCmd(lebel_farming),
        
        cmd.LabelCmd(label_done),
        cmd.TurnInQuestCmd(quest_id),
        cmd.LabelCmd(label_stop),
        cmd.SleepCmd(1000)
    ]
    
def attack(monster_name = "*"):
    return [cmd.UseSkillCmd(slot, monster_name) for slot in DEFAULT_SKILL_LIST]

def attack_len():
    return len(attack())