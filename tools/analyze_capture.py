"""Analyse a capture produced by tools/capture_run.py.

Usage:
    python tools/analyze_capture.py [capture_logs/*.jsonl ...]

Prints a report focused on skill behaviour: cast rates, skip reasons, server
latency, cooldown accuracy, and dead air between packets.
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path


def load(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    records.sort(key=lambda r: r.get("t", 0))
    return records


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round(p / 100 * (len(ordered) - 1))))
    return ordered[idx]


def span(records: list[dict]) -> float:
    times = [r["t"] for r in records if "t" in r]
    return (max(times) - min(times)) if len(times) >= 2 else 0.0


def report(path: Path) -> None:
    records = load(path)
    print("=" * 78)
    print(f"FILE: {path.name}")
    print("=" * 78)
    if not records:
        print("  (empty)")
        return

    seconds = span(records)
    print(f"  records: {len(records)}   span: {seconds:.1f}s")

    # ---- lifecycle ----------------------------------------------------
    lifecycle = [r for r in records if r.get("kind") == "lifecycle"]
    attempts = [r for r in lifecycle if r.get("detail") == "attempt_start"]
    drops = [r for r in lifecycle if r.get("detail") in ("reconnecting", "attempt_error")]
    print(f"  attempts: {len(attempts)}   disconnects: {len(drops)}")
    for r in lifecycle:
        if r["detail"] in ("reconnecting", "attempt_error", "script_error", "max_attempts"):
            print(f"    ! {r['ts']} {r['detail']} {r.get('error', '')}")

    # ---- TX / RX volumes ---------------------------------------------
    tx = [r for r in records if r.get("dir") == "TX"]
    rx = [r for r in records if r.get("dir") == "RX"]
    evt = [r for r in records if r.get("dir") == "EVT"]
    print(f"  TX: {len(tx)}  RX: {len(rx)}  EVT: {len(evt)}")

    tx_by_cmd = Counter(r["detail"] for r in tx)
    rx_by_cmd = Counter(r["detail"] for r in rx)
    print("  top TX:", ", ".join(f"{k}={v}" for k, v in tx_by_cmd.most_common(8)))
    print("  top RX:", ", ".join(f"{k}={v}" for k, v in rx_by_cmd.most_common(8)))

    # ---- skill decisions ---------------------------------------------
    uses = [r for r in evt if r.get("kind") == "use_skill"]
    oks = [r for r in uses if r["detail"] == "ok"]
    skips = [r for r in uses if r["detail"] == "skipped"]
    blocks = [
        r for r in evt
        if r.get("kind") == "canUseSkill" and r["detail"] == "blocked"
    ]
    block_reasons = Counter(r.get("reason") for r in blocks)

    print("\n  --- SKILLS ---")
    print(f"  use_skill ok: {len(oks)}   skipped: {len(skips)}")
    if uses:
        efficiency = 100 * len(oks) / len(uses)
        print(f"  cast efficiency: {efficiency:.1f}%")
    print(f"  canUseSkill blocked: {len(blocks)}")
    if block_reasons:
        print(
            "  block reasons: "
            + ", ".join(f"{k}={v}" for k, v in block_reasons.most_common())
        )

    # per-slot breakdown
    per_slot = Counter(r.get("skill") for r in uses)
    per_slot_ok = Counter(r.get("skill") for r in oks)
    if per_slot:
        print("  per-slot (attempted/ok):")
        for slot in sorted(s for s in per_slot if s is not None):
            a, o = per_slot[slot], per_slot_ok.get(slot, 0)
            rate = 100 * o / a if a else 0
            print(f"    slot {slot}: {a} / {o}  ({rate:.0f}% cast)")

    # ---- cast timing --------------------------------------------------
    gar = sorted([r for r in tx if r.get("detail") == "gar"], key=lambda r: r["t"])
    if len(gar) >= 2:
        gaps = [
            b["t"] - a["t"] for a, b in zip(gar, gar[1:])
        ]
        active_gaps = [g for g in gaps if g < 10]
        print(f"\n  gar packets: {len(gar)}")
        if active_gaps:
            print(
                "  inter-cast gap ms: "
                f"min={min(active_gaps)*1000:.0f} "
                f"p50={_pct(active_gaps, 50)*1000:.0f} "
                f"p95={_pct(active_gaps, 95)*1000:.0f} "
                f"max={max(active_gaps)*1000:.0f}"
            )
            if len(active_gaps) > 1:
                print(f"  mean={statistics.mean(active_gaps)*1000:.0f}ms  "
                      f"stdev={statistics.pstdev(active_gaps)*1000:.0f}ms")
            cast_rate = len(gar) / max(seconds, 1)
            print(f"  cast rate: {cast_rate:.2f}/s")

    # ---- TX -> first response latency ---------------------------------
    latency = []
    rx_times = sorted(r["t"] for r in rx)
    for g in gar:
        later = [t for t in rx_times if t >= g["t"]]
        if later:
            latency.append(later[0] - g["t"])
    if latency:
        print(
            "  TX->next RX latency ms: "
            f"p50={_pct(latency, 50)*1000:.0f} "
            f"p95={_pct(latency, 95)*1000:.0f} "
            f"max={max(latency)*1000:.0f}"
        )

    # ---- combat ticks -------------------------------------------------
    ct = [r for r in rx if r.get("detail") == "ct"]
    if seconds > 0:
        print(f"  ct combat ticks: {len(ct)}  ({len(ct)/seconds:.2f}/s)")
    if ct and len(ct) >= 2:
        ct_gaps = [b["t"] - a["t"] for a, b in zip(ct, ct[1:])]
        ct_gaps = [g for g in ct_gaps if g < 5]
        if ct_gaps:
            print(f"  ct interval ms: p50={_pct(ct_gaps,50)*1000:.0f}  max={max(ct_gaps)*1000:.0f}")

    # ---- warnings / deaths -------------------------------------------
    warn = [
        r for r in rx
        if r.get("kind") == "xt" and "slow down" in str(r.get("raw", "")).lower()
    ]
    deaths = [r for r in rx if r.get("detail") == "playerDeath"]
    print(f"  spam warnings: {len(warn)}   deaths: {len(deaths)}")
    for r in warn[:10]:
        print(f"    ! {r['ts']} spam warning")

    # ---- dead air -----------------------------------------------------
    if len(records) >= 2:
        all_times = sorted(r["t"] for r in records)
        gaps = [
            (b - a, a) for a, b in zip(all_times, all_times[1:]) if b - a > 3
        ]
        if gaps:
            worst = sorted(gaps, reverse=True)[:5]
            print(f"  silent gaps >3s: {len(gaps)}")
            for g, at in worst:
                print(f"    {g:.1f}s of silence")

    # ---- skill loadout ------------------------------------------------
    loadouts = [r for r in evt if r.get("kind") == "skill_loadout"]
    if loadouts:
        print("\n  --- LOADOUT (first sAct) ---")
        for s in loadouts[0].get("skills", []):
            print(
                f"    slot {s['i']}: tgt={s['tgt']} cd={s['cd']}ms "
                f"mp={s['mp']} tgtMax={s['tgtMax']}"
            )


def main() -> None:
    paths = [Path(p) for p in sys.argv[1:]]
    if not paths:
        default = Path("capture_logs")
        paths = sorted(default.glob("*.jsonl"))
    if not paths:
        raise SystemExit("no capture files found")
    for p in paths:
        report(p)


if __name__ == "__main__":
    main()
