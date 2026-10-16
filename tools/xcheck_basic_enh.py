"""Check whether socketed EnhIDs in captured inventory match shop ItemIDs.

Answers: can a config entry identify a basic enhancement by id instead of by
name?  Compares every EnhID seen in capture_logs inventory payloads against
the ItemIDs catalogued in basic_enhancement.jsonl and forge_enhancement.jsonl.

Run:  python tools/xcheck_basic_enh.py
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def shop_item_ids(path: Path) -> dict[int, tuple[str, str, int]]:
    """ItemID -> (name, sES, pattern) from a shop-packet jsonl."""
    out: dict[int, tuple[str, str, int]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        shop = obj.get("b", {}).get("o", {}).get("shopinfo")
        if not shop:
            continue
        for item in shop.get("items", []):
            iid = item.get("ItemID")
            if iid is None:
                continue
            out.setdefault(
                iid,
                (item.get("sName", "?"), item.get("sES", "?"), item.get("PatternID", 0)),
            )
    return out


def inventory_enh_ids() -> tuple[Counter, Counter, Counter]:
    """(EnhID, EnhPatternID, ItemID) counters scraped from capture payloads."""
    enh: Counter = Counter()
    pat: Counter = Counter()
    item: Counter = Counter()
    cap = ROOT / "capture_logs"
    if not cap.exists():
        return enh, pat, item
    for path in cap.glob("*.jsonl"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        # Payloads arrive as escaped JSON inside the captured line.
        for m in re.finditer(r'\\*"EnhID\\*":\s*(\d+)', text):
            enh[int(m.group(1))] += 1
        for m in re.finditer(r'\\*"EnhPatternID\\*":\s*(\d+)', text):
            pat[int(m.group(1))] += 1
        for m in re.finditer(r'\\*"ItemID\\*":\s*(\d+)', text):
            item[int(m.group(1))] += 1
    return enh, pat, item


def main() -> int:
    basic = shop_item_ids(ROOT / "basic_enhancement.jsonl")
    forge = shop_item_ids(ROOT / "forge_enhancement.jsonl")
    enh, pat, item = inventory_enh_ids()

    print(f"basic shop ItemIDs : {len(basic)}")
    print(f"forge  shop ItemIDs : {len(forge)}")
    print(f"capture EnhID seen  : {sum(enh.values())} ({len(enh)} distinct)")
    print(f"capture EnhPatternID: {sum(pat.values())} ({len(pat)} distinct)")
    print()

    matched_basic = {i: c for i, c in enh.items() if i in basic}
    matched_forge = {i: c for i, c in enh.items() if i in forge}
    unknown = {i: c for i, c in enh.items() if i not in basic and i not in forge}

    print("--- socketed EnhID found in basic_enhancement.jsonl (by ItemID) ---")
    if not matched_basic:
        print("   NONE")
    for iid, c in sorted(matched_basic.items()):
        name, ses, pat_id = basic[iid]
        print(f"   {iid:>6} x{c:<4} slot={ses:<8} pat={pat_id:<4} {name}")

    print()
    print("--- socketed EnhID found in forge_enhancement.jsonl ---")
    if not matched_forge:
        print("   NONE")
    for iid, c in sorted(matched_forge.items()):
        name, ses, pat_id = forge[iid]
        print(f"   {iid:>6} x{c:<4} slot={ses:<8} pat={pat_id:<4} {name}")

    print()
    print(f"--- socketed EnhID in NEITHER file: {len(unknown)} distinct ---")
    for iid, c in sorted(unknown.items())[:40]:
        print(f"   {iid:>6} x{c}")
    if len(unknown) > 40:
        print(f"   ... {len(unknown) - 40} more")

    print()
    print("--- do capture ItemIDs match basic shop ItemIDs? ---")
    item_hit = sum(c for i, c in item.items() if i in basic)
    print(f"   {item_hit} inventory ItemID occurrences are also basic shop ids")

    ok = bool(matched_basic)
    print()
    print("VERDICT:", "basic EnhID == shop ItemID (config can use ids)" if ok
          else "no overlap -- basic enhancements need another key")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
