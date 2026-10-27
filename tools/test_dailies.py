"""``CoreDailies``: the helpers' contract and the not-ported list.

    python tools/test_dailies.py

Two things are guarded here.  First the order every daily goes through -- accept
before farming, report instead of returning quietly when the server refuses the
daily, and the reward picked by id on the turn-in.  Second the five dailies this
port cannot run yet: they must stay *named* in ``NOT_PORTED`` and must not exist
as callable stubs, so nothing looks ported when it is not.
"""
import asyncio
import inspect
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bot import core_dailies as dailies  # noqa: E402

failures = []
passed = 0


def check(label, got, want):
    global passed
    if got == want:
        passed += 1
    else:
        failures.append(f"{label}: got {got!r}, want {want!r}")


# --- stubs ------------------------------------------------------------------
class StubPlayer:
    def __init__(self, held=None, banked=None):
        self.held = dict(held or {})
        self.banked = dict(banked or {})
        self.INVENTORY = []

    def get_item_inventory(self, name):
        qty = self.held.get(name, 0)
        return type("Row", (), {"qty": qty})() if qty else None

    def get_item_bank(self, name):
        qty = self.banked.get(name, 0)
        return type("Row", (), {"qty": qty})() if qty else None


class StubBot:
    def __init__(self, held=None, banked=None):
        self.logs = []
        self.player = StubPlayer(held, banked)

    def log(self, *args):
        self.logs.append(" ".join(map(str, args)))


class StubQuest:
    """Just the two properties CheckDailyv2 reads."""

    def __init__(self, caps=None, requirements=()):
        self.reward_entries = [(0, name, cap) for name, cap in (caps or {}).items()]
        self.turn_in_requirements = [{"sName": name} for name in requirements]


class StubCommand:
    """Records the calls a daily makes, with the refusals switched from outside."""

    def __init__(self, accept=True, turn_in=True, held=None, banked=None,
                 quests=None):
        self.bot = StubBot(held, banked)
        self.quests = dict(quests or {})
        self.calls = []
        self.accept = accept
        self.turn_in = turn_in
        self.held = dict(held or {})
        self.banked = dict(banked or {})

    async def ensure_accept_quest(self, quest):
        self.calls.append(("accept", quest))
        return self.accept

    async def ensure_turn_in_quest(self, quest, item_id=-1):
        self.calls.append(("turnin", quest, item_id))
        return self.turn_in

    def add_drop(self, item):
        self.calls.append(("drop", item))

    async def join_map(self, name):
        self.calls.append(("join", name))

    async def jump_cell(self, cell, pad="Left"):
        self.calls.append(("cell", cell, pad))

    async def sleep(self, milliseconds):
        return None

    def is_in_bank(self, item, qty=1, operator=">="):
        return self.banked.get(item, 0) >= qty

    def is_in_inventory(self, item, qty=1, operator=">=", isTemp=False):
        return self.held.get(item, 0) >= qty

    def is_in_inventory_or_bank(self, item, qty=1, operator=">=", isTemp=False):
        return self.is_in_inventory(item, qty) or self.is_in_bank(item, qty)

    async def bank_to_inv(self, names):
        self.calls.append(("unbank", names))

    async def inv_to_bank(self, names):
        self.calls.append(("bank", names))

    async def has_item(self, item, qty=1, isTemp=False):
        return self.held.get(item, 0) >= qty

    async def has_item_id(self, item_id):
        return False

    async def is_completed_before(self, quest_id, timeout_sec: float = 3.0):
        return False

    def quest_in_progress(self, quest):
        return False

    def get_loaded_quest(self, quest):
        return self.quests.get(quest)

    def get_quest_rewards(self, quest):
        return []

    def is_still_connected(self):
        return True

    async def sell_item(self, item, qty=1):
        self.calls.append(("sell", item, qty))

    async def buy_item(self, *args, **kwargs):
        self.calls.append(("buy", args, kwargs))


def patch(**replacements):
    original = {name: getattr(dailies, name) for name in replacements}
    for name, value in replacements.items():
        setattr(dailies, name, value)
    return original


def restore(original):
    for name, value in original.items():
        setattr(dailies, name, value)


def run(coro):
    return asyncio.run(coro)


# ============================================================================
# 1. daily_routine -- accept, farm, turn in, and say so when refused
# ============================================================================
async def _noop_hunt(*args, **kwargs):
    _noop_hunt.calls.append((args, kwargs))


async def _noop_wait(*args, **kwargs):
    _noop_wait.calls.append((args, kwargs))


