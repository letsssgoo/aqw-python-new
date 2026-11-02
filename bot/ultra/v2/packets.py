"""Packet watchers fed by the bot's subscriber list.

``CoreLoneWolf`` arms its detectors on the client's packet stream
(``Bot.Flash.FlashCall``) and each script polls ``HasPacketDetection``.  The
engine's equivalent of that stream is :meth:`core.bot.Bot.notify_subscribers`:
it fires for **every** inbound message, before the bot parses it, so a watcher
sees exactly the text the reference matches on and can never swallow a packet
another subscriber needs.

:meth:`core.command.Command.subscribe` / ``bot.subscribe`` is the same hook
``bot/ultra/core_ultra.py`` uses (``self.cmd.bot.subscribe(self.message_handler)``).
The older ``handle_server_response`` wrapping is kept only as a fallback for a
bot object without a subscriber list (the test stubs), never as the primary
path.
"""
from __future__ import annotations

import json
from typing import Optional


class _Watcher:
    """Attach to the bot's message stream; subclasses implement ``inspect``."""

    def __init__(self, bot):
        self.bot = bot
        self.running = False
        self._callback = None
        self._original = None

    # ---------------------------------------------------------------- attach
    def _attach(self) -> bool:
        self._detach()
        subscribe = getattr(self.bot, "subscribe", None)
        if callable(subscribe):
            self._callback = self._on_message
            try:
                subscribe(self._callback)
            except Exception:
                self._callback = None
            else:
                self.running = True
                return True

        # Fallback: a bot without a subscriber list.  Chain whatever handler is
        # installed so the bot still processes the packet afterwards.
        handler = getattr(self.bot, "handle_server_response", None)
        if handler is None:
            return False
        self._original = handler

        async def wrapped(msg):
            result = await handler(msg)
            self._guard(msg)
            return result

        try:
            self.bot.handle_server_response = wrapped
        except Exception:
            self._original = None
            return False
        self.running = True
        return True

    def _detach(self) -> None:
        self.running = False
        callback, self._callback = self._callback, None
        if callback is not None:
            unsubscribe = getattr(self.bot, "unsubscribe", None)
            if callable(unsubscribe):
                try:
                    unsubscribe(callback)
                except Exception:
                    pass
        if self._original is not None:
            try:
                self.bot.handle_server_response = self._original
            except Exception:
                pass
            self._original = None

    # -------------------------------------------------------------- dispatch
    def _on_message(self, msg) -> None:
        """Subscriber callback -- synchronous, and never raises into the loop."""
        self._guard(msg)

    def _guard(self, msg) -> None:
        if not self.running:
            return
        try:
            self.inspect(msg)
        except Exception:
            pass

    def inspect(self, msg) -> None:      # pragma: no cover - abstract
        raise NotImplementedError


class PacketDetector(_Watcher):
    """Count responses whose ``cmd`` matches and whose body carries ``text``."""

    def __init__(self, bot, command: str = "ct", text: str = "Abyss!"):
        super().__init__(bot)
        self.command = command
        self.text = text
        self.count = 0
        self.history: list = []

    def start(self) -> bool:
        """Arm the detector; False when there is nothing to hook."""
        self.count = 0
        self.history = []
        return self._attach()

    def inspect(self, msg: str) -> None:
        """Count one response; ignore anything that is not our packet."""
        if not msg or '"cmd"' not in msg:
            return
        try:
            data = json.loads(msg.strip())["b"]["o"]
        except Exception:
            return
        if data.get("cmd") != self.command:
            return
        if self.text.lower() in json.dumps(data).lower():
            self.count += 1
            self.history.append(data)

    def seen(self, detection: int) -> bool:
        """``HasPacketDetection``: at least ``detection`` matches so far."""
        return bool(self.running and detection > 0 and self.count >= detection)

    def stop(self) -> None:
        """Disarm and detach from the bot's subscribers."""
        self._detach()

    @property
    def armed(self) -> Optional[bool]:
        """True when armed; None keeps the type honest for callers."""
        return True if self.running else None


class ZoneWatcher(_Watcher):
    """Record ``zoneSet`` events off ``event`` packets -- the ``RunToArea`` feed.

    Ultra Dage's boss room announces two walk zones ("A" and "B", empty for the
    middle) and the reference walks to a fixed spot for each; ``DrainZoneEvents``
    turns those letters into ``WalkTo`` calls.  The engine has no Flash event
    bus, so the same letter comes from the ``event`` packet's ``args.zoneSet`` --
    the field ``bot/slavery/bot_slave.py`` already walks on for Astral Empyrean.
    """

    def __init__(self, bot):
        super().__init__(bot)
        self.events: list = []

    def start(self) -> bool:
        """Arm the listener; False when there is nothing to hook."""
        self.events.clear()
        return self._attach()

    def inspect(self, msg: str) -> None:
        if not msg or '"cmd"' not in msg:
            return
        try:
            data = json.loads(msg.strip())["b"]["o"]
        except Exception:
            return
        if data.get("cmd") != "event":
            return
        zone = (data.get("args") or {}).get("zoneSet")
        if zone is None:
            return
        self.events.append(str(zone))

    def drain(self) -> list:
        """Take everything seen since the last drain."""
        drained, self.events = self.events, []
        return drained

    def stop(self) -> None:
        self._detach()


class MarkerWatcher(_Watcher):
    """Count packets whose raw text carries the ``markers``.

    Ultra Gramiel's detectors match raw fragments of the packet, not parsed
    fields: ``"animStr":"Charge"``, ``"cInf":"m:2"``, ``Liberator``.  One
    matching packet counts once, even when several markers overlap.
    """

    def __init__(self, bot, command: str = "ct", markers=(),
                 require_all: bool = True, choice: bool = False):
        super().__init__(bot)
        self.command = command
        self.markers = tuple(m for m in markers if m)
        #: ``StartPacketDetector`` matches only when **every** marker is in the
        #: packet; ``StartPacketChoiceDetector`` reports the first one it finds.
        self.require_all = require_all
        self.choice = choice
        self.count = 0
        self.last = ""          # which marker matched most recently
        self.history: list = []  # every match, in arrival order

    def start(self) -> bool:
        self.count = 0
        self.history = []
        if not self.markers:
            return False
        return self._attach()

    def inspect(self, msg: str) -> None:
        if not msg:
            return
        # Match on a space-free copy: the server is free to pretty-print the
        # JSON, and the reference compares the packet text itself.
        flat = msg.replace(" ", "")
        if self.command and f'"cmd":"{self.command}"' not in flat:
            return
        present = [marker for marker in self.markers
                   if marker.replace(" ", "") in flat]
        if not present:
            return
        if self.require_all and not self.choice and len(present) != len(self.markers):
            return
        # Speaker's choice detector wants the first warning it finds; the
        # animation detectors want the animation marker itself, which is last.
        matched = present[0] if self.choice else present[-1]
        self.last = matched
        self.history.append(matched)
        self.count += 1

    def seen(self, detection: int) -> bool:
        return bool(self.running and detection > 0 and self.count >= detection)

    def drain_history(self) -> list:
        """Take the matches seen since the last drain, in order."""
        drained, self.history = self.history, []
        return drained

    def stop(self) -> None:
        self._detach()
