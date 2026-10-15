"""join_map has to wait for the map to change, or the caller re-sends the join.

A transfer packet is not a join.  ``Command.is_not_in_map`` compares against the
map name the client reports in ``moveToArea``, which lands *after* the server's
"You joined" chat line -- so a caller that loops on ``is_not_in_map`` (every farm
in ``bot/`` does) used to fire the transfer a second time and collect "Cannot
join a room you are already in".  That warning showed up in a live log two
seconds after the join.

Drives the real coroutines against a stub client that confirms the transfer a
moment later, the way the live server does.

Run:  python tools/test_join_map.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.command import Command                      # noqa: E402

PASS = 0
FAIL = 0


def check(label: str, got, want, extra: str = "") -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok   {label}   [{got}]" if extra == "" else
              f"  ok   {label}   [{extra}]")
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, want {want!r} {extra}")


class StubPlayer:
    USER = "Tester"
    CELL = "Enter"          # already parked on the spawn pad, so jump_cell no-ops
    PAD = "Spawn"
    ISDEAD = False


class StubBot:
    """A client that only reports the new map once the server has answered."""

    def __init__(self, map_name: str = "battleon", answers: bool = True):
        self.strMapName = map_name
        self.player = StubPlayer()
        self.is_client_connected = True
        self.roomNumber = None
        self.areaId = "battleon-1"
        self.is_joining_map = False
        self.is_aggro_handler_task_running = False
        self.aggro_mons_id = []
        self.accept_quest = None            # only touched by is_still_connected
        self.sent: list[str] = []
        self.answers = answers
        self.pending: str | None = None

    # --- what the socket layer would do --------------------------------
    def write_message(self, msg: str) -> None:
        self.sent.append(msg)
        if "tfer" in msg or "house" in msg:
            self.pending = msg.split("%")[7].split("-")[0]

    def release(self) -> None:
        """The server confirmed the transfer: apply what it named."""
        if self.pending is not None and self.answers:
            self.strMapName = self.pending
            self.pending = None

    def transfers(self) -> list[str]:
        return [m for m in self.sent if "tfer" in m]

    # --- bits Command.join_map touches ---------------------------------
    async def ensure_leave_from_combat(self, always: bool = False) -> None:
        return None

    def jump_cell(self, cell: str, pad: str) -> None:
        self.sent.append(f"jump:{cell}")


async def _join_with_the_server_answering(cmd: Command, bot: StubBot,
                                          map_name: str, delay: float = 0.1):
    """Join ``map_name`` while a task confirms the transfer afterwards."""

    async def server():
        await asyncio.sleep(delay)
        bot.release()

    task = asyncio.ensure_future(server())
    try:
        await cmd.join_map(map_name, safeLeave=False)
    finally:
        await task


def main() -> int:
    print("=" * 74)
    print("join_map: one transfer per map change")
    print("=" * 74)

    # --- 1. already there: no packet at all ---------------------------
    print("\n-- already in the map --")
    bot = StubBot("evilwarnul")
    cmd = Command(bot)
    asyncio.run(cmd.join_map("evilwarnul", safeLeave=False))
    check("no transfer sent", bot.transfers(), [])

    # --- 2. one join, one packet, and the map is actually set ---------
    print("\n-- the server confirms the transfer --")
    bot = StubBot("battleon")
    cmd = Command(bot)
    asyncio.run(_join_with_the_server_answering(cmd, bot, "evilwarnul"))
    check("exactly one transfer", len(bot.transfers()), 1, str(bot.transfers()))
    check("map changed before join_map returned", bot.strMapName, "evilwarnul")

    # --- 3. the regression: the caller's guard must not re-fire -------
    # This is the live shape: `while is_not_in_map: join_map; continue`.
    print("\n-- the farm loop that used to send the join twice --")
    bot = StubBot("battleon")
    cmd = Command(bot)
    rounds = 0

    async def farm_loop():
        nonlocal rounds
        while cmd.is_not_in_map("evilwarnul") and rounds < 5:
            rounds += 1
            async def server():
                await asyncio.sleep(0.1)
                bot.release()
            task = asyncio.ensure_future(server())
            try:
                await cmd.join_map("evilwarnul", safeLeave=False)
            finally:
                await task

    asyncio.run(farm_loop())
    check("the loop ran once", rounds, 1)
    check("still exactly one transfer", len(bot.transfers()), 1,
          str(bot.transfers()))

    # --- 4. a server that never answers must not hang the caller ------
    print("\n-- the server never confirms --")
    bot = StubBot("battleon", answers=False)
    cmd = Command(bot)
    cmd.MAP_JOIN_TIMEOUT_MS = 200           # keep the bound out of the test
    asyncio.run(cmd.join_map("evilwarnul", safeLeave=False))
    check("one transfer, then it gives up", len(bot.transfers()), 1,
          str(bot.transfers()))
    check("map unchanged", bot.strMapName, "battleon")
    check("the caller can retry", cmd.is_not_in_map("evilwarnul"), True)

    # --- 5. wait_for_map answers for itself ---------------------------
    print("\n-- wait_for_map's own contract --")
    bot = StubBot("battleon")
    cmd = Command(bot)
    cmd.MAP_JOIN_TIMEOUT_MS = 200
    check("reports the timeout", asyncio.run(cmd.wait_for_map("evilwarnul")),
          False)
    bot.strMapName = "evilwarnul"
    check("reports the change", asyncio.run(cmd.wait_for_map("evilwarnul")),
          True)
    check("map compare is case-insensitive",
          asyncio.run(cmd.wait_for_map("EVILWARNUL")), True)

    print()
    print("=" * 74)
    print(f"passed {PASS}   failed {FAIL}")
    print("=" * 74)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
