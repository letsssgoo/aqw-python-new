import socket
from core.command import Command
from core.player import Player
from core.utils import normalize
import faulthandler
import json
import zlib
import base64
import time
import threading
import weakref
from typing import Awaitable, Callable, List, Optional
from xml.etree import ElementTree
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from colorama import Fore, Back, Style, init
import inspect
import asyncio
from model import Shop
from model import Monster
from model import ItemInventory, ItemType, Faction, PlayerArea
from model import Skill
from model import Quest, normalize_quest_id
from handlers import register_quest_task, death_handler_task, aggro_handler_task
import time
import traceback

#: Seconds to wait for the bank before a script starts anyway.  The bank load is
#: a single HTTP POST fired from the login packet that carries CHARID; it lands
#: within a second in practice.  The bound exists only so a session that never
#: sends that packet still runs, with a warning.
BANK_WAIT_TIMEOUT_S = 10

#: Seconds between losing the connection and logging back in.  The server keeps
#: the old session for a while after a peer reset, and a relogin inside that
#: window is refused -- which then looks like "the bot just stopped".
RELOGIN_DELAY_S = 35

#: How many relogin attempts a single ``start_bot`` makes before it gives up and
#: lets its thread end.  ``0`` means keep trying for as long as the bot is asked
#: to run: a farm left alone for hours must not stop for good because three
#: relogins in a row could not get through -- the delay grows instead (see
#: ``RELOGIN_DELAY_S`` and the cap below), so retrying stays cheap.
RELOGIN_MAX_ATTEMPTS = 0

#: The largest relogin delay, in seconds, once the attempts start adding up.
RELOGIN_MAX_DELAY_S = 300.0

#: A session that sends nothing at all for this long is treated as stuck and is
#: re-established, and so is one that receives nothing back for that long.
#: Sending nothing is the stronger signal: /shadowblast's "stuck at Enter" keeps
#: receiving packets -- other players in the map keep the socket busy -- while
#: the bot itself casts at nothing and never sends again, so "no packets
#: received" alone cannot see it.  ``0`` turns the check off.
STALL_SECONDS = 15 * 60

#: How often a running session says it is still alive, in seconds (0 = off).
HEARTBEAT_SECONDS = 15 * 60

#: A read that returns this fast, with nothing read, is a broken socket rather
#: than the reader's own one-second idle timeout.
READ_FAIL_FAST_S = 0.5

#: Consecutive fast failures before the session is dropped.  Looping straight
#: back on a dead socket is what let one orphaned reader eat a core.
READ_FAILURES_BEFORE_DROP = 3

#: A script that spins without awaiting freezes the whole event loop: the packet
#: reader, every task and ``_watch_loop`` (itself a task) stop with it, so the
#: 15-minute stall detector can never fire and the log says nothing at all --
#: the "stuck at Enter with no sign of life" a farm loop that never yields
#: produces.  Only another thread still runs, so one reports the freeze and
#: dumps the stack of the thread that is spinning.  ``0`` turns it off.
LOOP_FREEZE_SECONDS = 60.0

#: Bots the freeze reporter watches; weak so a discarded bot costs nothing.
_BOTS: 'weakref.WeakSet[Bot]' = weakref.WeakSet()
_freeze_thread_started = False


def _freeze_watch() -> None:
    """Report bots whose event loop has stopped ticking (a loop with no await)."""
    seen: dict[int, tuple[int, float]] = {}
    while True:
        time.sleep(max(1.0, LOOP_FREEZE_SECONDS / 4.0))
        now = time.time()
        for bot in list(_BOTS):
            if not bot.is_client_connected:
                seen.pop(id(bot), None)
                continue
            key = id(bot)
            ticks = bot.loop_ticks
            previous = seen.get(key)
            if previous is None or previous[0] != ticks:
                seen[key] = (ticks, now)
                continue
            frozen = now - previous[1]
            if frozen < LOOP_FREEZE_SECONDS:
                continue
            if now - bot.freeze_reported < LOOP_FREEZE_SECONDS:
                continue
            bot.freeze_reported = now
            try:
                where = f"{bot.strMapName}/{bot.player.CELL}"
            except Exception:
                where = "?"
            print(f"[watch] {bot.username or 'bot'}: no task has run for "
                  f"{frozen:.0f}s in {where}; the event loop is blocked by a "
                  f"loop that never awaits. Thread stacks:", flush=True)
            faulthandler.dump_traceback(all_threads=True)


def _start_freeze_watch() -> None:
    """Start the freeze reporter once per process."""
    global _freeze_thread_started
    if _freeze_thread_started or LOOP_FREEZE_SECONDS <= 0:
        return
    _freeze_thread_started = True
    threading.Thread(target=_freeze_watch, name="loop-freeze-watch",
                     daemon=True).start()


