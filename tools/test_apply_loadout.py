"""Test CoreUltra.apply_loadout(): order, slot pinning, and stopping on failure.

The rules under test are the ones stated in plan.md:

* class first (item name), gear second (enhancement name, slot pinned by the
  config field), scroll last;
* an empty scroll leaves whatever the previous boss put on;
* **any** failure stops the bot -- class in neither inventory nor bank, an
  enhancement that cannot be found, a missing scroll, an unknown boss key or
  an unknown slot -- and no further slot is attempted after it;
* once aborted, nothing else runs.

Equipment is stubbed because the subject is orchestration, not lookup: the
real ``equip_enhancement`` is covered by tools/test_enhancement.py and
tools/test_equip_level.py.

Run:  python tools/test_apply_loadout.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.ultra import config                            # noqa: E402
from bot.ultra.config import Enhance, Loadout           # noqa: E402
from bot.ultra.core_ultra import CoreUltra              # noqa: E402
from bot.ultra.daily import DailyUltra                  # noqa: E402
from core.command import Command                        # noqa: E402

PASS = 0
FAIL = 0


def check(label: str, got: Any, want: Any, extra: str = "") -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok   {label}" + (f"   [{extra}]" if extra else ""))
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, want {want!r} {extra}")


class StubPlayer:
    """Minimal player: carries the Scroll of Enrage stock the guard checks."""

    def get_item_inventory(self, name: str):
        return type("Item", (), {"qty": 999})()


class StubCommand(Command):
    """Records equipment calls and returns whatever the test scripted.

    ``script`` maps a call kind to the outcome for the next call of that kind;
    default is True (everything succeeds).
    """

    def __init__(self, script: Optional[dict] = None) -> None:
        self.script = script or {}
        self.calls: list[tuple] = []
        self.stops: list[str] = []
        self.bot = type("B", (), {
            "areaId": "test-1",
            "stop_bot": lambda s: None,
            "player": StubPlayer(),
        })()

    def _next(self, kind: str) -> bool:
        outcome = self.script.get(kind, True)
        if isinstance(outcome, list):
            return outcome.pop(0) if outcome else True
        return outcome

    async def equip_item(self, name: str) -> bool:
        self.calls.append(("class", name))
        return self._next("class")

    async def equip_enhancement(self, name: str, slot: str = "", **kw) -> bool:
        self.calls.append(("gear", slot, name, tuple(sorted(kw.items()))))
        return self._next(f"gear:{name}")

    async def equip_scroll(self, name: str) -> bool:
        self.calls.append(("scroll", name))
        return self._next("scroll")

    def stop_bot(self, msg: str = "") -> None:
        self.stops.append(msg)


class FakeDaily(DailyUltra):
    """DailyUltra with the four boss steps stubbed out.

    The real steps build a boss object and copy its abort flag up; here they
    just record, so the assertions below are about the *sequence* (order, and
    stopping after a failure) rather than about any one boss.  The real
    hand-off is covered separately, with an actual ``CoreUltra`` subclass
    that calls ``_abort``.
    """

    def __init__(self, cmd, index_class):
        super().__init__(cmd, index_class)
        self.ran: list[str] = []

    async def step_tyndarius(self):
        self.ran.append("tyndarius")

    async def step_engineer(self):
        self.ran.append("engineer")

    async def step_ezrajal(self):
        self.ran.append("ezrajal")

    async def step_warden(self):
        self.ran.append("warden")


def main() -> int:
    import asyncio

    print("=" * 74)
    print("apply_loadout: order, slot pinning, stop-on-failure")
    print("=" * 74)

    # --- 1. happy path: class, then gear in order, then scroll ----------
    print("\n-- success path (tyndarius, slot 2) --")
    cmd = StubCommand()
    ultra = CoreUltra(cmd, 2)
    lo = asyncio.run(ultra.apply_loadout("tyndarius"))
    check("returns the loadout", lo is not None, True)
    check("no abort", ultra.aborted, False)
    check("bot not stopped", cmd.stops, [])
    kinds = [c[0] for c in cmd.calls]
    check("class first, scroll last",
          kinds[0] == "class" and kinds[-1] == "scroll", True, str(kinds))
    check("class + 3 gear + scroll", len(cmd.calls), 5, str(cmd.calls))

    # --- 2. slot pinning: every gear call carries its config slot --------
    print("\n-- slot pinning (the field IS the slot) --")
    cmd = StubCommand()
    ultra = CoreUltra(cmd, 2)
    asyncio.run(ultra.apply_loadout("tyndarius"))
    slots = {c[1] for c in cmd.calls if c[0] == "gear"}
    check("gear slots pinned", slots, {"Weapon", "he", "ba"}, str(sorted(slots)))
    # 'Forge' alone spans three slots in the registry; the pin is what stops
    # equip_enhancement picking a weapon or cape by accident.
    helm = [c for c in cmd.calls if c[0] == "gear" and c[1] == "he"]
    check("helm call pinned to 'he'", len(helm), 1, str(helm))

    # --- 3. class missing: stop immediately, try no gear ----------------
    print("\n-- class in neither inventory nor bank --")
    cmd = StubCommand({"class": False})
    ultra = CoreUltra(cmd, 2)
    lo = asyncio.run(ultra.apply_loadout("tyndarius"))
    check("returns None", lo, None)
    check("aborted", ultra.aborted, True)
    check("stop_bot called once", len(cmd.stops), 1, str(cmd.stops))
    check("no gear attempted", [c[0] for c in cmd.calls], ["class"])

    # --- 4. enhancement missing: stop, later slots untouched ------------
    print("\n-- weapon enhancement not found --")
    cmd = StubCommand({"gear:Arcana's Concerto": False})
    ultra = CoreUltra(cmd, 2)
    lo = asyncio.run(ultra.apply_loadout("tyndarius"))
    check("returns None", lo, None)
    check("aborted", ultra.aborted, True)
    check("stop_bot names the enhancement",
          len(cmd.stops) == 1 and "Arcana's Concerto" in cmd.stops[0],
          True, str(cmd.stops))
    check("class equipped first", cmd.calls[0][0], "class")
    check("helm/cape/scroll never attempted",
          [c[0] for c in cmd.calls[1:]], ["gear"], str(cmd.calls))

    # --- 5. scroll missing: stop ----------------------------------------
    print("\n-- scroll not in inventory --")
    cmd = StubCommand({"scroll": False})
    ultra = CoreUltra(cmd, 2)
    lo = asyncio.run(ultra.apply_loadout("tyndarius"))
    check("returns None", lo, None)
    check("aborted", ultra.aborted, True)
    check("gear all attempted before the scroll fails",
          [c[0] for c in cmd.calls], ["class", "gear", "gear", "gear", "scroll"])

    # --- 6. no scroll configured -> equip_scroll is not called ----------
    print("\n-- loadout with scroll=None --")
    cmd = StubCommand()
    no_scroll = Loadout(cls="ArchPaladin", weapon="Valiance",
                        cape="Lament", helm="Forge")
    config.LOADOUTS["_test_no_scroll"] = {1: no_scroll}
    try:
        ultra = CoreUltra(cmd, 1)
        lo = asyncio.run(ultra.apply_loadout("_test_no_scroll"))
        check("returns loadout", lo is not None, True)
        check("no scroll call",
              [c[0] for c in cmd.calls], ["class", "gear", "gear", "gear"])
    finally:
        config.LOADOUTS.pop("_test_no_scroll", None)

    # --- 7. tier pinning passes level/rarity through --------------------
    print("\n-- Enhance(name, level=...) forwards its tier --")
    cmd = StubCommand()
    lo2 = Loadout(cls="ArchPaladin", weapon=Enhance("Awe Blast", level=100, rarity=7),
                  cape="Penitence", helm="Forge")
    config.LOADOUTS["_test_tier"] = {1: lo2}
    try:
        ultra = CoreUltra(cmd, 1)
        got = asyncio.run(ultra.apply_loadout("_test_tier"))
        check("returns loadout", got is not None, True)
        awe = [c for c in cmd.calls if c[0] == "gear" and c[2] == "Awe Blast"]
        check("level and rarity forwarded",
              awe and awe[0][3] == (("level", 100), ("rarity", 7)),
              True, str(awe))
    finally:
        config.LOADOUTS.pop("_test_tier", None)

    # --- 8. bare string gear forwards no kwargs -------------------------
    print("\n-- bare string forwards no tier kwargs --")
    cmd = StubCommand()
    ultra = CoreUltra(cmd, 1)
    asyncio.run(ultra.apply_loadout("tyndarius"))
    kw = [c[3] for c in cmd.calls if c[0] == "gear"]
    check("all bare-string calls have empty kwargs",
          all(k == () for k in kw), True, str(kw))

    # --- 9. unknown boss / unknown slot ---------------------------------
    print("\n-- unknown boss key --")
    cmd = StubCommand()
    ultra = CoreUltra(cmd, 1)
    lo = asyncio.run(ultra.apply_loadout("nosuchboss"))
    check("returns None", lo, None)
    check("aborted", ultra.aborted, True)
    check("nothing equipped", cmd.calls, [])
    check("message names the boss and the known keys",
          "nosuchboss" in cmd.stops[0] and "tyndarius" in cmd.stops[0],
          True, str(cmd.stops))

    print("\n-- boss exists but the slot does not (slot 5) --")
    cmd = StubCommand()
    ultra = CoreUltra(cmd, 5)
    lo = asyncio.run(ultra.apply_loadout("tyndarius"))
    check("returns None", lo, None)
    check("aborted", ultra.aborted, True)
    check("nothing equipped", cmd.calls, [])
    check("message names the slots it has", "has:" in cmd.stops[0],
          True, str(cmd.stops))

    # --- 10. already aborted: no further work ---------------------------
    print("\n-- already aborted --")
    cmd = StubCommand()
    ultra = CoreUltra(cmd, 2)
    ultra.aborted = True
    lo = asyncio.run(ultra.apply_loadout("tyndarius"))
    check("returns None immediately", lo, None)
    check("no calls made", cmd.calls, [])

    # --- 11. DailyUltra stops between bosses ----------------------------
    print("\n-- DailyUltra stops after an aborted boss --")
    cmd = StubCommand()
    runner = FakeDaily(cmd, 2)
    asyncio.run(runner.run())
    check("all four ran when nothing failed",
          runner.ran, ["tyndarius", "engineer", "ezrajal", "warden"])
    check("stopped with the completion message", len(cmd.stops), 1,
          str(cmd.stops))

    # run() must stop as soon as the runner's flag is set, whatever set it
    class FailEngineer(FakeDaily):
        async def step_engineer(self):
            await super().step_engineer()
            self.aborted = True
            self.cmd.stop_bot("engineer: boom")

    cmd = StubCommand()
    runner = FailEngineer(cmd, 2)
    asyncio.run(runner.run())
    check("stops after the boss that failed",
          runner.ran, ["tyndarius", "engineer"])
    check("later bosses skipped", "ezrajal" not in runner.ran, True)
    check("abort message propagated", cmd.stops, ["engineer: boom"])

    # ...and the production path for setting that flag: a real boss object
    # that calls _abort, reached through _run_one.
    class AbortingBoss(CoreUltra):
        """A boss whose loadout check fails: _abort then return, like run()."""

        async def run(self):
            self._abort("engineer: no loadout")

    class HalfRun(FakeDaily):
        async def step_engineer(self):
            self.ran.append("engineer")
            await self._run_one(AbortingBoss)

    cmd = StubCommand()
    runner = HalfRun(cmd, 2)
    asyncio.run(runner.run())
    check("_run_one carries a boss's abort flag up to the runner",
          runner.ran, ["tyndarius", "engineer"])
    check("boss's stop_bot is the only one", cmd.stops,
          ["engineer: no loadout"])

    # --- 12. get_loadout error messages are actionable ------------------
    print("\n-- KeyError contents --")
    try:
        config.get_loadout("tyndarius", 9)
        check("raises", False, True)
    except KeyError as e:
        msg = str(e)
        check("names the boss", "tyndarius" in msg, True, msg)
        check("lists the slots", "has:" in msg and "1" in msg, True, msg)

    try:
        config.get_solo_loadout("Some Unknown Class")
        check("raises", False, True)
    except KeyError as e:
        check("solo error lists known classes",
              "legion revenant" in str(e), True, str(e))

    print()
    print("=" * 74)
    print(f"passed {PASS}   failed {FAIL}")
    print("=" * 74)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
