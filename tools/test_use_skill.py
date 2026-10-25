"""Integration test: drive the real ``Command.use_skill`` with a stub bot.

``tools/test_skill.py`` covers the model. This covers the *branching* in
``use_skill`` that the model feeds -- ``skill.target`` and ``skill.max_targets``
-- by running the actual coroutine and asserting on which packet it would have
sent. Nothing here touches the network: ``Bot.use_skill_to_*`` are replaced
with recorders.

Run:  python tools/test_use_skill.py
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.command import Command, SkillMode  # noqa: E402
from core.player import Player  # noqa: E402
from model import ItemInventory, ItemType, Monster, Skill  # noqa: E402

ok = 0
failures = []


def check(label: str, got, want) -> None:
    global ok
    if got == want:
        ok += 1
    else:
        failures.append(f"{label}: got {got!r}, want {want!r}")


# --- stubs ------------------------------------------------------------------
class Recorder:
    """Stands in for Bot, capturing what would go on the wire."""

    def __init__(self, monsters, skills):
        self.calls: list[tuple] = []
        self.monsters = monsters
        self.spam_backoff_ms = 0
        self.skillAnim = None
        self.scroll_id = 12917
        self.player = Player()
        self.player.SKILLS = skills
        self.player.CELL = "1"
        self.player.PAD = "1"
        self.player.CURRENT_HP = 1000
        self.player.MAX_HP = 1000
        self.player.MANA = 500
        self.player.ISDEAD = False
        self.player.ManaCost = 1.0
        self.player.CDREDUCTION = 0.0
        self.player.LOGINUSERID = 1

    # what use_skill calls out to -------------------------------------------
    def use_skill_to_monster(self, skill, monsters_id, max_target):
        self.calls.append(("monster", skill, tuple(monsters_id), max_target))

    def use_skill_to_player(self, skill, max_target):
        self.calls.append(("player", skill, max_target))

    def use_skill_to_myself(self, skill):
        self.calls.append(("myself", skill))

    def use_scroll(self, monsters_id, max_target):
        # Mirrors Bot.use_scroll: the fired id is bot.scroll_id, not an argument.
        self.calls.append(("scroll", tuple(monsters_id), max_target,
                           self.scroll_id))

    def use_potion(self, potion_id):
        # Mirrors Bot.use_potion: i1>p:<charId>%<itemId>% -- the item slot.
        self.calls.append(("potion", potion_id))

    def debug(self, *_a, **_k):
        pass

    def write_message(self, *_a, **_k):
        pass

    def jump_cell(self, *_a, **_k):
        pass


class FakeCommand(Command):
    """Command with the decorator's connection guards satisfied."""

    def __init__(self, bot):
        self.bot = bot
        self.last_skill_cast_ms = 0

    def is_player_alive(self):
        return not self.bot.player.ISDEAD

    def is_still_connected(self):
        return True

    async def sleep(self, milliseconds: int):
        # Never actually sleep in a test; just record the pacing request.
        self.paced.append(milliseconds)

    paced: list[int] = []


def make_monster(mon_map_id: str, frame: str, alive: bool = True) -> Monster:
    m = Monster({
        "MonMapID": mon_map_id, "MonID": "1", "strMonName": "Black Flame",
        "intState": 1 if alive else 0, "intHP": 100, "intHPMax": 100,
        "frame": frame,
    })
    # Monster's constructor reads intState; force frame/alive explicitly so the
    # test does not depend on which payload keys it happens to honour.
    m.frame = frame
    m.is_alive = alive
    m.mon_name = "Black Flame"
    return m


# --- the real Legion Revenant loadout, verbatim from sAct --------------------
def loadout() -> list[Skill]:
    return [Skill(s) for s in (
        {"nam": "aa", "typ": "aa", "ref": "aa", "tgt": "h", "tgtMax": 3,
         "tgtMin": 1, "mp": -15, "cd": 1500, "id": 1558},
        {"nam": "Atramentous Shade", "typ": "m", "ref": "a1", "tgt": "h",
         "tgtMax": 3, "tgtMin": 1, "mp": 10, "cd": 6000, "id": 1559},
        {"nam": "Bone Besieger", "typ": "m", "ref": "a2", "tgt": "h",
         "tgtMax": 3, "tgtMin": 1, "mp": 15, "cd": 6000, "id": 1560},
        {"nam": "Legion Feast", "typ": "m", "ref": "a3", "tgt": "f",
         "tgtMax": 7, "tgtMin": 1, "mp": 15, "cd": 6000, "id": 1561},
        {"nam": "Unrelenting", "typ": "m", "ref": "a4", "tgt": "h",
         "tgtMax": 3, "tgtMin": 1, "mp": 20, "cd": 12000, "id": 1562},
        {"nam": None, "typ": "i", "ref": "i1", "tgt": "f", "tgtMax": None,
         "tgtMin": None, "mp": 0, "cd": 60000, "id": None},
    )]