class Bot:
    #: See RELOGIN_DELAY_S: an attribute so a test can shorten it.
    RELOGIN_DELAY_S: float = RELOGIN_DELAY_S
    #: See RELOGIN_MAX_ATTEMPTS: likewise an attribute, for the same reason.
    RELOGIN_MAX_ATTEMPTS: int = RELOGIN_MAX_ATTEMPTS
    #: See STALL_SECONDS / HEARTBEAT_SECONDS: attributes so a test (or a caller)
    #: can shorten them.
    STALL_SECONDS: float = STALL_SECONDS
    HEARTBEAT_SECONDS: float = HEARTBEAT_SECONDS


    def __init__(
            self, 
            roomNumber: Optional[int] = None, 
            itemsDropWhiteList = [],
            cmdDelay: int = 1000,
            showLog: bool = True, 
            showDebug: bool = False,
            showChat: bool = True,
            autoRelogin: bool = False,
            followPlayer: str = "",
            slavesPlayer: List[str] = [],
            isScriptable: bool = False,
            farmClass: Optional[str] = None,
            soloClass: Optional[str] = None,
            restartOnAFK: bool = True,
            autoAdjustSkillDelay: bool = False,
            respawnCellPad: List[str] = [],
            muteSpamWarning: bool = False,
            antiMod: bool = True
            ):
        self.roomNumber = roomNumber
        self.showLog = showLog
        self.cmdDelay = cmdDelay
        self.showDebug = showDebug
        self.showChat = showChat
        #: The stall/heartbeat task of the current session.
        self.watch_task = None
        #: Bumped once a second by ``_tick_loop``.  The freeze reporter thread
        #: reads it: a number that stops moving means the event loop itself is
        #: blocked by a script spinning without an await, which no task on that
        #: loop -- the stall detector included -- can notice or report.
        self.loop_ticks = 0
        #: Last time the freeze reporter spoke about this bot.
        self.freeze_reported = 0.0
        #: Time of the last packet the server sent, and of the last one we sent,
        #: plus how many arrived/sent since the last heartbeat.  The stall
        #: detector and the heartbeat read these: sending nothing is what a stuck
        #: farm looks like, since other players keep the socket receiving.
        self.last_packet_ts = time.time()
        self.last_send_ts = time.time()
        self.packets_seen = 0
        self.packets_sent = 0
        self.items_drop_whitelist: list[str] = itemsDropWhiteList
        self.dropped_items: list[dict] = []
        self.auto_relogin = autoRelogin
        self.follow_player = followPlayer
        self.slaves_player = slavesPlayer
        self.isScriptable = isScriptable
        self.farmClass = farmClass
        self.soloClass = soloClass
        self.restart_on_afk = restartOnAFK
        self.respawn_cell_pad = respawnCellPad
        self.mute_spam_warning = muteSpamWarning
        self.anti_mod = antiMod
        #: Total deaths this session; the ultra party reads the delta to spot wipes.
        self.deaths = 0
        #: Where the player stood when it died: ``(map, cell, pad)``.  The death
        #: handler respawns the character a few seconds later, by which time the
        #: server has already moved it to the map's own spawn (cell
        #: ``Enter``) -- reading ``player.CELL`` there sends the bot back to
        #: Enter instead of the farm.
        self.death_cell_pad = None

        # autoRelogin is honoured as passed: the old force-disable only dodged a
        # stop_bot() in read_server_in_background() that read_batch() can never reach.
        
        self.is_char_load_complete= False
        self.is_joining_map = False
        self.is_client_connected = False
        self.is_script_paused = False
        self.is_paused = False
        self.was_paused = False
        self.taunt_error = False
        
        self.wait_ms = 0
        self.player = Player()
        self.cmds = []
        self.index = 0
        self.areaId = None
        #: The map name from ``moveToArea``; empty until the first one arrives,
        #: so anything that reads it before then (the stall watcher, a log line)
        #: sees a string rather than an AttributeError.
        self.strMapName = ""
        # Player identity in the current cell. These three used to be created
        # lazily inside extract_user_ids, so calling get_user_id() before the
        # first cell load raised AttributeError -- see extract_user_ids for the
        # user_id/username_id mix-up this also fixes.
        self.user_ids: list[str] = []
        self.username_id: str | None = None   # our own character id
        self.user_id: str | None = None       # alias of username_id, see extract_user_ids
        self.canuseskill = True
        self.skillAnim = None
        self.username = ""
        self.password = ""
        self.server = ""
        self.server_info: List[str] = []
        self.client_socket = None
        self.users_id_in_cell = []
        self.users_name_in_cell = []
        self.loaded_quest_datas = []
        self.failed_get_quest_datas = []
        self.aggro_mons_id = []
        self.aggro_delay_ms = 500
        #: Fishing: set by the ``castWait`` / ``CatchResult`` packets and read by
        #: ``bot.core_farms.fishing_rep``.
        self.fishing_cast_wait = False
        self.fishing_caught = False
        self.fishing_wait_ms = 0
        self.fishing_derp = False
        self.fishing_catch_result = {}
        #: Set when a monster respawned since the area packet that built the
        #: list; read by the hunts when their target cannot be found.
        self.monsters_stale = False
        #: The one aggro handler task.  ``Command.start_aggro`` is called from
        #: inside farm loops, so it must replace this task rather than add one.
        self.aggro_task = None
        self.loaded_shop_datas: List[Shop] = []
        self.registered_auto_quest_ids = []
        self.is_register_quest_task_running = False
        self.is_aggro_handler_task_running = False
        self.followed_player_cell = None
        self.subscribers = []
        self.scroll_id: str = ""
        self.battle_analyzer: bool = False

        self.auto_adjust_skill_delay = autoAdjustSkillDelay
        self.check_spam_time = None
        # Added on top of Command.MIN_SKILL_GAP_MS whenever the server says we
        # are acting too soon, and bled back off one step per quiet minute.
        # Starts at 0 so normal pacing is unaffected. This replaces the old
        # skill_delay_ms counter, which was written on a warning but never read
        # by any sleep, so autoAdjustSkillDelay could not slow anything down.
        self.spam_backoff_ms = 0

        self.missing_turn_in_item_questid: list[int] = [] # this mean quest is unlocked (green quest)
        self.missing_quest_progress_questid: list[int] = [] # this mean quest is locked (red quest)
        self.one_time_questid: list[int] = [] # one-time story quests already completed

        self.player_in_area: list[PlayerArea] = []

        self.bot_main = None
        self.command = Command(self, init_handler=True)

        #: The reader task of the current session.  One per session: a relogin
        #: used to start a second one without ending the first, and an orphaned
        #: reader on a closed socket kept calling ``recv`` on it -- which fails
        #: instantly, so it spun at full CPU.
        self.reader_task = None
        #: Why a relogin was asked for, for the log line that follows it.
        self.relogin_reason = ""

    def subscribe(self, callback):
        """Subscribe to messages."""
        if callable(callback):
            if callback not in self.subscribers:
                self.subscribers.append(callback)

    def unsubscribe(self, callback):
        """Unsubscribe from messages."""
        if callback in self.subscribers:
            self.subscribers.remove(callback)

    def notify_subscribers(self, message):
        """Notify all subscribers."""
        for subscriber in self.subscribers:
            subscriber(message)
        
    def set_login_info(self, username, password, server):
        self.username = username
        self.password = password
        self.server = server
        
    async def start_bot(self, botMain: Optional[Callable[[Command], Awaitable[None]]] = None):
        """Run the bot, and keep bringing it back while it can come back.

        One relogin is one more *session* on this same object -- not another
        ``start_bot`` call from inside the dying one.  The old shape recursed
        (``start_bot`` -> ``relogin_and_restart`` -> ``start_bot``), so a long run
        collected an await stack, a reader task and a register-quest task per
        relogin, and the orphaned readers then spun on their closed sockets: that
        is where a CPU graph that only ever climbs came from.

        This loop is bounded and says so; the retry that never gives up belongs to
        the app layer, which restarts a pane whose thread has ended.
        """
        if botMain is not None:
            self.bot_main = botMain

        attempts = 0
        while True:
            ran = await self._run_session()
            if ran:
                # The bot really ran this time, so the count is about consecutive
                # failures to get it running again -- not about how long it has
                # been alive.  Without this a scheduled save-state relogin every
                # hour would hit the cap after three hours and stop for good.
                attempts = 0
            if not self.auto_relogin:
                return
            attempts += 1
            if (self.RELOGIN_MAX_ATTEMPTS
                    and attempts > self.RELOGIN_MAX_ATTEMPTS):
                print(f"[relogin] {attempts - 1} attempts did not get the bot "
                      f"running; stopping here so the app can restart it.")
                return
            delay = min(self.RELOGIN_DELAY_S * attempts,
                        max(self.RELOGIN_DELAY_S, RELOGIN_MAX_DELAY_S))
            reason = f" ({self.relogin_reason})" if self.relogin_reason else ""
            self.relogin_reason = ""
            cap = f"/{self.RELOGIN_MAX_ATTEMPTS}" if self.RELOGIN_MAX_ATTEMPTS else ""
            print(f"[relogin] attempt {attempts}{cap}{reason} in "
                  f"{delay:g} secs...")
            await asyncio.sleep(delay)
            if not self.auto_relogin:
                print("[relogin] cancelled (the bot was stopped).")
                return

    async def _run_session(self) -> bool:
        """One login, one connection, one script run.

        Returns:
            bool: True when a session ran to its end; False when the login or the
            connection failed, which is what the caller's own retry is for.
        """
        self._reset_session_state()
        self.login(self.username, self.password, self.server)
        if not self.server_info:
            print("[relogin] the login did not go through; retrying.")
            return False
        await self.connect_client()
        if not self.is_client_connected:
            print("[relogin] could not connect; retrying.")
            return False

        if self.isScriptable and self.bot_main:
            self._start_reader()

            while self.is_client_connected:
                while self.is_char_load_complete is False:
                    # The character load never arrives on a session that has
                    # already ended, and waiting for it without this check hung
                    # the thread for good -- the pane looked alive and never ran.
                    if not self.is_client_connected:
                        return False
                    await asyncio.sleep(0.01)

                # The bank arrives on its own login packet -- the one that
                # fills in CHARID -- and not on the packet that marks the
                # character loaded.  Without this wait a script can start
                # with an empty BANK and farm what is already banked.  It
                # waits for the load to have been *attempted*, bounded, so a
                # session that never sends the packet still runs -- loudly.
                bank_deadline = time.time() + BANK_WAIT_TIMEOUT_S
                while (not self.player.bank_load_finished
                       and self.is_client_connected
                       and time.time() < bank_deadline):
                    await asyncio.sleep(0.05)
                if not self.player.bank_load_finished:
                    print(Fore.YELLOW + "[bank] not loaded yet; checks that "
                          "consult the bank may farm what is already "
                          "banked." + Fore.RESET)

                if not self.is_register_quest_task_running:
                    self.run_register_quest_task()
                    self.is_register_quest_task_running = True

                self._cancel_task("watch_task")
                self.watch_task = asyncio.create_task(self._watch_loop())
                self._cancel_task("tick_task")
                self.tick_task = asyncio.create_task(self._tick_loop())

                # The script runs in its own task so a dropped connection can
                # end it.  Waiting on it directly was the reason a peer reset
                # mid-farm stopped nothing: the script sits in a loop that
                # never checks the connection, so ``botMain`` never returned
                # and the relogin below was never reached.
                script = asyncio.create_task(
                    self.bot_main(self._resolve_script_arg(self.bot_main)))
                while self.is_client_connected and not script.done():
                    await asyncio.sleep(0.2)
                if not script.done():
                    print("Connection lost while the script was running; "
                          "stopping it and relogging.")
                    script.cancel()
                    try:
                        await script
                    except asyncio.CancelledError:
                        pass
                elif not script.cancelled() and script.exception() is not None:
                    # let the traceback out through the task machinery
                    script.result()

                self.stop_bot()
            return True

        await self.run_commands()
        return True

    def _start_reader(self) -> None:
        """Start this session's reader, ending the previous one first."""
        self._cancel_reader()
        self.reader_task = asyncio.create_task(self.read_server_in_background())

    def _cancel_reader(self) -> None:
        """Drop the reader task of the session that is ending."""
        self._cancel_task("reader_task")

    def request_relogin(self, reason: str = "") -> None:
        """End this session and ask ``start_bot`` to bring the bot back.

        The packet handlers ("invalid session", AFK) call this.  They used to
        call ``relogin_and_restart`` inline, which started the next session from
        inside the one it was killing -- the recursion this replaces.
        """
        self.relogin_reason = reason
        self.stop_bot()

    def _reset_session_state(self) -> None:
        """Clear what belongs to one session, so the next one starts clean."""
        self.index = 0
        self.is_char_load_complete = False
        self.is_joining_map = False
        self.is_register_quest_task_running = False
        self.loaded_quest_datas = []
        self.loaded_shop_datas: List[Shop] = []
        self.registered_auto_quest_ids = []
        self.check_spam_time = None
        self.spam_backoff_ms = 0

        _BOTS.add(self)
        _start_freeze_watch()

    def _progress_signature(self):
        """A cheap fingerprint of "the world moved", for the stall detector.

        Map, cell, level, gold, hp/mana and how much is carried: a farm changes
        at least one of those constantly.  That covers what a working bot does
        between kills -- buying (gold down, inventory up), a map change (the map
        name changes), and a long fight (hp/mana move every hit).

        What it deliberately does **not** count is *trying*: a join that never
        lands, a purchase that never goes through or a jump at a cell that is not
        there leave every one of these unchanged, which is exactly the shape of a
        stuck bot -- /shadowblast's "stuck at Enter" -- and the point of the
        detector.
        """
        player = self.player
        try:
            inv = sum(int(getattr(item, "qty", 0) or 0)
                      for item in player.INVENTORY)
            temp = sum(int(getattr(item, "qty", 0) or 0)
                       for item in player.TEMPINVENTORY)
        except Exception:
            inv = temp = 0
        return (self.strMapName, player.CELL, player.LEVEL, player.GOLD,
                player.CURRENT_HP, player.MANA, inv, temp)

    async def _watch_loop(self) -> None:
        """Say the session is alive, and re-establish it when it is not.

        Two things a farm left alone needs and cannot see for itself:

        * **Visibility** -- one line every ``HEARTBEAT_SECONDS`` with the map,
          cell, level and how many packets came in, so "is it still running?"
          is answerable from the log instead of from a guess.
        * **A stall detector** -- the shape /shadowblast shows: the socket is up,
          the bot stands at Enter casting at nothing, and no packet arrives
          again.  Nothing inside the script can notice that, so the session is
          re-established here, which is what a fresh area packet fixes.

        Both are one sleep and a subtraction per tick, so the cost is nothing.
        """
        stall = self.STALL_SECONDS
        beat = self.HEARTBEAT_SECONDS
        if not stall and not beat:
            return
        tick = max(1.0, min(x for x in (stall, beat) if x) / 3.0)
        last_beat = time.time()
        last_sig = self._progress_signature()
        last_progress = time.time()
        while self.is_client_connected:
            await asyncio.sleep(tick)
            if not self.is_client_connected:
                return
            now = time.time()
            if beat and now - last_beat >= beat:
                seen, self.packets_seen = self.packets_seen, 0
                sent, self.packets_sent = self.packets_sent, 0
                last_beat = now
                print(f"[watch] still running: {self.strMapName}/"
                      f"{self.player.CELL} level {self.player.LEVEL} "
                      f"{self.player.CURRENT_HP}/{self.player.MAX_HP} hp, "
                      f"{sent} sent / {seen} received in the last "
                      f"{beat / 60:.0f} min")
            if not stall:
                continue
            signature = self._progress_signature()
            if signature != last_sig:
                last_sig = signature
                last_progress = now
            quiet_out = now - self.last_send_ts
            quiet_in = now - self.last_packet_ts
            quiet_work = now - last_progress
            if quiet_out >= stall:
                print(f"[watch] sent nothing for {quiet_out / 60:.0f} min in "
                      f"{self.strMapName}/{self.player.CELL}; the session looks "
                      f"stuck, re-establishing it")
                self.request_relogin(f"silent {quiet_out / 60:.0f} min")
                return
            if quiet_in >= stall:
                print(f"[watch] nothing came back for {quiet_in / 60:.0f} min in "
                      f"{self.strMapName}/{self.player.CELL}; the session looks "
                      f"stuck, re-establishing it")
                self.request_relogin(f"no answer {quiet_in / 60:.0f} min")
                return
            if quiet_work >= stall:
                print(f"[watch] nothing has changed for "
                      f"{quiet_work / 60:.0f} min in "
                      f"{self.strMapName}/{self.player.CELL} (still sending, but "
                      f"stuck); re-establishing the session")
                self.request_relogin(f"no progress {quiet_work / 60:.0f} min")
                return

    async def _tick_loop(self) -> None:
        """Bump ``loop_ticks`` every second while the session is up.

        Nothing else depends on the number: it exists so the freeze reporter
        thread can tell a busy loop from a frozen event loop.  One wake-up a
        second costs nothing next to the socket reader.
        """
        while self.is_client_connected:
            self.loop_ticks += 1
            await asyncio.sleep(1.0)

    def _resolve_script_arg(self, botMain):
        """Pass the object the script's ``main`` expects.

        Two conventions coexist in ``bot/``: the current ``main(cmd)`` (a
        ``Command``) and the legacy ``main(bot: Bot)`` that wraps it again with
        ``Command(bot)``.  The harness always sent the ``Command``, so the
        legacy scripts raised ``'Command' object has no attribute 'player'``
        (they treat the argument as a ``Bot``).  Tell them apart by the first
        parameter's name/annotation.
        """
        try:
            params = list(inspect.signature(botMain).parameters.values())
        except (TypeError, ValueError):
            return self.command
        if not params:
            return self.command
        first = params[0]
        annotation = first.annotation
        ann_name = annotation if isinstance(annotation, str) else getattr(annotation, "__name__", "")
        if first.name == "bot" or ann_name == "Bot":
            return self
        return self.command
            
    def run_register_quest_task(self):
        asyncio.create_task(register_quest_task(self))  
    
    def run_death_hanlder_task(self):
        asyncio.create_task(death_handler_task(self))  

    def run_aggro_hadler_task(self):
        """Start the aggro handler, ending any previous one.

        Exactly one: two of these double every ``aggroMon`` packet, and a farm
        loop calls ``start_aggro`` often enough to end up with dozens.
        """
        self._cancel_task("aggro_task")
        self.aggro_task = asyncio.create_task(aggro_handler_task(self))

    def _cancel_task(self, name: str) -> None:
        """Cancel the task held on ``self.<name>``, if any, without blocking."""
        task = getattr(self, name, None)
        setattr(self, name, None)
        if task is None or task.done():
            return
        try:
            if task is asyncio.current_task():
                return          # asked from inside it; it is ending anyway
        except RuntimeError:
            pass
        task.cancel()
    
    def stop_bot(self, user_triggered=False):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Stopping bot...")
        if user_triggered:
            self.auto_relogin = False
        self._cancel_reader()
        # The aggro handler is per bot, not per session: without this a stopped
        # pane kept sending aggroMon for as long as the process lived.
        self._cancel_task("aggro_task")
        self.is_aggro_handler_task_running = False
        self.aggro_mons_id = []
        # The stall/heartbeat watcher belongs to the session that is ending.
        self._cancel_task("watch_task")
        if self.client_socket:
            try:
                self.client_socket.close()
            except Exception as e:
                print(f"Error closing socket: {e}")
        self.is_client_connected = False
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Bot stopped")

    def debug(self, *args):
        if not self.showDebug:
            return
        caller_frame = inspect.currentframe().f_back
        caller_name = caller_frame.f_code.co_name
        combined_message = ' '.join(map(str, args))
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [{caller_name}] {combined_message}")

    def log(self, *args):
        """Log one script line -- the reference bot's ``Core.Logger``.

        ``showLog`` gates it and the timestamp matches the engine's other
        output, so a run reads the same way whether the line came from here or
        from a script.  Scripts call this instead of ``print``: their lines then
        sit in the same stream as the engine's, which is what makes a port's log
        comparable with the reference bot's.
        """
        if not self.showLog:
            return
        combined_message = ' '.join(map(str, args))
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {combined_message}")

    def login(self, username, password, server):
        if self.player.login(username, password):
            self.server_info = self.player.getServerInfo(server)
            
    async def relogin_and_restart(self, async_bot= None):
        """End this session; ``start_bot``'s own loop brings the bot back.

        Kept as the name the rest of the engine knows.  It deliberately does not
        call ``start_bot`` any more: doing so nested the next session inside the
        one it was killing, and a long run then held an await stack -- plus a
        reader task and a register-quest task -- per relogin.
        """
        if async_bot is not None:
            self.bot_main = async_bot
        self.request_relogin("relogin requested")
        await asyncio.sleep(0)
        
    async def connect_client(self):
        hostname, port = self.server_info
        print(f"Connecting to {Fore.GREEN}{self.server.upper()}{Fore.RESET}...")
        host_ip = socket.gethostbyname(hostname)
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.settimeout(5.0) 
        try:
            self.client_socket.connect((host_ip, port))
            self.write_message("<policy-file-request/>")
            self.is_client_connected = True
            print(f"{Fore.GREEN}Connected to {hostname}:{port}{Fore.RESET}")
        except (socket.error, ConnectionRefusedError) as e:
            self.is_client_connected = False
            print(f"{Fore.RED}Connection failed: {e}{Fore.RESET}")
            
    # Handling Sequential Commands bot mode
    async def run_commands(self):    
        if not self.is_client_connected:
            print("Client not connected!")
            return
        
        print("Running bot commands...")

        while self.is_client_connected:
            try:
                messages = self.read_batch(self.client_socket)
                
                # Handle Server Request-Response
                if messages:
                    for msg in messages:
                        try:
                            if msg.startswith("Z"):
                                msg = self.decompress_message(msg)
                            await self.handle_server_response(msg)
                        except Exception as e:
                            print(f"Handle Response Error: {e}")
                
                # Auto Quest Task
                if self.registered_auto_quest_ids and not self.is_register_quest_task_running:
                    self.run_register_quest_task()
                    self.is_register_quest_task_running = True

                # Handle Death / Respawn
                if self.player.ISDEAD:
                    self.write_message(f"%xt%zm%resPlayerTimed%{self.areaId}%{self.username_id}%")
                    self.jump_cell(self.player.CELL, self.player.PAD)
                    self.player.ISDEAD = False
                    self.player.MANA = 100
                    await asyncio.sleep(0.5)
                    continue

                # Command Execution Logic
                if self.is_char_load_complete and not self.is_joining_map:
                    if self.follow_player and self.followed_player_cell != self.player.CELL:
                        await self.goto_player(self.follow_player)
                        await asyncio.sleep(1)
                        continue                
                    
                    if self.cmds:
                        if self.index >= len(self.cmds):
                            self.index = 0                
                        
                        cmd = self.cmds[self.index]
                        await self.handle_command(cmd)
                        self.index += 1

                await asyncio.sleep(max(0.1, self.wait_ms / 1000))
                self.wait_ms = 0
                
            except BlockingIOError:
                await asyncio.sleep(0.1)
            except (ConnectionResetError, BrokenPipeError):
                print("Server closed the connection.")
                self.is_client_connected = False
                break
            except Exception as e:
                print(f"Loop Error: {e}")
                
        print('BOT STOPPED\n')
        # The relogin is ``start_bot``'s loop to decide; asking for one from here
        # would nest the next session inside this one.
        return

    def print_commands(self):
        print("Index\tCommand")
        print("------------------------------")
        for i, cmd in enumerate(self.cmds):
            print(cmd.to_string())
        print("------------------------------")

    async def handle_command(self, command):
        if command.skip_delay: # when skip_delay, we execute the cmd first before print its text
            await command.execute(self, self.command)
        if self.showLog: # print text
            cmd_string = command.to_string()
            if cmd_string:
                cmd_string = cmd_string.split(':')
                if len(cmd_string) > 1:
                    print(Fore.BLUE + f"[{datetime.now().strftime('%H:%M:%S')}] [{self.index}] {cmd_string[0]}:" + Fore.RESET + cmd_string[1])
                else:
                    print(Fore.BLUE + f"[{datetime.now().strftime('%H:%M:%S')}] [{self.index}] {cmd_string[0]}" + Fore.RESET)
        if not command.skip_delay:  # when not skip delay, execute cmd after print its text
            await command.execute(self, self.command)
            await asyncio.sleep(self.cmdDelay/1000)
    
    def check_user_access_level(self, username: str, access_level: int):
        if access_level >= 30 and self.anti_mod:
            print(Fore.RED + f"[{datetime.now().strftime('%H:%M:%S')}] You meet {username}, a staff!")
            self.auto_relogin = False
            self.stop_bot()

    async def handle_server_response(self, msg):
        # The stall detector and the heartbeat read these two: one timestamp and
        # one counter per inbound packet, which is as cheap as a liveness signal
        # gets.
        self.last_packet_ts = time.time()
        self.packets_seen += 1
        if msg.startswith("Z"):
            msg = self.decompress_message(msg)

        if self.auto_adjust_skill_delay and self.check_spam_time:
            # One step per quiet minute, not one per message: the old version
            # left check_spam_time pinned, so once the 300 s window elapsed it
            # subtracted on every single inbound packet.
            if (time.time() - self.check_spam_time) > 60 and self.spam_backoff_ms > 0:
                self.spam_backoff_ms = max(0, self.spam_backoff_ms - 300)
                self.check_spam_time = time.time()
                print(f"skill pacing backoff: +{self.spam_backoff_ms} ms")
        self.notify_subscribers(msg)
        if "counter" in msg.lower():
            self.debug(Fore.RED + msg + Fore.WHITE)

        if self.is_valid_json(msg):
            data = json.loads(msg)
            try:
                data = data["b"]["o"]
            except:
                return
            cmd = data["cmd"]
            if cmd == "moveToArea":
                uo_branch = data.get("uoBranch")
                mon_branch = data.get("monBranch")
                mon_def = data.get("mondef")
                mon_map = data.get("monmap")
                self.areaName = data["areaName"] #"yulgar-99999"
                self.areaId = data["areaId"]
                self.strMapName: str = data["strMapName"] #"yulgar"
                self.monsters: list[Monster] = []
                #: Cleared by a fresh area packet, set by ``respawnMon``.
                self.monsters_stale = False
                self.player_in_area: list[PlayerArea] = []
                for i_uo_branch in uo_branch:
                    if (i_uo_branch["uoName"].lower() == self.player.USER.lower()):
                        self.player.PAD = i_uo_branch["strPad"]
                        self.player.CELL = i_uo_branch["strFrame"]
                    if (i_uo_branch["uoName"].lower() == self.follow_player.lower()):
                        self.followed_player_cell = i_uo_branch["strFrame"]
                    if (i_uo_branch["uoName"].lower() == self.player.USER.lower()):
                        self.player.setIsInCombat(i_uo_branch["intState"])
                    self.player_in_area.append(PlayerArea(i_uo_branch))
                if mon_def and mon_branch and mon_map:
                    for i_mon_branch in mon_branch:
                        self.monsters.append(Monster(i_mon_branch))
                    for i_mon_def in mon_def:
                        for mon in self.monsters:
                            if str(i_mon_def["MonID"]) == mon.mon_id:
                                mon.mon_name = i_mon_def["strMonName"]
                    for i_mon_map in mon_map:
                        for mon in self.monsters:
                            if str(i_mon_map["MonMapID"]) == mon.mon_map_id:
                                mon.frame = i_mon_map["strFrame"]
            elif cmd == "initUserDatas":
                try:
                    for i in data["a"]:
                        username = i["data"]["strUsername"]
                        access_level = int(i["data"]["intAccessLevel"])
                        if username.lower() == self.username.lower() and self.player.CHARID == 0:
                            self.player.CHARID = i["data"]["CharID"]
                            self.player.GOLD = int(i["data"]["intGold"])
                            # Level sits in this payload under one of two keys
                            # depending on the client build; neither is worth
                            # raising over, so read whichever is present.
                            self.player.LEVEL = int(
                                i["data"].get("iLvl")
                                or i["data"].get("intLevel") or 0
                            )
                        self.check_user_access_level(username, access_level)
                    if not self.player.BANK:
                        # print("Load bank and inventory...")
                        self.player.loadBank()
                        self.write_message(f"%xt%zm%retrieveInventory%{self.areaId}%{self.username_id}%")
                except Exception as e:
                    print(f"initUserDatas err: {e}")
            elif cmd == "initUserData":
                username = data["data"]["strUsername"]
                access_level = int(data["data"]["intAccessLevel"])
                self.check_user_access_level(username, access_level)
                # The Awe story counter.  ``CoreAdvanced.uAwe``-era code and
                # ``CoreAwe.GetAweRelic`` read it off the client
                # (``world.myAvatar.objData.intAQ``); it arrives on this packet,
                # in the entry's ``data``.
                aq = (data.get("data") or {}).get("intAQ")
                if aq is None:
                    aq = data.get("intAQ")
                if aq is not None:
                    self.player.intAQ = int(aq)
                    self.debug(f"intAQ = {self.player.intAQ}")
            elif cmd == "equipItem":
                pass
            elif cmd == "loadInventoryBig":
                self.is_char_load_complete = True
                for item in data["items"]:
                    self.player.INVENTORY.append(ItemInventory(item))
                for faction in data.get("factions", []):
                    self.player.addFaction(Faction(faction))

            # on monster spwaned in map
            elif cmd == "mtls":
                for mon in self.monsters:
                    if mon.mon_map_id == str(data["id"]):
                        mon.is_alive = int(data["o"].get("intState", mon.is_alive)) > 0
                        mon.current_hp = int(data["o"].get("intHP", mon.current_hp))
                        break
            # on player spwaned in map
            elif cmd == "uotls":
                if str(data['unm']) == str(self.player.USER):
                    self.player.MAX_HP = int(data['o'].get('intHPMax', self.player.MAX_HP))
                    self.player.MANA = int(data['o'].get('intMP', self.player.MANA))
                    self.player.setIsInCombat(data["o"].get("intState"))
                    if self.player.IS_IN_COMBAT == False:
                        self.player.setLastTarget(None)
                else:
                    player_name: str = data['unm']
                    player_found = False
                    for player in self.player_in_area:
                        if player_name.lower() == player.str_username.lower():
                            player_found = True
                            player.updateDataPlayer(data["o"])
                            break
                    if not player_found:
                        self.player_in_area.append(PlayerArea(data["o"]))
                    
            elif cmd == "sAct":
                # Wrap each entry in model.Skill.  Skill subclasses dict, so
                # every existing `SKILLS[n]["cd"]` / `.get("anim")` call site
                # keeps working -- only the type changes.  See model/skill.py
                # for the field map (21 keys, not all present on all slots).
                self.player.SKILLS = [
                    Skill.from_payload(s) for s in data["actions"]["active"]
                ]
                for skill in self.player.SKILLS:
                    self.player.skills_ref[skill.ref] = {
                        "anim": skill.animation,
                        "strl": skill.string_label,
                    }
                    # Slots start off-cooldown so the first rotation is not
                    # held back by an arbitrary deadline.
                    skill.next_use = datetime.now()
            elif cmd == "stu":
                # Merge the delta the server sent.  `sta` carries only changed
                # keys, so PlayerStats.update() merges rather than replaces.
                # CDREDUCTION/ManaCost stay in sync below for existing readers.
                self.player.STATS.update(
                    data.get("sta"),
                    data.get("tempSta"),
                    data.get("wDPS"),
                )
                sta = data.get("sta") or {}
                if sta.get("$tha") is not None:
                    self.player.CDREDUCTION = sta["$tha"]
                if sta.get("$cmc") is not None:
                    self.player.ManaCost = sta["$cmc"]
            elif cmd == "ct":
                anims = data.get("anims")
                a = data.get("a")
                m = data.get("m")
                p = data.get("p")
                sarsa = data.get("sarsa")
                sara = data.get("sara")
                if anims:
                    for anim in anims:
                        if anim["cInf"] == f"p:{self.username_id}":
                            animStr: str = anim.get("animStr")
                            strl: str = anim.get("strl", "")
                            
                # update player status
                if p:
                    player = p.get(self.username)
                    if player:
                        self.player.CURRENT_HP = player.get("intHP", self.player.CURRENT_HP)
                        self.player.MANA = player.get("intMP", self.player.MANA)
                        # self.player.IS_IN_COMBAT = int(player.get("intState", self.player.IS_IN_COMBAT)) == 2
                        self.player.setIsInCombat(player.get("intState"))
                
                # update monsters status
                if m:
                    for mon_map_id, mon_condition in m.items():
                        for mon in self.monsters:
                            if mon.mon_map_id == mon_map_id:
                                mon.current_hp = int(mon_condition.get("intHP", mon.current_hp))
                                mon.is_alive = mon.current_hp > 0
                                # print(f"[{datetime.now().strftime('%H:%M:%S')}] Monster {mon.mon_name} ({mon.mon_map_id}) HP: {mon.current_hp}, Alive: {mon.is_alive}")
                            
                # update auras
                if a:
                    for action in a:
                        tInf = action.get('tInf')
                        action_cmd = action.get('cmd')

                        # update aura for monster
                        if tInf.startswith('m'):
                            for mon in self.monsters:
                                if f"m:{mon.mon_map_id}" == tInf:
                                    if 'aura+' in action_cmd:
                                        mon.addAura(action.get('auras', []))
                                    elif 'aura-' in action_cmd:
                                        removed_aura = action.get('aura', {}).get('nam')
                                        mon.removeAura(removed_aura) 
                        
                        # update aura for player
                        if self.username_id in tInf:
                            if 'aura+' in action_cmd:
                                self.player.addAura(action.get('auras', []))
                            elif 'aura' in action_cmd:
                                removed_aura = action.get('aura', {}).get('nam')
                                self.player.removeAura(removed_aura)
                if sarsa:
                    for sarsaElm in sarsa:
                        if sarsaElm["cInf"] == f"p:{self.username_id}":
                            for aSarsa in sarsaElm["a"]:
                                sarsaType = aSarsa["type"]
                                sarsaTarget = aSarsa["tInf"]
                                sarsaActRef = aSarsa["actRef"]
                                self.debug(Fore.GREEN + "skill casted: " + sarsaActRef + Fore.WHITE)
                                if "m" in sarsaTarget:
                                    self.debug(Fore.BLUE + f"[SARSA] [{sarsaType.upper()}] {aSarsa['hp']} DMG to {sarsaTarget}" + Fore.WHITE)
                                    if self.battle_analyzer:
                                        self.battle_analyzer_total_damage += aSarsa['hp']
                                        now = datetime.now()
                                        if (now - self.battle_analyzer_last_print) >= timedelta(seconds=5):
                                            self.debug(Fore.RED + f"DPS: {self.battle_analyzer_total_damage / int((datetime.now() - self.battle_analyzer_time_start).total_seconds())}" + Fore.WHITE)
                                            self.battle_analyzer_last_print = now
                                else:
                                    if aSarsa['hp'] < 0:
                                        self.debug(Fore.BLUE + f"[SARSA] [HEAL] {abs(aSarsa['hp'])} HP to {sarsaTarget}" + Fore.WHITE)
                                    else:
                                        self.debug(Fore.BLUE + f"[SARSA] [{sarsaType.upper()}] to {sarsaTarget}" + Fore.WHITE)
                if sara:
                    for saraElm in sara:
                        actionResult = saraElm["actionResult"]
                        saraCInf = actionResult["cInf"]
                        saraTInf = actionResult["tInf"]
                        if saraCInf == f"p:{self.username_id}" and saraTInf == f"p:{self.username_id}":
                            saraType = actionResult["typ"]
                            if saraType == "d":
                                self.debug(Fore.CYAN + f"[SARA] [HOT] {abs(actionResult['hp'])} HOT to {saraTInf}" + Fore.WHITE)
                            else:
                                self.debug(Fore.CYAN + f"[SARA] [{saraType.upper()}] to {saraTInf}" + Fore.WHITE)
                        elif saraCInf.startswith("m") and saraTInf == f"p:{self.username_id}":
                            saraType = actionResult.get("type", "")
                            self.debug(Fore.CYAN + f"[SARA] [{saraType.upper()}] {actionResult['hp']} DMG to {saraTInf}" + Fore.WHITE)
            elif cmd == "seia":
                # Some classes ship fewer than six slots in sAct; the item
                # slot arrives here instead.  Pad with an empty Skill so this
                # handler can fill it in rather than raising IndexError.
                while len(self.player.SKILLS) <= 5:
                    self.player.SKILLS.append(Skill())
                self.player.SKILLS[5]["anim"] = data["o"]["anim"]
                self.player.SKILLS[5]["strl"] = data["o"]["strl"]
                self.player.SKILLS[5]["cd"] = data["o"]["cd"]
                self.player.SKILLS[5]["tgt"] = data["o"]["tgt"]
                anim_strl = {
                        "anim" : self.player.SKILLS[5]["anim"],
                        "strl" : self.player.SKILLS[5]["strl"]
                    }
                self.player.SKILLS[5]["ref"] = "i1"
                self.player.SKILLS[5]["nextUse"] = datetime.now()
                self.player.skills_ref["i1"] = anim_strl
                # print(self.player.skills_ref)
                # print(f"Skills: {self.player.SKILLS}")
            elif cmd == "castWait":
                # Fishing: the server says how long this cast takes (it varies:
                # 2800-7000 ms in the capture) and whether it is a derp cast.
                # CoreFarms.FishingREP waits for this instead of trusting its own
                # 3500 ms starter value, and this is that packet.
                self.fishing_wait_ms = int(data.get("wait") or 0)
                self.fishing_derp = bool(data.get("derp") or False)
                self.fishing_cast_wait = True
            elif cmd == "CatchResult":
                # Fishing: what was caught.  The server turns the fish in itself
                # (a ``turnIn`` message follows), so nothing is sent from here.
                self.fishing_catch_result = data.get("catchResult") or {}
                self.fishing_caught = True
            elif cmd == "playerDeath":
                if int(data["userID"]) == self.player.LOGINUSERID:
                    print(Fore.RED + "DEATH" + Fore.WHITE)
                    self.player.ISDEAD = True
                    self.deaths += 1
                    # Remember the farm, not the spawn cell the server is about
                    # to move the character to.
                    self.death_cell_pad = (self.strMapName, self.player.CELL,
                                           self.player.PAD)
                    if self.isScriptable:
                        self.run_death_hanlder_task()
            elif cmd == "getQuests":
                for quest_id, quest_data in data.get("quests").items():
                    self.loaded_quest_datas.append(Quest.from_payload(quest_data))
            elif cmd == "loadShop":
                shop = Shop(data["shopinfo"])
                # Opening a forge shop teaches the enhancement registry every
                # enhancement it sells (name <-> EnhID <-> pattern <-> slot),
                # so equip_enhancement() works without the jsonl on disk.
                if shop.is_forge:
                    shop.register_enhancements()
                found = False
                for loaded_shop in self.loaded_shop_datas:
                    if str(loaded_shop.shop_id) == str(shop.shop_id):
                        found = True
                        break
                if found == False:
                    self.loaded_shop_datas.append(shop)
            elif cmd == "buyItem":
                if data["bitSuccess"] == 1:
                    for loaded_shop in self.loaded_shop_datas:
                        for shop_item in loaded_shop.items:
                            if str(shop_item.item_id) == str(data["ItemID"]):
                                bought = ItemInventory({
                                    "sName": shop_item.item_name,
                                    "ItemID": data["ItemID"],
                                    "CharItemID": data["CharItemID"],
                                    "iQty": data["iQty"]
                                })
                                print(f"bought {bought.item_name} {bought.qty}")
                                player_item = self.player.get_item_inventory_by_id(bought.item_id)
                                if player_item:
                                    player_item.qty += bought.qty
                                else:
                                    self.player.INVENTORY.append(bought)
                                return
            elif cmd == "sellItem":
                # {"t":"xt","b":{"r":-1,"o":{"iQtyNow":230,"cmd":"sellItem","intAmount":43750,"CharItemID":8.3779747E8,"bCoins":0,"iQty":7}}}
                for item in self.player.INVENTORY:
                    if int(item.char_item_id) == int(data["CharItemID"]):
                        self.player.GOLD += int(data["intAmount"])
                        self.player.GOLDFARMED += int(data["intAmount"])
                        debug_data_gold = {
                            "gold_added": int(data["intAmount"]),
                            "gold_now": self.player.GOLD,
                            "gold_farmed": self.player.GOLDFARMED
                        }
                        print(Fore.YELLOW + str(debug_data_gold) + Fore.WHITE)
                        if data["iQtyNow"] == 0:
                            self.player.INVENTORY.remove(item)
                            print(f"sold {data['iQty']}x {item.item_name}. qty now: 0")
                        else:
                            item.qty = data["iQtyNow"]
                            print(f"sold {data['iQty']}x {item.item_name}. qty now: {item.qty}")
                        break
            elif cmd == "addGoldExp":
                self.player.GOLD += data["intGold"]
                self.player.GOLDFARMED += data["intGold"]
                gold_added = data["intGold"]
                debug_data_gold = {
                    "gold_added": gold_added,
                    "gold_farmed": self.player.GOLDFARMED,
                    "gold_now": self.player.GOLD
                }
                intExp = data.get("intExp", 0)
                if intExp > 0:
                    self.player.EXPFARMED += intExp
                    debug_data_exp = {
                        "exp_added": intExp,
                        "exp_farmed": self.player.EXPFARMED
                    }
                    self.debug(Fore.BLUE + str(debug_data_exp) + Fore.WHITE)
                intRep = data.get("iRep", 0)
                if intRep > 0:
                    # {"t":"xt","b":{"r":-1,"o":{"FactionID":75,"cmd":"addGoldExp","intGold":0,"intExp":0,"typ":"q","bonusRep":1000,"iRep":3000}}}
                    self.player.addRepToFaction(data.get('FactionID', 0), data.get('iRep', 0))
                self.debug(Fore.YELLOW + str(debug_data_gold) + Fore.WHITE)
            elif cmd == "dropItem":
                dropItems = data.get('items', {})
                lowered_droplist = [item.lower() for item in self.items_drop_whitelist]
                for itemDropRaw in dropItems.values():
                    itemDrop: ItemInventory = ItemInventory(itemDropRaw)
                    is_whitelisted = itemDrop.item_name.lower() in lowered_droplist
                    drop_info = {
                        "item_id": str(itemDrop.item_id),
                        "item_name": str(itemDrop.item_name),
                        "qty": int(itemDrop.qty),
                        "is_acs": bool(itemDrop.is_acs),
                        "is_temp": bool(itemDrop.is_temp),
                        "s_type": str(itemDrop.s_type),
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "picked_up": is_whitelisted
                    }
                    if not hasattr(self, "dropped_items"):
                        self.dropped_items = []
                    existing = next((d for d in self.dropped_items if d.get("item_id") == drop_info["item_id"]), None)
                    if existing:
                        existing.update(drop_info)
                    else:
                        self.dropped_items.insert(0, drop_info)
                        if len(self.dropped_items) > 50:
                            self.dropped_items.pop()

                    if is_whitelisted:
                        print(f"get drop {itemDrop.item_name}")
                        self.get_drop(self.username_id, itemDrop.item_id)
                        self.player.INVENTORY.append(itemDrop)
            elif cmd == "addItems":
                dropItems = data.get('items', {})
                if hasattr(self, "dropped_items"):
                    for d_id in dropItems.keys():
                        for d in self.dropped_items:
                            if str(d.get("item_id")) == str(d_id):
                                d["picked_up"] = True
                for itemId, dropItem in dropItems.items():
                    dropItem: ItemInventory = ItemInventory(dropItem)
                    # Item inventory
                    if dropItem.char_item_id:
                        playerItem = self.player.get_item_inventory_by_id(itemId)
                        playerBankItem = self.player.get_item_bank_by_id(itemId)
                        item_name = dropItem.item_name
                        if playerItem:
                            playerItem.qty = dropItem.qty_now
                            playerItem.char_item_id = dropItem.char_item_id
                            # await self.check_registered_quest_completion(itemId)
                            item_name = playerItem.item_name
                        else:
                            self.player.INVENTORY.append(dropItem)
                        if playerBankItem:
                            playerBankItem.qty = dropItem.qty_now
                            playerBankItem.char_item_id = dropItem.char_item_id
                            item_name = playerBankItem.item_name
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] add items {item_name}. qty now {dropItem.qty_now}")
                    # Item temp inventory
                    else:
                        playerItem = self.player.get_item_temp_inventory_by_id(itemId)
                        if playerItem:
                            playerItem.qty += dropItem.qty
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] add temp items {playerItem.item_name}. qty now {playerItem.qty}")
                        else:
                            self.player.TEMPINVENTORY.append(dropItem)
                        
            elif cmd == "turnIn":
                sItems = data.get("sItems").split(',')
                for s_item in sItems:
                    itemId = s_item.split(':')[0]
                    iQty = int(s_item.split(':')[1])
                    playerItem = self.player.get_item_inventory_by_id(itemId)
                    if playerItem:
                        if playerItem.qty - iQty == 0:
                            self.player.INVENTORY.remove(playerItem)
                        else:
                            playerItem.qty -= iQty
                    playerTempItem = self.player.get_item_temp_inventory_by_id(itemId)
                    if playerTempItem:
                        if playerTempItem.qty - iQty == 0:
                            self.player.TEMPINVENTORY.remove(playerTempItem)
                        else:
                            playerTempItem.qty -= iQty
            elif cmd == "event":
                pass
                # print(Fore.GREEN + data["args"]["zoneSet"] + Fore.WHITE)
                # if data["args"]["zoneSet"]  == "A":
                #     if self.strMapName.lower() == "ultraspeaker":
                #         await self.walk_to(100, 321)
            elif cmd == "ccqr":
                quest_id = normalize_quest_id(data.get('QuestID'))
                s_name = data.get('sName', None)
                faction_id = data.get('rewardObj', {}).get('FactionID', None)
                i_rep = data.get('rewardObj', {}).get('iRep', 0)
                is_success = data.get('bSuccess', 0)
                ccqr_msg = data.get('msg', '')
                if is_success == 1:
                    quest = self.get_loaded_quest(quest_id)
                    if quest is not None and quest_id not in self.registered_auto_quest_ids:
                        self.loaded_quest_datas.remove(quest)
                    print(Fore.YELLOW + f"ccqr: [{datetime.now().strftime('%H:%M:%S')}] {quest_id} - {s_name} - {i_rep} rep" + Fore.WHITE)
                else:
                    print(Fore.RED + f"ccqr: [{datetime.now().strftime('%H:%M:%S')}] {quest_id} - {s_name} | {ccqr_msg}" + Fore.WHITE)
                    if quest_id and "Missing Turn In Item" in ccqr_msg:
                        self.missing_turn_in_item_questid.append(quest_id)
                    if quest_id and "Missing Quest Progress" in ccqr_msg:
                        self.missing_quest_progress_questid.append(quest_id)
                    if "One Time Quest Only" in ccqr_msg:
                        if quest_id is not None and int(quest_id) not in self.one_time_questid:
                            self.one_time_questid.append(int(quest_id))
            elif cmd == "Wheel":
                dropItems = data.get('dropItems')
                dropItemsName = [item["sName"] for item in dropItems.values() if "sName" in item]
                print(Fore.YELLOW + f"Wheel: {dropItemsName}" + Fore.WHITE)
            elif cmd == "acceptQuest":
                quest_id = normalize_quest_id(data["QuestID"])
                if data["bSuccess"] == 1:
                    if self.get_loaded_quest(quest_id) is None:
                        self.write_message(f"%xt%zm%getQuests%{self.areaId}%{quest_id}%")
                        self.do_wait(500)
                elif data["bSuccess"] == 0:
                    if quest_id and quest_id not in self.failed_get_quest_datas:
                        self.failed_get_quest_datas.append(quest_id)
                    reason = str(data.get("msg") or "").strip()
                    if reason and reason.lower() != "success":
                        print(Fore.YELLOW + f"[accept] quest {quest_id}: "
                              f"{reason}" + Fore.RESET)
            elif cmd == "addFaction":
                # {"t":"xt","b":{"r":-1,"o":{"cmd":"addFaction","faction":{"FactionID":"75","bitSuccess":"1","CharFactionID":"48707365","sName":"Yew Mountains","iRep":"0"}}}}
                self.player.addFaction(Faction(data["faction"]))
            elif cmd == "clearAuras":
                self.player.removeAllAuras()
        elif self.is_valid_xml(msg):
            if ("<cross-domain-policy><allow-access-from domain='*'" in msg):
                self.write_message(f"<msg t='sys'><body action='login' r='0'><login z='zone_master'><nick><![CDATA[SPIDER#0001~{self.player.USER}~5.3]></nick><pword><![CDATA[{self.player.TOKEN}]]></pword></login></body></msg>")
            elif "joinOK" in msg:
                self.extract_user_ids(msg)
            elif "userGone" in msg:
                self.extract_remove_user(msg)
            elif "uER" in msg:
                self.extract_new_user(msg)
                root = ET.fromstring(msg)
                newId = root.find(".//u").get("i")
                msg = f"%xt%zm%retrieveUserData%{self.areaId}%{newId}%"
                self.write_message(msg)
            elif "logout" in msg:
                print("Client logged out.")
                self.is_client_connected = False
                return
        elif msg.startswith("%") and msg.endswith("%"):
            if f"%server%" in msg:
                print(Fore.MAGENTA + f"[{datetime.now().strftime('%H:%M:%S')}] {msg.split('%')[4]}" + Fore.RESET)
            if f"%xt%loginResponse%" in msg:
                self.write_message(f"%xt%zm%firstJoin%1%")
                self.write_message(f"%xt%zm%cmd%1%ignoreList%$clearAll%")
            elif "You joined" in msg:
                self.write_message(f"%xt%zm%retrieveUserDatas%{self.areaId}%{self.username_id}%")
                self.is_joining_map = False
            elif "warning" in msg:
                msg = msg.split('%')
                text = msg[4]
                if "Please slow down" in text:
                    if self.mute_spam_warning == False:
                        print(Fore.RED + f"[{datetime.now().strftime('%H:%M:%S')}] server warning: {text}" + Fore.WHITE)
                else:
                    print(Fore.RED + f"[{datetime.now().strftime('%H:%M:%S')}] server warning: {text}" + Fore.WHITE)                    
                # Both server texts count: the baseline run produced two
                # "Last action was too soon!" warnings and zero "spamming the
                # server", so matching only the latter meant the backoff never
                # fired for the failure this bot actually hits.
                if "spamming the server" in text or "too soon" in text:
                    if self.auto_adjust_skill_delay:
                        self.spam_backoff_ms = min(self.spam_backoff_ms + 300, 2400)
                        self.check_spam_time = time.time()
                        print(f"skill pacing backoff: +{self.spam_backoff_ms} ms")
            elif "exitArea" in msg:
                if msg.split('%')[5].lower() == self.follow_player.lower():
                    self.followed_player_cell = None
                    await self.ensure_leave_from_combat(always=True)
                for player in self.player_in_area[:]:
                    if player.str_username.lower() == msg.split('%')[5].lower():
                        # print(f"{player.str_username} has left the area")
                        self.player_in_area.remove(player)
                        break
            elif "uotls" in msg:
                username = msg.split('%')[4]
                movement = msg.split('%')[5]
                cell = None
                pad = None
                for m in movement.split(','):
                    key, value = m.split(':')
                    if key == "strFrame":
                        cell = value
                    elif key == "strPad":
                        pad = value
                if username == self.follow_player:
                    if cell != self.player.CELL:
                        self.followed_player_cell = cell
                for player in self.player_in_area[:]:
                    if player.str_username.lower() == username.lower():
                        if cell:
                            player.str_frame = cell
                        if pad:
                            player.str_pad = pad
                        break
            elif "respawnMon" in msg:
                # ``%xt%respawnMon%-1%<MonMapID>%``: a monster is back.  It carries
                # no name and no cell, so it cannot be *added* to the list -- but
                # it does say the map's monster state moved on, which is the hint
                # ``jump_to_monster`` needs when its target is nowhere to be found.
                # Ignoring this packet outright (it used to be a bare ``pass``) is
                # why a bot parked at a map's spawn could not walk back to a
                # monster that had respawned: /shadowblast's "stuck at Enter".
                parts = msg.split("%")
                mon_id = parts[4] if len(parts) > 4 else ""
                for mon in self.monsters:
                    if mon.mon_map_id == mon_id:
                        mon.is_alive = True
                        break
                self.monsters_stale = True
            elif "chatm" in msg:
                if self.showChat:
                    msg = msg.split('%')
                    text = msg[4].replace("zone~", ": ").replace("guild~", "[GUILD]: ").replace("party~", "[PARTY]: ")
                    sender = msg[5]
                    print(Fore.MAGENTA + f"[{datetime.now().strftime('%H:%M:%S')}] {sender} {text}" + Fore.WHITE)
            elif "whisper" in msg:
                if self.showChat:
                    msg = msg.split('%')
                    text = msg[4]
                    sender = msg[5]
                    print(Fore.MAGENTA + f"[{datetime.now().strftime('%H:%M:%S')}] {sender} [WHISPER] : {text}" + Fore.WHITE)
            elif f"Your status is now Away From Keyboard" in msg:
                if self.isScriptable and self.auto_relogin:
                    print("Relogin and restart bot on AFK...")
                    self.request_relogin("AFK")
                elif not self.isScriptable and self.restart_on_afk:
                    print("Restart cmds on AFK...")
                    self.index = 0
                    pass
            elif "invalid session" in msg:
                if self.isScriptable and self.auto_relogin:
                    print("Relogin and restart bot on invalid session...")
                    self.request_relogin("invalid session")

    async def check_registered_quest_completion(self, item_id, is_temp: bool = False):
        for registered_quest_id in self.registered_auto_quest_ids:
            if self.can_turn_in_quest(registered_quest_id):
                self.turn_in_quest(registered_quest_id)

    async def read_server_in_background(self):
        """Background task to read and handle messages.

        A read that comes back *instantly* with nothing in it is a broken socket,
        not the reader's own one-second idle timeout -- and looping straight back
        onto one is a busy loop: an orphaned reader whose session had already
        ended kept calling ``recv`` on its closed socket and ate a whole core,
        for as long as the process lived.  A few of those, one per relogin, is
        what made the CPU climb over a long run.  So: a fast empty read is
        counted, spaced out, and after three in a row the session is dropped --
        which is what lets the relogin (or the app) take over cleanly.
        """
        failures = 0
        while self.is_client_connected:
            try:
                started = time.monotonic()
                messages = await self.read_batch_async(self.client_socket)
                elapsed = time.monotonic() - started
                if messages:
                    failures = 0
                    for msg in messages:
                        if msg.startswith("Z"):
                            msg = self.decompress_message(msg)
                        await self.handle_server_response(msg)
                    continue
                if elapsed < READ_FAIL_FAST_S:
                    failures += 1
                    if failures >= READ_FAILURES_BEFORE_DROP:
                        print("[ws] the socket stopped answering; dropping the "
                              "session so it can be re-established.")
                        self.is_client_connected = False
                        break
                    await asyncio.sleep(READ_FAIL_FAST_S)
                    continue
                failures = 0
            except CustomError as e:
                print(f"Critical error encountered: {e}")
                self.run = False  # Stop the bot
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"Unexpected error in testasync: {e}")
                tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
                print(tb_str)
                if self.is_client_connected == False and self.auto_relogin == False:
                    raise Exception("Connection closed by the server.")
                await asyncio.sleep(READ_FAIL_FAST_S)
        if self.client_socket:
            self.client_socket.close()
    
    async def read_batch_async(self, conn):
        """
        Asynchronous version of read_batch to avoid blocking.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.read_batch, conn)

    def read_batch(self, conn):
        message_builder = ""
        complete_messages = []

        conn.settimeout(1.0)

        while self.is_client_connected:
            try:
                buf = conn.recv(1024)

                if not buf:
                    print("Server closed connection (EOF)")
                    self.is_client_connected = False
                    break

                message_builder += buf.decode("utf-8")

                if not message_builder.endswith("\x00"):
                    continue

                messages = message_builder.split("\x00")
                message_builder = ""  # reset buffer

                for msg in messages:
                    msg = msg.strip()
                    if not msg:
                        continue
                    if (
                        self.is_valid_json(msg)
                        or self.is_valid_xml(msg)
                        or (msg.startswith("%") and msg.endswith("%"))
                        or msg.startswith("Z")
                    ):
                        complete_messages.append(msg)

                if complete_messages:
                    return complete_messages

            except socket.timeout:
                return []

            except ConnectionResetError:
                print("Connection reset by peer")
                self.is_client_connected = False
                break

            except Exception as e:
                print("Unexpected socket error:", e)
                return []

        return []
    
    def write_message(self, message):
        # print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        self.last_send_ts = time.time()
        self.packets_sent += 1
        if self.client_socket is None:
            return "Error: Connection is not established"
        try:
            self.client_socket.sendall((message + "\u0000").encode('utf-8'))
        except socket.error as e:
            return f"Error writing to the connection: {e}"
        return None

    def decompress_message(self, msg: str) -> str:
        """Decompress a message if it starts with 'Z' using Base64 and Zlib."""
        if msg.startswith("Z"):
            try:
                b64_data = msg[1:]
                decompressed = zlib.decompress(base64.b64decode(b64_data))
                return decompressed.decode("utf-8")
            except zlib.error:
                try:
                    decompressed = zlib.decompress(base64.b64decode(b64_data), -zlib.MAX_WBITS)
                    return decompressed.decode("utf-8")
                except Exception as e:
                    print(f"Error decompressing Z packet: {e}")
                    return msg
            except Exception as e:
                print(f"Error decompressing Z packet: {e}")
                return msg
        return msg

    def is_valid_json(self, s):
        try:
            json.loads(s)
            return True
        except json.JSONDecodeError:
            return False

    def is_valid_xml(self, s):
        try:
            ElementTree.fromstring(s)
            return True
        except ElementTree.ParseError:
            return False
    
    async def goto_player(self, player_name):
        player_found = next((p for p in self.player_in_area if p.str_username.lower() == player_name.lower()), None)
        if player_found:
            self.jump_cell(player_found.str_frame, player_found.str_pad)
        else:
            self.write_message(f"%xt%zm%cmd%1%goto%{player_name}%")
        
    def get_drop(self, user_id, item_id):
        packet = f"%xt%zm%getDrop%{user_id}%{item_id}%"
        self.write_message(packet)
    
    def accept_quest(self, quest_id: int):
        quest_id = normalize_quest_id(quest_id)
        self.write_message(f"%xt%zm%acceptQuest%{self.areaId}%{quest_id}%")
        self.do_wait(500)
        
    def turn_in_quest(self, quest_id: int, item_id: int = -1, qty: int = 1):
        quest_id = normalize_quest_id(quest_id)
        packet = f"%xt%zm%tryQuestComplete%{self.areaId}%{quest_id}%{item_id}%false%{qty}%wvz%"
        self.write_message(packet)
        self.do_wait(500)

    def use_scroll(self, monsterid, max_target):
        """Cast the equipped scroll/potion at up to ``max_target`` monsters.

        The scroll fired is always ``bot.scroll_id``, set by
        :meth:`Command.equip_scroll`. Callers reach this through
        ``use_skill(5, ...)``; there is no per-call scroll id, matching the
        android tree and ``bot/templeshrine``'s usage.

        Args:
            monsterid: Monster map ids to target.
            max_target (int): Cap on how many get targeted.
        """
        self.target = [f"i1>m:{i}" for i in monsterid][:max_target]
        self.write_message(f"%xt%zm%gar%1%0%{','.join(self.target)}%{self.scroll_id}%wvz%")
        
    def use_potion(self, potion_id):
        self.write_message(f"%xt%zm%gar%1%0%i1>p:{self.user_id}%{potion_id}%wvz%")

    def use_skill_to_monster(self, skill, monsters_id, max_target):
        if not monsters_id:
            return
        for mon in self.monsters:
            if mon.mon_map_id == str(monsters_id[0]):
                self.player.setLastTarget(mon)
                break
        self.target = [f"a{skill}>m:{i}" for i in monsters_id][:max_target]
        self.write_message(f"%xt%zm%gar%1%0%{','.join(self.target)}%wvz%")
        # print(f"[{datetime.now().strftime('%H:%M:%S')}] tgt_mon: {self.target}")

    def use_skill_to_player(self, skill, max_target):
        self.target = [f"a{skill}>p:{i}" for i in self.user_ids][:max_target-1]
        self.target.insert(0, f"a{skill}>p:{self.username_id}")
        final_target = []
        for tgt in self.target:
            if tgt not in final_target:
                final_target.append(tgt)
        self.write_message(f"%xt%zm%gar%1%0%{','.join(final_target)}%wvz%")
        # print(f"[{datetime.now().strftime('%H:%M:%S')}] tgt_p: {','.join(final_target)}")
    
    def use_skill_to_myself(self, skill):
        self.write_message(f"%xt%zm%gar%1%0%a{skill}>p:{self.username_id}%wvz%")

    def do_wait(self, wait_ms: int):
        self.wait_ms = wait_ms/1000

    def extract_user_ids(self, xml_message: str):
        root = ET.fromstring(xml_message)
        self.user_ids = []
        self.username_id = None
        for user in root.findall(".//u"):
            user_id: str = user.get("i")
            self.user_ids.append(user_id)  # Append to the list
            name: str = user.find("n").text  # Get the username
            if name.lower() == self.player.USER.lower():
                self.username_id = user_id  # Store the ID of the target username
        # self.user_id used to be assigned inside the loop, so it was left
        # pointing at whichever <u> element happened to come last -- anyone in
        # the cell but us. Everything that identifies this player reads it: the
        # respawn packets in check_alive() and death_handler, the potion target
        # in use_potion(), get_user_id(), and the tInf comparisons in
        # bot/templeshrine. Pin it to our own id instead.
        if self.username_id is not None:
            self.user_id = self.username_id

    def extract_new_user(self, xml_message: str):
        root = ET.fromstring(xml_message)
        newId = root.find(".//u").get("i")
        self.user_ids.append(newId)
    
    def extract_remove_user(self, xml_message: str):
        root = ET.fromstring(xml_message)
        toRemove = root.find(".//user").get("id")
        for i in self.user_ids:
            if i == toRemove:
                self.user_ids.remove(i)
                break
        
    async def ensure_leave_from_combat(self, sleep_ms: int = 2000, always: bool = False):
        if self.player.IS_IN_COMBAT or always:
            self.jump_cell(self.player.CELL, self.player.PAD)
            await asyncio.sleep(sleep_ms/1000)
        
    def jump_cell(self, cell: str, pad: str = "Left"):
        msg = f"%xt%zm%moveToCell%{self.areaId}%{cell}%{pad}%"
        self.player.CELL = cell
        self.player.PAD = pad
        self.player.setPlayerPositionXY(0,0)
        self.write_message(msg)

    async def walk_to(self, x: int, y: int, speed = 8):
        self.write_message(f"%xt%zm%mv%{self.areaId}%{x}%{y}%{speed}%")
        self.player.setPlayerPositionXY(x, y)
    
    def find_best_cell(self, monster_name, byMostMonster: bool = True, byAliveMonster: bool = False):
        if not self.monsters:
            return None
        if monster_name.startswith('id.'):
            monster_name = monster_name.split('.')[1]

        def _is_match(mon):
            if not mon.frame:
                return False
            if monster_name == "*":
                return True
            return mon.mon_name.lower() == monster_name.lower() or str(mon.mon_map_id) == str(monster_name)

        if byAliveMonster:
            filtered_monsters = [mon for mon in self.monsters if _is_match(mon) and mon.is_alive and mon.current_hp > 0]
            if not filtered_monsters:
                filtered_monsters = [mon for mon in self.monsters if _is_match(mon)]
        else:
            filtered_monsters = [mon for mon in self.monsters if _is_match(mon)]

        if not filtered_monsters:
            return None

        cell_counts = {}
        for mon in filtered_monsters:
            if mon.frame:
                cell_counts[mon.frame] = cell_counts.get(mon.frame, 0) + 1

        if not cell_counts:
            return None

        return max(cell_counts, key=cell_counts.get)

    def get_loaded_quest(self, quest_id) -> Optional[Quest]:
        """The tracked :class:`Quest` with this id, or ``None``.

        A quest present in :attr:`loaded_quest_datas` is in progress -- the
        server only lists it in ``getQuests`` once it has been accepted.  The
        id is normalised, so a wire string and a script int agree; an id that
        is not a number (``0``) matches nothing.
        """
        wanted = normalize_quest_id(quest_id)
        if wanted <= 0:
            return None
        for loaded_quest in self.loaded_quest_datas:
            if loaded_quest.quest_id == wanted:
                return loaded_quest
        return None

    def loaded_quest_ids(self) -> list:
        """Ids of every quest currently tracked as in progress."""
        return [quest.quest_id for quest in self.loaded_quest_datas]

    def can_turn_in_quest(self, questId: int) -> bool:
        quest = self.get_loaded_quest(questId)
        return bool(quest and quest.requirements_met(self.player))

    def quest_not_in_progress(self, quest_id: int) -> bool:
        """Return True when the quest is not currently tracked in progress."""
        return self.get_loaded_quest(quest_id) is None

    def reset_cmds(self):
        self.index = 0
        self.cmds = []
        
    def add_cmd(self, cmd):
        self.cmds.append(cmd)
        
    def add_cmds(self, cmds):
        self.cmds.extend(cmds)
    
    def start_battle_analyzer(self):
        self.battle_analyzer: bool = True
        self.battle_analyzer_time_start: datetime = datetime.now()
        self.battle_analyzer_total_damage: int = 0
        self.battle_analyzer_last_print: datetime = self.battle_analyzer_time_start
    
    def stop_battle_analyzer(self):
        self.battle_analyzer: bool = False
        self.battle_analyzer_time_start: datetime = None
        self.battle_analyzer_total_damage: int = 0
    
    def get_player_in_area(self, player_name: str) -> Optional[PlayerArea]:
        for player in self.player_in_area:
            if player_name.lower() == player.str_username.lower():
                return player
        return None

    def is_player_hp_below(self, player_name: str, percent: float) -> bool:
        player = self.get_player_in_area(player_name)
        if player is None:
            return False
        return player.is_hp_below(percent)

class CustomError(Exception):
    """Exception raised for custom error in the application."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message
    
    def get_message(self):
        return self.message