_noop_hunt.calls = []
_noop_wait.calls = []

saved = patch(hunt_item=_noop_hunt, wait_for_item=_noop_wait)
try:
    cmd = StubCommand()
    ok = run(dailies.daily_routine(cmd, 802, "arcangrove", "Gorillaphant",
                                   "Slain Gorillaphant", 50, cell="LeftBack",
                                   pad="Left", reward="Elders' Blood"))
    kinds = [call[0] for call in cmd.calls]
    check("routine ran", ok, True)
    check("routine order", kinds, ["accept", "drop", "join", "turnin"])
    check("routine hunted the item", _noop_hunt.calls[0][0][1], "Slain Gorillaphant")
    check("routine hunted the qty", _noop_hunt.calls[0][0][2], 50)
    check("routine held the cell", _noop_hunt.calls[0][1]["cell"], "LeftBack")
    check("routine waited for the reward",
          _noop_wait.calls[0][0][1], "Elders' Blood")

    # A refused daily must report and farm nothing.
    cmd = StubCommand(accept=False)
    _noop_hunt.calls.clear()
    ok = run(dailies.daily_routine(cmd, 802, "arcangrove", "Gorillaphant",
                                   "Slain Gorillaphant"))
    check("refused daily: not ok", ok, False)
    check("refused daily: no hunt", _noop_hunt.calls, [])
    check("refused daily: says why",
          any("cannot be accepted" in line for line in cmd.bot.logs), True)

    # --- chain_complete: accept then turn in with the chosen reward --------
    cmd = StubCommand()
    ok = run(dailies.chain_complete(cmd, 3319, 22332))
    check("chain complete ok", ok, True)
    check("chain complete order", [c[0] for c in cmd.calls], ["accept", "turnin"])
    check("chain complete reward id", cmd.calls[1][2], 22332)

    cmd = StubCommand(accept=False)
    ok = run(dailies.chain_complete(cmd, 592))
    check("chain refused: not ok", ok, False)
    check("chain refused: no turnin passed",
          [c[0] for c in cmd.calls], ["accept"])

    # --- check_dailyv2: cap from the quest's own iStk, drops whitelisted ---
    cmd = StubCommand(held={"Barium": 5})
    ok = run(dailies.check_dailyv2(cmd, 2091, any_item=False,
                                   items=("Barium", "Copper")))
    check("check daily ok", ok, True)
    check("check daily whitelisted", ("drop", ["Barium", "Copper"]) in cmd.calls,
          True)
    check("check daily unbanked the missing one",
          ("unbank", "Copper") in cmd.calls, True)

    # A banked copy is not unbanked here: the reference's `_item == null` test
    # counts the bank, so this branch only fires when the item is nowhere.
    cmd = StubCommand(banked={"Barium": 5})
    run(dailies.check_dailyv2(cmd, 2091, any_item=False, items=("Barium",)))
    check("check daily leaves a banked copy alone",
          [c for c in cmd.calls if c[0] == "unbank"], [])

    # --- the max-stack half, from the quest's own iStk --------------------
    quest = StubQuest(caps={"Elders' Blood": 20})
    cmd = StubCommand(held={"Elders' Blood": 20}, quests={802: quest})
    check("max stack: any=True stops",
          run(dailies.check_dailyv2(cmd, 802, items=("Elders' Blood",))), False)
    check("max stack: says why",
          any("maximum amount" in line for line in cmd.bot.logs), True)

    cmd = StubCommand(held={"Barium": 1000}, quests={2091: StubQuest(
        caps={"Barium": 1000, "Copper": 1000})})
    check("max stack: any=False runs while one is short",
          run(dailies.check_dailyv2(cmd, 2091, any_item=False,
                                    items=("Barium", "Copper"))), True)

    cmd = StubCommand(held={"Barium": 1000, "Copper": 1000}, quests={2091: StubQuest(
        caps={"Barium": 1000, "Copper": 1000})})
    check("max stack: any=False stops when all are full",
          run(dailies.check_dailyv2(cmd, 2091, any_item=False,
                                    items=("Barium", "Copper"))), False)

    # A cap the payload does not carry is not guessed: the daily runs and the
    # server has the last word.
    cmd = StubCommand(held={"Mystery": 9999}, quests={1234: StubQuest()})
    check("max stack: unknown cap runs",
          run(dailies.check_dailyv2(cmd, 1234, items=("Mystery",))), True)

    # The quest's own requirement names are whitelisted too.
    cmd = StubCommand(quests={1235: StubQuest(requirements=("Slain Gorillaphant",))})
    run(dailies.check_dailyv2(cmd, 1235))
    check("check daily whitelists requirements",
          ("drop", ["Slain Gorillaphant"]) in cmd.calls, True)

    # --- a refused daily stops the loop instead of spinning ----------------
    # ``mine_crafting`` asks for one turn-in per metal; the second is refused
    # once the daily is spent, so the loop has to stop there.
    async def _noop_equip(cmd_, solo=False):
        return True

    saved_loop = patch(hunt_item=_noop_hunt, wait_for_item=_noop_wait,
                       equip_class=_noop_equip)
    try:
        cmd = StubCommand(turn_in=False)
        run(dailies.mine_crafting(cmd, metals=("Barium", "Copper"), quant=2))
        check("mine crafting: one turn-in per day only",
              [c for c in cmd.calls if c[0] == "turnin"],
              [("turnin", 2091, 11932)])
        check("mine crafting: says why it stopped",
              any("one turn-in per day" in line for line in cmd.bot.logs), True)
    finally:
        restore(saved_loop)

    # ``monthly_treasure_chest_keys`` loops while keys and chests are held; a
    # chest quest that refuses must break it.
    cmd = StubCommand(held={"Treasure Chest": 1,
                            "Magic Treasure Chest Key": 1},
                      quests={1238: StubQuest()})
    cmd.bot.player.is_member = True
    calls = []

    async def refusing_chain(cmd_, quest, item_id=-1):
        calls.append(quest)
        return False

    saved_chain = dailies.chain_complete
    dailies.chain_complete = refusing_chain
    try:
        run(dailies.monthly_treasure_chest_keys(cmd, log=False))
    finally:
        dailies.chain_complete = saved_chain
    check("monthly keys: the chest loop stops after one refusal", calls, [1238])
    check("monthly keys: says why it stopped",
          any("stops here before it can spin" in line for line in cmd.bot.logs),
          True)

    # --- not_ported: named, with its reason --------------------------------
    cmd = StubCommand()
    dailies.not_ported(cmd, "friendships")
    line = cmd.bot.logs[-1]
    check("not ported names it", "friendships" in line, True)
    check("not ported gives the reason",
          "extension-packet listener" in line, True)