def setup(monsters):
    rec = Recorder(monsters, loadout())
    cmd = FakeCommand(rec)
    for s in rec.player.SKILLS:
        s.next_use = datetime.now()
    return rec, cmd


def run(coro):
    return asyncio.run(coro)


# ============================================================================
# 1. hostile skill + a monster in the cell -> monster packet, correct targets
# ============================================================================
mons = [make_monster("10", "1"), make_monster("11", "1"), make_monster("12", "2")]
rec, cmd = setup(mons)
sent = run(cmd.use_skill(1, "*", False, SkillMode.ALL))
check("h skill with monsters: returned", sent, True)
check("h skill with monsters: one packet", len(rec.calls), 1)
check("h skill: routed to monsters", rec.calls[0][0], "monster")
check("h skill: cell-1 targets only", rec.calls[0][2], ("10", "11"))
check("h skill: max_target 3", rec.calls[0][3], 3)
check("h skill: cooldown armed",
      rec.player.SKILLS[1].next_use > datetime.now(), True)
check("h skill: skillAnim set", rec.skillAnim, rec.player.SKILLS[1].get("anim"))


# ============================================================================
# 2. the int(None) regression: scroll slot has tgtMax = None
# ----------------------------------------------------------------------------
# As sAct ships it (no scroll equipped yet) slot 5 has tgt="f".  With an item
# equipped in the potion slot that slot *is* the item, so it goes out as
# i1>p:<charId>%<itemId>% (the Vigil packet) rather than a5>p:<charId>; with
# nothing equipped it keeps the class-skill packet.  Either way the old
# `int(skill.get("tgtMax", 1))` ran BEFORE either branch and raised int(None).
# ============================================================================
rec, cmd = setup([make_monster("10", "1")])
try:
    sent = run(cmd.use_skill(5, "*", False, SkillMode.ALL))
    check("scroll slot does not raise", "no exception", "no exception")
except TypeError as exc:
    check("scroll slot does not raise", f"TypeError {exc}", "no exception")
check("slot 5 (tgt=f) with an item equipped: item packet",
      rec.calls[0][0], "potion")
check("slot 5: fires bot.scroll_id", rec.calls[0][1], 12917)
check("slot 5: returned", sent, True)

# Nothing equipped -> the slot is not an item and keeps the class-skill packet.
rec, cmd = setup([make_monster("10", "1")])
rec.scroll_id = ""
sent = run(cmd.use_skill(5, "*", False, SkillMode.ALL))
check("slot 5 (tgt=f) with no item: player branch", rec.calls[0][0], "player")
check("slot 5: max_target fell back to 1", rec.calls[0][2], 1)
check("slot 5: returned with no item", sent, True)

# ...and the old expression really did raise, so this is a genuine fix
try:
    int(loadout()[5].get("tgtMax", 1))
    check("old int(tgtMax) raised", "no exception", "TypeError")
except TypeError:
    check("old int(tgtMax) raised", "TypeError", "TypeError")

# After `seia` re-points slot 5 at a hostile target it reaches use_scroll.
rec, cmd = setup([make_monster("10", "1"), make_monster("11", "1")])
rec.player.SKILLS[5]["tgt"] = "h"
rec.player.SKILLS[5]["tgtMax"] = None          # seia does not send tgtMax
sent = run(cmd.use_skill(5, "*", False, SkillMode.ALL))
check("hostile slot 5: returned", sent, True)
check("hostile slot 5: routed to scroll", rec.calls[0][0], "scroll")
check("hostile slot 5: targets cell monsters", rec.calls[0][1], ("10", "11"))
check("hostile slot 5: max_target fell back to 1", rec.calls[0][2], 1)
check("hostile slot 5: default scroll id", rec.calls[0][3], 12917)

# ...and the scroll fired is bot.scroll_id (set by equip_scroll), not a
# per-call argument -- exactly how bot/templeshrine drives it.
rec, cmd = setup([make_monster("10", "1")])
rec.player.SKILLS[5]["tgt"] = "h"
sent = run(cmd.use_skill(5, "*", False, SkillMode.ALL))
check("scroll fired is bot.scroll_id", rec.calls[0][3], 12917)

# The removed keyword must be rejected loudly rather than silently ignored.
rec, cmd = setup([make_monster("10", "1")])
try:
    run(cmd.use_skill(5, "*", False, SkillMode.ALL, scroll_id=99999))
    check("scroll_id kwarg rejected", "no exception", "TypeError")
