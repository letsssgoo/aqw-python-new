"""A/B two `bot/ultra` telemetry runs (see tools/analyze_ultra.py).

    python tools/compare_ultra.py <run_a> <run_b>

Prints, per boss and slot, the delta in damage share, damage taken and deaths
between run A and run B, so a change to config.LOADOUTS can be judged on more
than a feeling.
"""

from __future__ import annotations

import glob
import sys
from pathlib import Path

from analyze_ultra import REPO_ROOT, load_records, slot_data  # noqa: E402

RUNS_DIR = REPO_ROOT / "capture_logs" / "ultra"


def summarize(run_id: str) -> dict:
    out = {}
    for path in sorted(glob.glob(str(RUNS_DIR / run_id / "slot*.jsonl"))):
        records = load_records(Path(path))
        if not records:
            continue
        out[records[0].get("slot")] = slot_data(records)
    return out


def totals(boss: str, run: dict) -> dict:
    dmg = taken = deaths = 0
    for info in run.values():
        data = info["bosses"].get(boss)
        if not data:
            continue
        dmg += data["dmg"]
        taken += data["taken"]
        deaths += data["deaths"]
    return {"dmg": dmg, "taken": taken, "deaths": deaths}


def main() -> int:
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    run_a, run_b = sys.argv[1], sys.argv[2]
    a, b = summarize(run_a), summarize(run_b)
    bosses = sorted({boss for run in (a, b) for info in run.values() for boss in info["bosses"]})
    print(f"A={run_a}  B={run_b}")
    for boss in bosses:
        ta, tb = totals(boss, a), totals(boss, b)
        print(f"\n== {boss}")
        print(f"  team dmg   {ta['dmg']:>12,} -> {tb['dmg']:>12,}  ({tb['dmg'] - ta['dmg']:+,})")
        print(f"  taken      {ta['taken']:>12,} -> {tb['taken']:>12,}  ({tb['taken'] - ta['taken']:+,})")
        print(f"  deaths     {ta['deaths']:>12} -> {tb['deaths']:>12}")
        for slot in sorted(set(a) | set(b)):
            da = a.get(slot, {}).get("bosses", {}).get(boss)
            db = b.get(slot, {}).get("bosses", {}).get(boss)
            if not da and not db:
                continue
            da = da or {"dmg": 0, "taken": 0, "deaths": 0}
            db = db or {"dmg": 0, "taken": 0, "deaths": 0}
            print(f"  slot{slot}: dmg {da['dmg']:>12,} -> {db['dmg']:>12,} ({db['dmg'] - da['dmg']:+,})"
                  f"  taken {da['taken']:>10,} -> {db['taken']:>10,}"
                  f"  deaths {da['deaths']} -> {db['deaths']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
