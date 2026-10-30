"""Shared harness for the Ultra V2 suites.

The checks live in three files so one run stays short:

    python tools/test_ultra_v2.py           # options, presets, potions, party
    python tools/test_ultra_v2_fights.py    # the four dailies
    python tools/test_ultra_v2_weeklies.py  # Drakath and Nulgath

Everything here is offline: the engine's packet layer is stubbed, so the suites
pin the parts that must not drift.
"""
import asyncio
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bot.ultra.v2 import enhancements, options, potions, presets, scrolls, sync  # noqa: E402,F401
from bot.ultra.v2.core import V2Core, WIPE_DEATHS  # noqa: E402,F401
from bot.ultra.v2.dailies import warden  # noqa: E402,F401
from bot.ultra.v2.registry import ORDER as V2_ORDER  # noqa: E402,F401
from bot.ultra.v2.registry import REGISTRY as V2_REGISTRY  # noqa: E402,F401

failures = []
passed = 0


def check(label, got, want):
    global passed
    if got == want:
        passed += 1
    else:
        failures.append(f"{label}: got {got!r}, want {want!r}")


def run(coro):
    return asyncio.run(coro)


def finish(name):
    print(f"passed {passed}   failed {len(failures)}")
    if failures:
        for line in failures:
            print("FAIL", line)
        raise SystemExit(1)
    print(f"{name} OK")


class _StubBot:
    """Just enough Bot to construct a runner: no socket, no packets."""

    def __init__(self):
        self.logs = []
        self.player = type("P", (), {
            "LEVEL": 100, "CELL": "Enter", "PAD": "Spawn", "ISDEAD": False,
            "AURAS": [], "MANA": 100, "MAX_MP": 100, "CURRENT_HP": 100,
            "MAX_HP": 100, "GOLD": 0,
        })()

    def log(self, *args):
        self.logs.append(" ".join(map(str, args)))


class _StubCommand:
    def __init__(self):
        self.bot = _StubBot()

    def is_still_connected(self):
        return True

    def is_monster_alive(self, target="*"):
        return False          # nothing is in the cell: the boss never appeared

    async def sleep(self, ms):
        # Yield to the loop: the skill engine polls until stop_skills cancels
        # it, and a sleep that returns without yielding starves the event loop
        # so the cancel never runs (a hung test, not a hung bot).
        await asyncio.sleep(0)

    def is_in_inventory_or_bank(self, name, qty=1, operator=">=", isTemp=False):
        return True

    def can_turnin_quest(self, quest_id):
        # Default stub: the drop is still missing, so a retry is expected.
        return getattr(self, "turnin_ready", False)


__all__ = [
    "asyncio", "pathlib", "sys", "REPO_ROOT", "enhancements", "options",
    "potions", "presets", "scrolls", "sync", "V2Core", "WIPE_DEATHS",
    "warden", "V2_ORDER", "V2_REGISTRY", "check", "run", "finish", "failures",
    "passed",
]
