"""Which item field identifies *the enhancement* on an item?

Reads every inventory-shaped payload in the captures and reports the value
distribution for EnhPatternID / EnhID / iEnh / EnhLvl / EnhRty, plus the
tempSta stat block.  Result decides how equip-by-enhancement must be keyed.

    python tools/survey_enh.py [capture.jsonl ...]
"""
import collections
import json
import pathlib
import sys

FILES = sys.argv[1:] or [
    "capture_logs/capture_20261004_195658.jsonl",
    "capture_logs/capture_20261004_210744.jsonl",
]

FIELDS = ("EnhPatternID", "EnhID", "iEnh", "EnhLvl", "EnhRty",
          "EnhDPS", "EnhRng", "sES", "sType")


def main() -> None:
    dist: dict[str, collections.Counter] = {f: collections.Counter() for f in FIELDS}
    by_slot: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    pairs: collections.Counter = collections.Counter()
    temp_sta: dict[str, set] = collections.defaultdict(set)
    w_dps: collections.Counter = collections.Counter()
    n_items = 0
    n_with_enh = 0

    for path in FILES:
        p = pathlib.Path(path)
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("dir") != "RX":
                continue
            raw = rec.get("raw")
            if not isinstance(raw, str) or not raw.startswith("{"):
                continue
            try:
                msg = json.loads(raw)
            except (ValueError, TypeError):
                continue
            body = msg.get("b") if isinstance(msg, dict) else None
            inner = body.get("o") if isinstance(body, dict) else None
            if not isinstance(inner, dict):
                continue
            cmd = inner.get("cmd")

            if cmd == "stu":
                if isinstance(inner.get("tempSta"), dict):
                    for slot, stats in inner["tempSta"].items():
                        if isinstance(stats, dict):
                            temp_sta[slot].update(stats)
                if "wDPS" in inner:
                    w_dps[inner["wDPS"]] += 1

            if cmd not in ("loadInventoryBig", "retrieveInventory", "loadInventory",
                           "searchShops", "buyItem"):
                continue
            items = inner.get("items")
            if isinstance(items, dict):
                items = list(items.values())
            if not isinstance(items, list):
                continue
            for it in items:
                if not isinstance(it, dict) or "sName" not in it:
                    continue
                n_items += 1
                for f in FIELDS:
                    if f in it:
                        dist[f][str(it[f])] += 1
                if "EnhID" in it or "iEnh" in it or "EnhPatternID" in it:
                    n_with_enh += 1
                slot = str(it.get("sES", "?"))
                by_slot[slot][str(it.get("EnhPatternID", "-"))] += 1
                if "EnhID" in it or "iEnh" in it:
                    pairs[(str(it.get("sES", "?")),
                           str(it.get("EnhPatternID", "-")),
                           str(it.get("EnhID", it.get("iEnh", "-"))))] += 1

    print(f"items scanned: {n_items}   carrying enhancement fields: {n_with_enh}")
    print()
    print("value distribution per field")
    print("-" * 70)
    for f in FIELDS:
        c = dist[f]
        if not c:
            print(f"  {f:<15} (absent)")
            continue
        top = ", ".join(f"{k}x{v}" for k, v in c.most_common(8))
        print(f"  {f:<15} {len(c)} distinct: {top}")

    print()
    print("EnhPatternID by equipment slot  (sES)")
    print("-" * 70)
    for slot, c in sorted(by_slot.items()):
        print(f"  {slot:<10} {dict(c.most_common(6))}")

    print()
    print("(sES, EnhPatternID, EnhID) triples, most common")
    print("-" * 70)
    for k, v in pairs.most_common(12):
        print(f"  {k}  x{v}")

    print()
    print("tempSta per-slot stat contribution  <- what the enhancement adds")
    print("-" * 70)
    for slot, stats in sorted(temp_sta.items()):
        print(f"  {slot}: {sorted(stats)}")

    print()
    print(f"wDPS values: {dict(w_dps.most_common(8))}")


if __name__ == "__main__":
    main()