except TypeError:
    check("scroll_id kwarg rejected", "TypeError", "TypeError")


# ============================================================================
# 3. friendly skill -> player packet, never a monster packet
# ============================================================================
rec, cmd = setup([make_monster("10", "1")])
sent = run(cmd.use_skill(3, "*", False, SkillMode.ALL))
check("f skill: returned", sent, True)
check("f skill: routed to player", rec.calls[0][0], "player")
check("f skill: uses tgtMax 7", rec.calls[0][2], 7)
check("f skill: only one packet", len(rec.calls), 1)


# ============================================================================
# 4. skill_mode filters: the packet never goes out, and is NOT counted as a cast
# ============================================================================
rec, cmd = setup([make_monster("10", "1")])
armed = rec.player.SKILLS[1].next_use          # captured before the call
sent = run(cmd.use_skill(1, "*", False, SkillMode.BUFF_ONLY))
check("ATTACK_ONLY-style slot under BUFF_ONLY: refused", sent, False)
check("BUFF_ONLY: nothing sent", rec.calls, [])
check("BUFF_ONLY: cooldown NOT armed",
      rec.player.SKILLS[1].next_use == armed, True)

rec, cmd = setup([make_monster("10", "1")])
sent = run(cmd.use_skill(3, "*", False, SkillMode.ATTACK_ONLY))
check("friendly slot under ATTACK_ONLY: refused", sent, False)
check("ATTACK_ONLY: nothing sent", rec.calls, [])

rec, cmd = setup([make_monster("10", "1")])
sent = run(cmd.use_skill(1, "*", False, SkillMode.NONE))
check("SkillMode.NONE: refused", sent, False)
check("SkillMode.NONE: nothing sent", rec.calls, [])

# buff_only=True shorthand wins over skill_mode
rec, cmd = setup([make_monster("10", "1")])
sent = run(cmd.use_skill(3, "*", False, SkillMode.ALL, buff_only=True))
check("buff_only shorthand allows f skill", sent, True)


# ============================================================================
# 5. empty cell -> refused, nothing sent, cooldown untouched
# ============================================================================
rec, cmd = setup([])                       # no monsters at all
armed = rec.player.SKILLS[1].next_use
sent = run(cmd.use_skill(1, "*", False, SkillMode.ALL))
check("empty cell: refused", sent, False)
check("empty cell: nothing sent", rec.calls, [])
check("empty cell: cooldown untouched",
      rec.player.SKILLS[1].next_use == armed, True)

# monster present but on ANOTHER cell
rec, cmd = setup([make_monster("10", "9")])
sent = run(cmd.use_skill(1, "*", False, SkillMode.ALL))
check("wrong cell: refused", sent, False)
check("wrong cell: nothing sent", rec.calls, [])

# monster in cell but dead
rec, cmd = setup([make_monster("10", "1", alive=False)])
sent = run(cmd.use_skill(1, "*", False, SkillMode.ALL))
check("dead monster: refused", sent, False)
check("dead monster: nothing sent", rec.calls, [])


# ============================================================================
# 6. targeting filters: id.<n> and bare names
# ============================================================================
rec, cmd = setup([make_monster("10", "1"), make_monster("11", "1")])
sent = run(cmd.use_skill(1, "id.11", False, SkillMode.ALL))
check("id.11: cast", sent, True)
# target_monsters is a *preference*, not a filter: priority goes first and the
# rest of the cell follows (unchanged from HEAD, see Step 3 in use_skill).
check("id.11: priority first, rest after", rec.calls[0][2], ("11", "10"))

# An id that matches nothing still fights whatever is in the cell. This is
# pre-existing behaviour -- assert it so a future "strict filter" change is a
# deliberate decision rather than an accident.
rec, cmd = setup([make_monster("10", "1")])
sent = run(cmd.use_skill(1, "id.99", False, SkillMode.ALL))
check("unknown id: falls back to cell", rec.calls[0][2], ("10",))
check("unknown id: still cast", sent, True)

# ...but an empty cell refuses outright, whatever the filter said.
rec, cmd = setup([])
sent = run(cmd.use_skill(1, "id.99", False, SkillMode.ALL))
check("unknown id + empty cell: refused", sent, False)
check("unknown id + empty cell: nothing sent", rec.calls, [])

rec, cmd = setup([make_monster("10", "1")])
sent = run(cmd.use_skill(1, "black flame", False, SkillMode.ALL))   # name match
check("name target: cast", sent, True)
check("name target: resolved to id", rec.calls[0][2], ("10",))


