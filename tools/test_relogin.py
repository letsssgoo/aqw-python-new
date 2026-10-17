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
import time
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

    # --- 4. a dead socket must not spin the reader ---------------------
    print("\n-- the socket answers nothing, instantly --")
    bot4 = Bot(isScriptable=True, autoRelogin=False)
    bot4.is_client_connected = True
    bot4.client_socket = None
    calls = []

    async def read_batch_async(conn):
        calls.append(time.monotonic())
        return []

    bot4.read_batch_async = read_batch_async
    asyncio.run(asyncio.wait_for(bot4.read_server_in_background(), timeout=10))
    check("the reader dropped the dead session", bot4.is_client_connected, False)
    check("it tried a few times, not thousands", len(calls), 3, str(len(calls)))
    print("  -> instant empty read x3 -> session dropped (no busy loop)")

    # --- 5. a failed connect is retried until the bot runs -------------
    print("\n-- the first connect fails --")
    bot5 = _stub_bot()
    attempts = {"n": 0}

    async def flaky_connect():
        attempts["n"] += 1
        if attempts["n"] == 1:
            bot5.is_client_connected = False        # the server refused
            return
        bot5.is_client_connected = True
        bot5.is_char_load_complete = True
        bot5.player.bank_load_finished = True

    bot5.connect_client = flaky_connect
    ran = []

    async def script(cmd):
        ran.append(True)
        bot5.auto_relogin = False

    asyncio.run(asyncio.wait_for(bot5.start_bot(script), timeout=10))
    check("the refused connect was retried", attempts["n"], 2, str(attempts["n"]))
    check("and the script then ran", ran, [True])
    print("  -> refused -> retry -> running")

    # --- 6. a server that never answers gives up, and says so ----------
    print("\n-- every connect fails --")
    bot6 = _stub_bot()
    tries = {"n": 0}

    async def never_connects():
        tries["n"] += 1
        bot6.is_client_connected = False

    bot6.connect_client = never_connects
    asyncio.run(asyncio.wait_for(bot6.start_bot(lambda cmd: None), timeout=10))
    check("attempts are capped", tries["n"], Bot.RELOGIN_MAX_ATTEMPTS + 1,
          str(tries["n"]))
    print("  -> capped, so the app layer can restart the pane")

    # --- 7. aggro keeps ONE handler task --------------------------------
    # can_we_aggro is asked once per farm-loop pass, and every call used to
    # create another handler: dozens of tasks each sending aggroMon twice a
    # second, which the server answers with a disconnect.
    print("\n-- start_aggro called from a farm loop --")
    bot7 = Bot(isScriptable=True, autoRelogin=False)
    cmd7 = bot7.command

    async def aggro_tasks():
        bot7.is_client_connected = True
        for _ in range(25):                      # a farm loop, asking every pass
            cmd7.start_aggro(["id.1", "id.2"])
        first = [t for t in asyncio.all_tasks()
                 if t.get_coro().__name__ == "aggro_handler_task"]
        cmd7.start_aggro(["id.9"])               # a different cell's monsters
        await asyncio.sleep(0.05)                # let the cancelled one end
        after = [t for t in asyncio.all_tasks()
                 if t.get_coro().__name__ == "aggro_handler_task"]
        cmd7.stop_aggro()
        return first, after

    first, after = asyncio.run(aggro_tasks())
    check("twenty-five calls, one handler", len(first), 1, str(len(first)))
    check("new ids replace it, not add", len(after), 1, str(len(after)))
    check("stop_aggro clears the ids", bot7.aggro_mons_id, [])
    print("  -> one task, replaced on change, quiet stop")

    print()
    print("=" * 74)
    print(f"passed {PASS}   failed {FAIL}")
    print("=" * 74)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
