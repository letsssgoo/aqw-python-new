"""Losing the socket must end the script and bring the bot back after a delay.

A farm loop that never checks the connection is the normal case, not the
exception: ``bot/``'s ``hunt_item`` sits in ``while cmd.is_not_in_map(...)``, and
``buy_item``'s join does the same.  When the socket was reset under one of those,
the script never returned, so ``start_bot`` never reached its relogin and the bot
simply stopped -- which is what the app and the browser dashboard showed.

Drives a real ``Bot`` with the login and the socket reader stubbed out, so
nothing touches the network.

Run:  python tools/test_relogin.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.bot import Bot                              # noqa: E402

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


def _stub_bot(auto_relogin: bool = True) -> Bot:
    """A Bot that logs in and reads nothing, without a socket."""
    bot = Bot(isScriptable=True, autoRelogin=auto_relogin)
    bot.RELOGIN_DELAY_S = 0.05          # the 35 s of the real thing
    bot.server_info = ("localhost", 1)
    bot.login = lambda *args: None

    async def connect_client():
        bot.is_client_connected = True
        bot.is_char_load_complete = True
        bot.player.bank_load_finished = True

    async def read_server_in_background():
        while bot.is_client_connected:
            await asyncio.sleep(0.01)

    bot.connect_client = connect_client
    bot.read_server_in_background = read_server_in_background
    bot.run_register_quest_task = lambda: None
    return bot


def main() -> None:
    print("=" * 74)
    print("relogin: a dropped socket ends the script and the bot comes back")
    print("=" * 74)

    # --- 1. a drop mid-script cancels it and relogins ------------------
    print("\n-- the socket dies while the script is hung --")
    bot = _stub_bot()
    runs, cancelled = [], []

    async def script(cmd):
        runs.append(len(runs) + 1)
        if len(runs) == 1:
            try:
                await asyncio.sleep(3600)        # a loop that never checks
            except asyncio.CancelledError:
                cancelled.append(True)
                raise
        else:
            bot.auto_relogin = False             # the second session ends here

    async def scenario():
        task = asyncio.create_task(bot.start_bot(script))
        await asyncio.sleep(0.3)                 # first session, script hung
        check("the script started", runs, [1])
        bot.is_client_connected = False          # the peer reset
        await asyncio.wait_for(task, timeout=10)

    asyncio.run(scenario())
    check("the hung script was cancelled", cancelled, [True])
    check("a second session ran", runs, [1, 2])
    check("the bot is stopped at the end", bot.is_client_connected, False)
    print("  -> drop -> script cancelled -> relogin -> second session")

    # --- 2. a script that finishes by itself is not cancelled -----------
    print("\n-- the script finishes on its own --")
    bot2 = _stub_bot(auto_relogin=False)
    done = []

    async def quick(cmd):
        done.append(True)

    asyncio.run(asyncio.wait_for(bot2.start_bot(quick), timeout=10))
    check("it ran once", done, [True])
    check("nothing relogged in (autoRelogin off)", bot2.is_client_connected,
          False)
    print("  -> finished -> stopped, no relogin asked for")

    # --- 3. a crashing script still surfaces ---------------------------
    print("\n-- the script raises --")
    bot3 = _stub_bot(auto_relogin=False)

    async def boom(cmd):
        raise RuntimeError("script blew up")

    try:
        asyncio.run(asyncio.wait_for(bot3.start_bot(boom), timeout=10))
        check("the error propagates", False, True)
    except RuntimeError as error:
        check("the error propagates", str(error), "script blew up")

    print()
    print("=" * 74)
    print(f"passed {PASS}   failed {FAIL}")
    print("=" * 74)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
