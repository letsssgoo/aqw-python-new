"""Army sync for Ultra V2: named steps and signals over ``bot.ultra.party``.

The reference keeps a line-based ``.sync`` file per script (``START``, ``READY``,
``STEP``, ``ARRIVE``, ``SIGNAL``, ``STOP``) and walks it with a leader/follower
protocol.  This engine already has the transport -- ``bot/ultra/party.py``, one
folder per run id, markers per pane -- so V2 uses it instead of inventing a
second one:

* :meth:`Sync.step` is the reference's ``SyncArmy(step)`` -- a barrier every pane
  must reach before the fight moves on;
* :meth:`Sync.signal` / :meth:`Sync.read` are ``SendArmySignal`` /
  ``HasArmySignal``, with the value stored beside the marker;
* :meth:`Sync.stop` is ``StopArmySync(reason)``: every pane sees the abort and
  unwinds at its next step.

A barrier that times out does **not** wedge the run (party.barrier's contract):
the pane proceeds and says so, because one dead pane must not hang the other
three forever.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional, Sequence

from bot.ultra import party

#: One army is four panes; every ultra in scope is a four-player fight.
PARTY_SIZE = 4
SLOTS: Sequence[int] = (1, 2, 3, 4)
#: A step waits this long before conceding and moving on.
STEP_TIMEOUT_S = 180


class Sync:
    """Step / signal bookkeeping for one pane of one ultra run."""

    def __init__(self, ultra: str, slot: int, size: int = PARTY_SIZE):
        self.ultra = ultra
        self.slot = int(slot)
        self.size = int(size)
        #: Session name in the party folder -- one per ultra, so two ultras in
        #: the same run id do not read each other's markers.
        self.name = f"v2_{ultra}"

    @property
    def enabled(self) -> bool:
        """False for a lone bot: no ``AQW_RUN_ID`` means no party to wait for."""
        return party.enabled()

    # --- barriers ------------------------------------------------------
    async def step(self, step: str, timeout: int = STEP_TIMEOUT_S) -> bool:
        """Wait for the whole party to reach ``step``; False when stopped.

        Async on purpose: ``party.barrier`` blocks on ``time.sleep``, which
        would freeze the packet reader for the length of the wait.  The marker
        file is the same one v1 writes, so the two share a directory unchanged.
        """
        if self.aborted():
            return False
        if not self.enabled:
            return True

        name = f"{self.name}.{step}"
        directory = party._dir()
        key = party._safe_key(self.slot)
        try:
            (directory / f"{name}.{key}.ready").write_text(
                str(time.time()), encoding="utf-8")
        except Exception:
            return self.aborted() is None

        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.aborted():
                return False
            try:
                if len(list(directory.glob(f"{name}.*.ready"))) >= self.size:
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.2)

        # Keep going, loudly: the other pane may have died, and hanging here
        # would leave the survivor unable to finish its own quest.
        print(f"[v2] step {step}: the party did not fill in {timeout}s; "
              f"carrying on.")
        return self.aborted() is None

    # --- signals -------------------------------------------------------
    def signal(self, name: str, value: Any = True) -> None:
        party.publish(f"{self.name}.{name}", self.slot, value)

    def read(self, name: str) -> Dict[int, Any]:
        return party.published(f"{self.name}.{name}", SLOTS)

    def clear_signal(self, name: str) -> None:
        party.clear_signal(f"{self.name}.{name}", SLOTS)

    # --- stop / done ---------------------------------------------------
    def stop(self, reason: str) -> None:
        """Publish the abort so every pane unwinds at its next step."""
        for slot in SLOTS:
            party.mark_abort(self.name, slot, reason)

    def aborted(self) -> Optional[str]:
        return party.any_abort(self.name, SLOTS)

    def mark_done(self) -> None:
        party.mark_done(self.name, self.slot)

    def all_done(self) -> bool:
        return party.all_done(self.name, SLOTS)