finally:
    restore(saved)

# ============================================================================
# 2. elders_blood -- stops at the 20 cap without touching the quest
# ============================================================================
saved = patch(hunt_item=_noop_hunt, wait_for_item=_noop_wait)
try:
    cmd = StubCommand(held={"Elders' Blood": 20})
    run(dailies.elders_blood(cmd))
    check("at max: no accept", cmd.calls, [])
finally:
    restore(saved)

# ============================================================================
# 3. the not-ported list is honest
# ============================================================================
for name in ("nsod_daily", "break_intothe_hoard", "friendships"):
    check(f"{name} is listed", name in dailies.NOT_PORTED, True)
    check(f"{name} has a reason",
          bool(dailies.NOT_PORTED.get(name)), True)
    check(f"{name} is not a callable stub", hasattr(dailies, name), False)

# ...and the ones that had to wait for HuntMonsterQuest are real now.
for name in ("elden_ruby", "enchanted_dark_blood"):
    check(f"{name} is ported", hasattr(dailies, name), True)

# Every exported daily is async and takes the Command first.
for name in dir(dailies):
    if name.startswith("_") or name in ("not_ported",):
        continue
    value = getattr(dailies, name)
    if not inspect.iscoroutinefunction(value):
        continue
    params = list(inspect.signature(value).parameters)
    check(f"{name} takes cmd first", params[0] if params else None, "cmd")

# --- "Missing Badge" -------------------------------------------------------
# Quest 802's turn-in was refused with "Missing Badge" on a live account: the
# daily must then be skipped instead of farming fifty gorillaphants again.
badge = StubCommand()
badge.bot.missing_badge_questid = [802]
check("badge refusal: the daily is skipped, not farmed",
      run(dailies.check_dailyv2(badge, 802, items=("Elders' Blood",))), False)
check("badge refusal: nothing is accepted or hunted", badge.calls, [])
check("badge refusal: it says why",
      any("does not have" in line for line in badge.bot.logs), True)

elders = StubCommand()
elders.bot.missing_badge_questid = [802]
run(dailies.elders_blood(elders))
check("badge refusal: Elders' Blood accepts nothing",
      [call for call in elders.calls if call[0] == "accept"], [])

print(f"passed {passed}   failed {len(failures)}")
if failures:
    for line in failures:
        print("FAIL", line)
    raise SystemExit(1)
print("dailies tests OK")
