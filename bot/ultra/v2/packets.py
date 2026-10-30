"""Packet detector -- count matching server responses (``StartPacketDetector``).

Ultra Nulgath's slot 4 cannot see the boss's ``Abyss!`` cast in its own state:
the packet is the only evidence that a taunt is due, so the reference arms a
detector on the ``ct`` command and asks ``HasPacketDetection(n)`` (``count >=
n``) how many casts it has seen.

The hook chains the existing ``Bot.handle_server_response`` the same way
:mod:`bot.ultra.telemetry` does -- the previous handler still runs first, so a
detector can never swallow a packet another subscriber needs.
"""
from __future__ import annotations

import json
from typing import Optional


class PacketDetector:
    """Count responses whose ``cmd`` matches and whose body carries ``text``."""

    def __init__(self, bot, command: str = "ct", text: str = "Abyss!"):
        self.bot = bot
        self.command = command
        self.text = text
        self.count = 0
        self.running = False
        self._original = None

    def start(self) -> bool:
        """Arm the detector; False when there is nothing to hook."""
        self.stop()
        handler = getattr(self.bot, "handle_server_response", None)
        if handler is None or not self.command or not self.text:
            return False
        self._original = handler

        async def wrapped(msg):
            result = await handler(msg)
            try:
                self.inspect(msg)
            except Exception:
                pass
            return result

        try:
            self.bot.handle_server_response = wrapped
        except Exception:
            self._original = None
            return False
        self.count = 0
        self.running = True
        return True

    def inspect(self, msg: str) -> None:
        """Count one response; ignore anything that is not our packet."""
        if not self.running or not msg or '"cmd"' not in msg:
            return
        try:
            data = json.loads(msg.strip())["b"]["o"]
        except Exception:
            return
        if data.get("cmd") != self.command:
            return
        if self.text.lower() in json.dumps(data).lower():
            self.count += 1

    def seen(self, detection: int) -> bool:
        """``HasPacketDetection``: at least ``detection`` matches so far."""
        return bool(self.running and detection > 0 and self.count >= detection)

    def stop(self) -> None:
        """Disarm, putting the previous handler back."""
        self.running = False
        if self._original is not None:
            try:
                self.bot.handle_server_response = self._original
            except Exception:
                pass
        self._original = None

    @property
    def armed(self) -> Optional[bool]:
        """True when armed; None keeps the type honest for callers."""
        return True if self.running else None


class ZoneWatcher:
    """Record ``zoneSet`` events off ``ct`` packets -- the ``RunToArea`` feed.

    Ultra Dage's boss room announces two walk zones ("A" and "B", empty for the
    middle) and the reference walks to a fixed spot for each; ``DrainZoneEvents``
    below turns those letters into ``WalkTo`` calls.  The engine has no Flash
    event bus, so the same letter comes from the ``event`` packet's
    ``args.zoneSet`` -- the field ``bot/slavery/bot_slave.py`` already walks on
    for Astral Empyrean -- chained like :class:`PacketDetector` so the previous
    handler still runs.
    """

    def __init__(self, bot):
        self.bot = bot
        self.events: list = []
        self.running = False
        self._original = None

    def start(self) -> bool:
        """Arm the listener; False when there is nothing to hook."""
        self.stop()
        handler = getattr(self.bot, "handle_server_response", None)
        if handler is None:
            return False
        self._original = handler

        async def wrapped(msg):
            result = await handler(msg)
            try:
                self.inspect(msg)
            except Exception:
                pass
            return result

        try:
            self.bot.handle_server_response = wrapped
        except Exception:
            self._original = None
            return False
        self.events.clear()
        self.running = True
        return True

    def inspect(self, msg: str) -> None:
        if not self.running or not msg or '"cmd"' not in msg:
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
        self.running = False
        if self._original is not None:
            try:
                self.bot.handle_server_response = self._original
            except Exception:
                pass
        self._original = None


class MarkerWatcher:
    """Count packets whose raw text carries any of ``markers``.

    Ultra Gramiel's detectors match raw fragments of the packet, not parsed
    fields: ``"animStr":"Charge"``, ``"cInf":"m:2"``, ``Liberator``.  One
    matching packet counts once, even when several markers overlap.
    """

    def __init__(self, bot, command: str = "ct", markers=()):
        self.bot = bot
        self.command = command
        self.markers = tuple(m for m in markers if m)
        self.count = 0
        self.running = False
        self._original = None

    def start(self) -> bool:
        self.stop()
        handler = getattr(self.bot, "handle_server_response", None)
        if handler is None or not self.markers:
            return False
        self._original = handler

        async def wrapped(msg):
            result = await handler(msg)
            try:
                self.inspect(msg)
            except Exception:
                pass
            return result

        try:
            self.bot.handle_server_response = wrapped
        except Exception:
            self._original = None
            return False
        self.count = 0
        self.running = True
        return True

    def inspect(self, msg: str) -> None:
        if not self.running or not msg:
            return
        # Match on a space-free copy: the server is free to pretty-print the
        # JSON, and the reference compares the packet text itself.
        flat = msg.replace(" ", "")
        if self.command and f'"cmd":"{self.command}"' not in flat:
            return
        if any(marker.replace(" ", "") in flat for marker in self.markers):
            self.count += 1

    def seen(self, detection: int) -> bool:
        return bool(self.running and detection > 0 and self.count >= detection)

    def stop(self) -> None:
        self.running = False
        if self._original is not None:
            try:
                self.bot.handle_server_response = self._original
            except Exception:
                pass
        self._original = None
