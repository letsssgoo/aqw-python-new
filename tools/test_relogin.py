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

    # --- 2b. ...and a finished script does not relogin even with it on --
    # This is the class-quest case: the script turns the last quest in, logs
    # "obtained", and the old loop then asked for a relogin it had no use for.
    print("\n-- the script finishes with autoRelogin on --")
    bot2b = _stub_bot(auto_relogin=True)
    finished = []

    async def finished_script(cmd):
        finished.append(True)

    asyncio.run(asyncio.wait_for(bot2b.start_bot(finished_script), timeout=10))
    check("it ran once, and only once", finished, [True])
    check("no relogin was attempted", bot2b.is_client_connected, False)
    check("it says the script completed", bot2b.stop_reason, "completed")
    check("so a launcher leaves it stopped", bot2b.finished_cleanly(), True)
    print("  -> finished -> stopped, autoRelogin had nothing to do")

    # --- 2c. a dropped connection is *not* "finished" -------------------
    print("\n-- the socket drops, relogin is off --")
    bot2c = _stub_bot(auto_relogin=False)

    async def hung(cmd):
        await asyncio.sleep(3600)

    async def drop_scenario():
        task = asyncio.create_task(bot2c.start_bot(hung))
        await asyncio.sleep(0.2)
        bot2c.is_client_connected = False
        await asyncio.wait_for(task, timeout=10)

    asyncio.run(drop_scenario())
    check("a drop is reported as a drop", bot2c.stop_reason, "connection-lost")
    check("and it is not 'finished'", bot2c.finished_cleanly(), False)
    print("  -> dropped -> a launcher is right to start it again")

    # --- 2d. pressing stop ends the run where it is ---------------------
    # A stop used to only flip the connection flag: every helper returned
    # quietly and the script walked to its own end, printing each step -- the
    # whole Farmer Joe log scrolling past after the stop button.  The script
    # must end at the step it was on.
    print("\n-- the user stops the bot mid-script --")
    bot2d = _stub_bot(auto_relogin=True)
    stop_steps = []

    async def stopping_script(cmd):
        stop_steps.append("step 1")
        await cmd.sleep(60_000)          # it is parked in a real step
        stop_steps.append("step 2")      # ... which must never run

    async def stop_scenario():
        task = asyncio.create_task(bot2d.start_bot(stopping_script))
        await asyncio.sleep(0.3)
        bot2d.stop_bot(user_triggered=True)
        await asyncio.wait_for(task, timeout=10)

    asyncio.run(stop_scenario())
    check("stop: the script ends where it was", stop_steps, ["step 1"])
    check("stop: it is not reported as a dropped connection",
          bot2d.stop_reason, "completed")
    check("stop: so a launcher leaves it stopped", bot2d.finished_cleanly(), True)
    print("  -> stopped -> the remaining steps never run")

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

    # --- 6. a server that never answers keeps being retried -------------
    # The default is unlimited: a farm left alone for hours must not stop for
    # good.  A cap is per instance, for a caller that wants one.
    print("\n-- every connect fails --")
    check("unlimited by default", Bot.RELOGIN_MAX_ATTEMPTS, 0)

    bot6 = _stub_bot()
    bot6.RELOGIN_MAX_ATTEMPTS = 3
    tries = {"n": 0}

    async def never_connects():
        tries["n"] += 1
        bot6.is_client_connected = False

    bot6.connect_client = never_connects
    asyncio.run(asyncio.wait_for(bot6.start_bot(lambda cmd: None), timeout=10))
    check("a caller's cap is honoured", tries["n"], 4, str(tries["n"]))
    print("  -> unlimited unless a caller caps it")

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

    # --- 8. a stuck session is one that stops *sending* ----------------
    # Other players keep the socket receiving, so "no packets came back" cannot
    # see a bot that stands still casting at nothing: silence on our side is the
    # signal.
    print("\n-- the bot sends nothing while packets keep arriving --")
    bot8 = _stub_bot(auto_relogin=False)
    bot8.is_client_connected = True
    bot8.STALL_SECONDS = 3.0
    bot8.HEARTBEAT_SECONDS = 0
    bot8.last_send_ts = time.time() - 999        # silent for ages
    bot8.last_packet_ts = time.time()            # while others keep it busy
    asyncio.run(asyncio.wait_for(bot8._watch_loop(), timeout=10))
    check("silence on our side triggers it",
          bot8.relogin_reason.startswith("silent"), True, bot8.relogin_reason)
    check("and the session was ended", bot8.is_client_connected, False)

    print("\n-- the server stops answering --")
    bot9 = _stub_bot(auto_relogin=False)
    bot9.is_client_connected = True
    bot9.STALL_SECONDS = 3.0
    bot9.HEARTBEAT_SECONDS = 0
    bot9.last_packet_ts = time.time() - 999      # nothing back for ages
    bot9.last_send_ts = time.time()              # while we keep sending
    asyncio.run(asyncio.wait_for(bot9._watch_loop(), timeout=10))
    check("no answer for long enough triggers it",
          bot9.relogin_reason.startswith("no answer"), True, bot9.relogin_reason)
    print("  -> sending nothing, or getting nothing back, re-establishes")

    print("\n-- stuck while still sending (the /shadowblast shape) --")
    bot10 = _stub_bot(auto_relogin=False)
    bot10.is_client_connected = True
    bot10.STALL_SECONDS = 3.0
    bot10.HEARTBEAT_SECONDS = 0
    bot10.strMapName = "shadowblast"
    bot10.player.CELL = "Enter"

    async def busy_scenario():
        async def keep_busy():
            # Still retrying the jump, and others in the map keep the socket
            # receiving: both silence checks stay quiet, so only "nothing has
            # changed" can see this one.
            while bot10.is_client_connected:
                bot10.last_send_ts = time.time()
                bot10.last_packet_ts = time.time()
                await asyncio.sleep(0.2)

        busy = asyncio.ensure_future(keep_busy())
        try:
            await asyncio.wait_for(bot10._watch_loop(), timeout=10)
        finally:
            busy.cancel()

    asyncio.run(busy_scenario())
    check("no progress at all triggers it",
          bot10.relogin_reason.startswith("no progress"), True,
          bot10.relogin_reason)
    print("  -> nothing changing is enough, packets or not")

    # --- 8. the freeze reporter must survive the app's log redirector ---
    # ``faulthandler`` writes to ``sys.stderr`` and needs a real ``fileno()``;
    # the app replaces both streams with one that has none, so dumping the
    # stacks raised AttributeError and killed the reporter exactly when it was
    # needed.  It now formats the stacks itself.
    print("\n-- the freeze reporter behind the app's redirector --")
    import io
    import threading

    from core import bot as core_bot

    class _RedirectedStream(io.StringIO):
        def fileno(self):
            raise AttributeError(
                "'UnifiedThreadRedirector' object has no attribute 'fileno'")

    class _LiveTask:
        def done(self):
            return False

    class _StuckBot:
        is_client_connected = True
        tick_task = _LiveTask()
        loop_ticks = 7
        freeze_reported = 0.0
        strMapName = "twilightzone"
        username = "yuvy"
        player = type("_Player", (), {"CELL": "Enter"})()

    stuck = _StuckBot()
    core_bot._BOTS.add(stuck)
    old_out, old_err = sys.stdout, sys.stderr
    old_seconds = core_bot.LOOP_FREEZE_SECONDS
    stream = _RedirectedStream()
    core_bot.LOOP_FREEZE_SECONDS = 0.3
    sys.stdout = sys.stderr = stream
    reporter = threading.Thread(target=core_bot._freeze_watch, daemon=True)
    try:
        reporter.start()
        deadline = time.time() + 4.0
        while time.time() < deadline and "[watch]" not in stream.getvalue():
            time.sleep(0.1)
    finally:
        sys.stdout, sys.stderr = old_out, old_err
        core_bot.LOOP_FREEZE_SECONDS = old_seconds
        core_bot._BOTS.discard(stuck)
    report = stream.getvalue()
    check("the reporter outlived a stream without fileno()",
          reporter.is_alive(), True)
    check("it named the frozen bot and its map",
          "twilightzone/Enter" in report, True)
    check("it printed each thread's stack itself",
          "--- thread" in report, True)
    print("  -> no faulthandler: stacks are formatted and logged")

    print()
    print("=" * 74)
    print(f"passed {PASS}   failed {FAIL}")
    print("=" * 74)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
