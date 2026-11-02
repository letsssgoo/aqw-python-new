"""The Scroll of Enrage gate shared by Temple and Eclipse.

A dungeon iteration needs every pane to carry the taunt scroll: if the taunter
runs dry mid-run the party wipes and the iteration is wasted.  So before each
iteration every pane reports its count; when one is under :data:`MIN_ENRAGE`
the whole party leaves for the safe map, crafts towards :data:`MAX_ENRAGE`,
and only then goes back in.

The gate is a small thread-safe rendezvous.  The hub passes one instance to
all four panes (``Bot.scroll_gate``); a standalone pane has no gate and just
checks itself.  A pane that never reports (crash, failed login) cannot hang the
rest: the report falls back to that pane's own count after a timeout.
"""
from __future__ import annotations

import threading
import time

from bot.ultra.v2 import scrolls as v2_scrolls

#: Minimum every pane must hold before a dungeon iteration starts.
MIN_ENRAGE = 50
#: What the crafting turns aim for; the scroll's stack cap.
MAX_ENRAGE = 1000
#: Where the party waits while crafting (out of the dungeon).
SAFE_MAP = "yulgar"
#: How long a pane waits for the other three to report before deciding alone.
REPORT_TIMEOUT_S = 20.0
#: How long the party waits for everyone to be out of the dungeon.
LEAVE_TIMEOUT_S = 90.0
#: How long the party waits for everyone to finish crafting (turn-ins are slow).
CRAFT_TIMEOUT_S = 1800.0


class PartyScrollGate:
    """One scroll-count meeting per dungeon iteration, plus leave/craft barriers."""

    def __init__(self, size: int = 4):
        self.size = int(size)
        self._lock = threading.Lock()
        self._epoch = 0
        self._reports: dict = {}
        self._decisions: dict = {}
        self._marks: dict = {}

    def report(self, key: str, qty: int,
               timeout: float = REPORT_TIMEOUT_S):
        """Wait for every pane's count; return ``(epoch, any_short)``.

        The last pane to arrive decides for the whole meeting, so all panes
        read the same answer.  On timeout the pane falls back to its own count
        instead of blocking the party forever.
        """
        with self._lock:
            epoch = self._epoch
            self._reports.setdefault(epoch, {})[key] = int(qty)
            if len(self._reports[epoch]) >= self.size:
                short = any(value < MIN_ENRAGE
                            for value in self._reports[epoch].values())
                self._decisions[epoch] = short
                self._epoch = epoch + 1

        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if epoch in self._decisions:
                    return epoch, self._decisions[epoch]
            time.sleep(0.05)
        return epoch, int(qty) < MIN_ENRAGE

    def barrier(self, name: str, key: str, epoch: int,
                timeout: float) -> bool:
        """Wait until all four panes have reached ``name`` for ``epoch``."""
        with self._lock:
            self._marks.setdefault((name, epoch), set()).add(key)
            done = len(self._marks[(name, epoch)]) >= self.size
        deadline = time.time() + timeout
        while not done and time.time() < deadline:
            with self._lock:
                done = len(self._marks.get((name, epoch), set())) >= self.size
            if not done:
                time.sleep(0.1)
        return done


async def _leave_dungeon(cmd) -> None:
    """Walk out to the safe map so crafting happens outside the instance."""
    await cmd.join_map(SAFE_MAP)
    try:
        await cmd.rest()
    except Exception:
        pass
    await cmd.sleep(1000)


async def _craft(cmd) -> None:
    await v2_scrolls.prepare(cmd, v2_scrolls.ENRAGE, minimum=MIN_ENRAGE,
                             target=MAX_ENRAGE)
    # Slot 5 must carry the scroll again once the crafting is done.
    try:
        await cmd.equip_scroll(v2_scrolls.ENRAGE)
    except Exception:
        pass


async def ensure(cmd) -> None:
    """Run the gate before one dungeon iteration (see the module docstring)."""
    key = str(getattr(cmd.bot.player, "USER", "") or "")
    qty = cmd.get_quant_item(v2_scrolls.ENRAGE)
    gate = getattr(cmd.bot, "scroll_gate", None)

    if gate is None:
        # Standalone pane: nobody else to coordinate with.
        if qty < MIN_ENRAGE:
            cmd.bot.log(f"[temple] Scroll of Enrage {qty} < {MIN_ENRAGE}; "
                        f"leaving to craft up to {MAX_ENRAGE}.")
            await _leave_dungeon(cmd)
            await _craft(cmd)
        return

    epoch, short = gate.report(key, qty)
    if not short:
        return
    cmd.bot.log(f"[temple] Scroll of Enrage {qty} < {MIN_ENRAGE}; the party "
                f"leaves the dungeon to craft up to {MAX_ENRAGE}.")
    await _leave_dungeon(cmd)
    gate.barrier("left", key, epoch, timeout=LEAVE_TIMEOUT_S)
    await _craft(cmd)
    gate.barrier("crafted", key, epoch, timeout=CRAFT_TIMEOUT_S)
