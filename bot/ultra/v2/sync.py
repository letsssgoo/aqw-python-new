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
three forever -- unless the caller asks for ``strict``, which is what the
pre-pull gates do: walking into the boss room a pane short is worse than
stopping.

Markers are only honoured while the pane that wrote them is still **waiting** on
that step: every waiting pane rewrites its marker twice a second, and a barrier
counts only markers newer than the moment this pane arrived.  Before that, a
marker left behind by an earlier attempt (or by an earlier run that reused the
same run id) made the barrier pass on its own, so the party pulled while one
pane was still setting up.
"""
from __future__ import annotations

import asyncio
import json
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

    #: How much older than this pane's own arrival another pane's marker may be
    #: and still count.  Panes start within a second of each other; a marker
    #: older than that belongs to an earlier attempt, not to a peer waiting
    #: beside us.
    FRESH_TOLERANCE_S = 2.0

    def __init__(self, ultra: str, slot: int, size: int = PARTY_SIZE):
        self.ultra = ultra
        self.slot = int(slot)
        self.size = int(size)
        #: Session name in the party folder -- one per ultra, so two ultras in
        #: the same run id do not read each other's markers.
        self.name = f"v2_{ultra}"
        #: When this pane started: markers and signals older than this belong
        #: to a previous run that reused the folder, not to this attempt.
        self.started_at = time.time()

    @property
    def enabled(self) -> bool:
        """False for a lone bot: no ``AQW_RUN_ID`` means no party to wait for."""
        return party.enabled()

    # --- barriers ------------------------------------------------------
    async def step(self, step: str, timeout: int = STEP_TIMEOUT_S,
                   strict: bool = False) -> bool:
        """Wait for the whole party to reach ``step``; False when stopped.

        Async on purpose: ``party.barrier`` blocks on ``time.sleep``, which
        would freeze the packet reader for the length of the wait.  The marker
        file is the same one v1 writes, so the two share a directory unchanged.

        Only markers written since this pane arrived count, and a waiting pane
        rewrites its own twice a second, so a marker left by an earlier attempt
        -- or by an earlier run in the same folder -- can no longer let the
        barrier pass on its own.  ``strict`` turns the timeout into a refusal
        instead of a "carrying on".
        """
        if self.aborted():
            return False
        if not self.enabled:
            return True

        name = f"{self.name}.{step}"
        directory = party._dir()
        marker = directory / f"{name}.{party._safe_key(self.slot)}.ready"
        since = time.time() - self.FRESH_TOLERANCE_S
        deadline = since + self.FRESH_TOLERANCE_S + timeout
        while time.time() < deadline:
            if self.aborted():
                return False
            self._publish(marker)
            if self._fresh_count(directory, name, since) >= self.size:
                return True
            await asyncio.sleep(0.5)

        if strict:
            print(f"[v2] step {step}: the party did not fill in {timeout}s; "
                  f"stopping instead of fighting a pane short.")
            return False
        # Keep going, loudly: the other pane may have died, and hanging here
        # would leave the survivor unable to finish its own quest.
        print(f"[v2] step {step}: the party did not fill in {timeout}s; "
              f"carrying on.")
        return self.aborted() is None

    @staticmethod
    def _publish(marker) -> None:
        """Leave (or refresh) this pane's marker for one step."""
        try:
            marker.write_text(str(time.time()), encoding="utf-8")
        except Exception:
            pass

    @staticmethod
    def _fresh_count(directory, name: str, since: float) -> int:
        """How many panes have arrived at ``name`` since ``since``."""
        try:
            paths = list(directory.glob(f"{name}.*.ready"))
        except Exception:
            return 0
        count = 0
        for path in paths:
            try:
                stamp = float(path.read_text(encoding="utf-8").strip())
            except Exception:
                try:
                    stamp = path.stat().st_mtime
                except Exception:
                    continue
            if stamp >= since:
                count += 1
        return count

    # --- signals -------------------------------------------------------
    def signal(self, name: str, value: Any = True) -> None:
        party.publish(f"{self.name}.{name}", self.slot, value)

    def read(self, name: str) -> Dict[int, Any]:
        return party.published(f"{self.name}.{name}", SLOTS)

    def read_fresh(self, name: str) -> Dict[int, Any]:
        """``read`` limited to signals published during this run.

        ``RIGHTEOUS_1`` from an earlier run in the same folder is a stale yes
        that sent the party in before the ArchPaladin sealed the boss.
        """
        since = self.started_at - self.FRESH_TOLERANCE_S
        found: Dict[int, Any] = {}
        directory = party._dir()
        for slot in SLOTS:
            path = directory / f"{self.name}.{name}.{party._safe_key(slot)}.sig"
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            try:
                stamp = float(data.get("t") or 0)
            except Exception:
                stamp = 0.0
            if stamp >= since:
                found[slot] = data.get("value")
        return found

    async def wait_signal(self, name: str, key: int = 0,
                          timeout: int = 120) -> bool:
        """Wait until ``key`` (or any pane when 0) publishes ``name``.

        Used by the Righteous Seal gate: the ArchPaladin seals the boss and the
        other panes must not step in before that signal exists.  Only a signal
        from this run counts, for the same reason the barriers ignore old
        markers.
        """
        if not self.enabled:
            return True
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.aborted():
                return False
            found = self.read_fresh(name)
            if key and found.get(key):
                return True
            if not key and any(found.values()):
                return True
            await asyncio.sleep(0.2)
        return False

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
