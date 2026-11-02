"""The Scroll of Enrage gate shared by Temple and Eclipse.

A dungeon iteration needs every pane to carry the taunt scroll: if the taunter
runs dry mid-run the party wipes and the iteration is wasted.  So each pane
publishes its count; when the master sees one under :data:`MIN_ENRAGE` it
raises the party flag, every pane leaves for the safe map, crafts towards
:data:`MAX_ENRAGE`, and then goes back in.

The gate is deliberately **non-blocking** while fighting: publishing a count
is a dict write, and the only state the other panes poll is a flag.  An earlier
version made every pane wait for a four-way meeting on each loop pass, which
stalled combat whenever one pane was slower or disconnected.

The hub passes one instance to all four panes (``Bot.scroll_gate``); a
standalone pane has no gate and just checks itself.
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
#: How long a pane waits for the rest of the party to finish crafting.
CRAFT_TIMEOUT_S = 1800.0


class PartyScrollGate:
    """Latest scroll count per pane plus the shared "party is crafting" flag."""

    def __init__(self, size: int = 4):
        self.size = int(size)
        self._lock = threading.Lock()
        self.counts: dict = {}
        self.crafting = False
        self._left: set = set()
        self._crafted: set = set()

    def publish(self, key: str, qty: int) -> None:
        """Record this pane's count; never blocks."""
        with self._lock:
            self.counts[key] = int(qty)

    def short(self):
        """True when any known pane is under the minimum; None while unknown."""
        with self._lock:
            if len(self.counts) < self.size:
                return None
            return any(value < MIN_ENRAGE for value in self.counts.values())

    def start_craft(self) -> None:
        with self._lock:
            self.crafting = True
            self._left.clear()
            self._crafted.clear()

    def mark_left(self, key: str) -> None:
        with self._lock:
            self._left.add(key)

    def mark_crafted(self, key: str) -> None:
        with self._lock:
            self._crafted.add(key)

    def all_crafted(self) -> bool:
        with self._lock:
            return len(self._crafted) >= self.size

    def craft_done(self) -> None:
        with self._lock:
            self.crafting = False


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


async def ensure(cmd, *, is_master: bool = False) -> None:
    """Run the gate for one loop pass (see the module docstring)."""
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

    gate.publish(key, qty)

    # Only the master decides.  It does not matter whether the party is inside
    # the dungeon at this instant: the whole point is to catch a short pane
    # before the next pull, and the loop runs between cells as well.
    if is_master and not gate.crafting and gate.short() is True:
        gate.start_craft()
        cmd.bot.log(f"[temple] a pane holds under {MIN_ENRAGE} Scroll of "
                    f"Enrage; the party leaves to craft up to {MAX_ENRAGE}.")

    if not gate.crafting:
        return

    await _leave_dungeon(cmd)
    gate.mark_left(key)
    await _craft(cmd)
    gate.mark_crafted(key)

    # Nobody re-enters until the whole party is done: the master clears the
    # flag, everyone else waits for it to clear.
    deadline = time.time() + CRAFT_TIMEOUT_S
    while time.time() < deadline:
        if is_master:
            if gate.all_crafted():
                gate.craft_done()
                cmd.bot.log("[temple] every pane finished crafting; going "
                            "back in.")
                return
        elif not gate.crafting:
            return
        await cmd.sleep(1000)