# ============================================================================
# 7. mana gate (skill 4 costs 20; auto-attack is free even at 0 mana)
# ============================================================================
rec, cmd = setup([make_monster("10", "1")])
rec.player.MANA = 0
sent = run(cmd.use_skill(4, "*", False, SkillMode.ALL))
check("0 mana blocks a 20-mana skill", sent, False)
check("0 mana: nothing sent", rec.calls, [])

rec, cmd = setup([make_monster("10", "1")])
rec.player.MANA = 0
sent = run(cmd.use_skill(0, "*", False, SkillMode.ALL))
check("auto-attack free at 0 mana (mp=-15)", sent, True)


# ============================================================================
# 8. cooldown gate: a still-cooling slot is refused by canUseSkill
# ============================================================================
rec, cmd = setup([make_monster("10", "1")])
rec.player.SKILLS[4].next_use = datetime.now() + timedelta(seconds=6)
sent = run(cmd.use_skill(4, "*", False, SkillMode.ALL))
check("cooling slot: refused", sent, False)
check("cooling slot: nothing sent", rec.calls, [])

rec, cmd = setup([make_monster("10", "1")])
rec.player.SKILLS[4].next_use = datetime.now() - timedelta(seconds=1)
sent = run(cmd.use_skill(4, "*", False, SkillMode.ALL))
check("expired cooldown: cast", sent, True)


# ============================================================================
# 9. out-of-range and empty-loadout slots must refuse, not raise
# ============================================================================
rec, cmd = setup([make_monster("10", "1")])
try:
    sent = run(cmd.use_skill(9, "*", False, SkillMode.ALL))
    check("slot 9 (absent): refuses not raises", sent, False)
except IndexError as exc:
    check("slot 9 (absent): refuses not raises", f"IndexError {exc}", False)

rec = Recorder([make_monster("10", "1")], [])
cmd = FakeCommand(rec)
try:
    sent = run(cmd.use_skill(0, "*", False, SkillMode.ALL))
    check("empty loadout: refuses not raises", sent, False)
except IndexError as exc:
    check("empty loadout: refuses not raises", f"IndexError {exc}", False)


# ============================================================================
# 10. a padded/empty Skill (the seia fallback) must refuse, not raise
# ============================================================================
rec, cmd = setup([make_monster("10", "1")])
rec.player.SKILLS.append(Skill())          # what the seia padding creates
try:
    sent = run(cmd.use_skill(6, "*", False, SkillMode.ALL))
    check("padded Skill: no KeyError/TypeError", "ok", "ok")
except (KeyError, TypeError) as exc:
    check("padded Skill: no KeyError/TypeError", repr(exc), "ok")


# ============================================================================
# 11. the check_alive wrapper must not cast when the session is gone
# ----------------------------------------------------------------------------
# A *dead but connected* player is deliberately NOT asserted here: check_alive
# blocks up to 11 s, respawns, and then casts, which is the correct behaviour
# but takes 11 s to observe.  What matters for use_skill is that a disconnected
# session yields no packet rather than an exception.
# ============================================================================
rec, cmd = setup([make_monster("10", "1")])
rec.player.ISDEAD = True                    # check_alive only checks the
cmd.is_still_connected = lambda: False       # connection on the dead path
armed = rec.player.SKILLS[1].next_use
sent = run(cmd.use_skill(1, "*", False, SkillMode.ALL))
check("disconnected: nothing sent", rec.calls, [])
check("disconnected: returns None (no cast)", sent, None)
check("disconnected: cooldown untouched",
      rec.player.SKILLS[1].next_use == armed, True)


# ============================================================================
# 12. class-safety conditions still run (Legion Revenant is not gated)
# ============================================================================
rec, cmd = setup([make_monster("10", "1")])
rec.player.INVENTORY = []                  # no equipped class -> always safe
sent = run(cmd.use_skill(1, "*", False, SkillMode.ALL))
check("no equipped class: safe", sent, True)

rec, cmd = setup([make_monster("10", "1")])
cls = ItemInventory({
    "sName": "Legion Revenant", "sType": ItemType.CLASS.value,
    "sES": ItemType.CLASS.value, "bEquipped": True, "iQty": 1, "iLvl": 1,
    "iRty": 1, "iDPS": 0, "iRng": 0, "iStk": 1, "bUpg": False,
})
rec.player.INVENTORY = [cls]
sent = run(cmd.use_skill(1, "*", False, SkillMode.ALL))
check("Legion Revenant not gated by conditions", sent, True)


print("=" * 74)
for line in failures:
    print("FAIL", line)
print(f"passed {ok}   failed {len(failures)}")
print("=" * 74)
sys.exit(1 if failures else 0)
