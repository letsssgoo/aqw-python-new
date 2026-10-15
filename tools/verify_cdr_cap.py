"""Verify the 0.5 cap on `$tha` against observed recast gaps.

Claim under test: honouring `$tha` up to its observed max (0.8444) would make
the local timer recast a 6000 ms skill after ~934 ms, producing same-slot gaps
far below anything we actually measured.  If the observed minimum instead
matches base*(1-0.5), the cap is correct.

    python tools/verify_cdr_cap.py
"""
import json
import pathlib
import statistics
from collections import defaultdict

FILE = pathlib.Path("capture_logs/capture_20261004_210744.jsonl")

# server cd per slot, from the sAct payload (slot0 = auto attack)
SERVER_CD = {0: 1500, 1: 6000, 2: 6000, 3: 6000, 4: 12000}
CD_START_DELAY_MS = 200


def load():
    tha, casts = [], defaultdict(list)
    for line in FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)

        # a successful cast is logged as kind=use_skill, detail=ok
        if rec.get("kind") == "use_skill" and rec.get("detail") == "ok":
            try:
                slot = int(rec["skill"])
            except (KeyError, TypeError, ValueError):
                pass
            else:
                casts[slot].append(float(rec["t"]))

        raw = rec.get("raw")
        if not isinstance(raw, str) or not raw.startswith("{"):
            continue
        try:
            msg = json.loads(raw)
        except ValueError:
            continue
        body = msg.get("b") if isinstance(msg, dict) else None
        inner = body.get("o") if isinstance(body, dict) else None
        if not isinstance(inner, dict) or inner.get("cmd") != "stu":
            continue
        v = (inner.get("sta") or {}).get("$tha")
        if isinstance(v, (int, float)):
            tha.append(float(v))
    return tha, casts


def main() -> None:
    tha, casts = load()

    print("=" * 74)
    print("$tha observed in the validated run")
    print("=" * 74)
    if tha:
        print(f"  n={len(tha)}  min={min(tha):.4f}  max={max(tha):.4f}  "
              f"median={statistics.median(tha):.4f}")
        over = [v for v in tha if v > 0.5]
        print(f"  packets above the 0.5 cap: {len(over)} "
              f"({100 * len(over) / len(tha):.1f}%)"
              + (f"  max over = {max(over):.4f}" if over else ""))
    else:
        print("  no cast records found")

    print()
    print("=" * 74)
    print("same-slot recast gaps: observed vs predicted")
    print("=" * 74)
    print(f"  {'slot':>4} {'n':>4} {'obs min':>9} {'obs p50':>9} "
          f"{'cap .5':>8} {'no cap':>8}  verdict")
    for slot in sorted(casts):
        ts = sorted(casts[slot])
        gaps = [b - a for a, b in zip(ts, ts[1:])]
        gaps = [g for g in gaps if g > 0]
        if not gaps:
            continue
        base = SERVER_CD.get(slot)
        if not base:
            print(f"  {slot:>4} {len(gaps):>4} {min(gaps) * 1000:8.0f}ms "
                  f"{statistics.median(gaps) * 1000:8.0f}ms  (no server cd)")
            continue
        # worst (fastest) $tha seen: capped vs uncapped
        worst_tha = max(tha) if tha else 0.0
        capped = base * (1 - min(worst_tha, 0.5)) + CD_START_DELAY_MS
        uncapped = base * (1 - worst_tha) + CD_START_DELAY_MS
        obs_min_ms = min(gaps) * 1000

        # does the uncapped prediction sit absurdly below what we saw?
        if obs_min_ms < uncapped * 0.5:
            verdict = "cap REQUIRED"
        elif abs(obs_min_ms - capped) < abs(obs_min_ms - uncapped):
            verdict = "matches cap"
        else:
            verdict = "matches uncapped"
        print(f"  {slot:>4} {len(gaps):>4} {obs_min_ms:8.0f}ms "
              f"{statistics.median(gaps) * 1000:8.0f}ms {capped:7.0f}ms "
              f"{uncapped:7.0f}ms  {verdict}")

    print()
    print("reading: 'cap REQUIRED' means honouring the full $tha would predict a")
    print("recast far faster than anything the run produced -> the 0.5 cap is")
    print("what the server actually allows.")


if __name__ == "__main__":
    main()
