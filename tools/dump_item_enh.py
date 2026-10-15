"""Extract (ItemID, name, EnhID, EnhPatternID, sES) from captured inventory.

Feeds the ultra config: shows which gear items carry which enhancement, so a
loadout can be written as EnhIDs instead of item names.

Run:  python tools/dump_item_enh.py
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAP = ROOT / "capture_logs"

# Item records arrive flattened inside a larger payload; grab the fields we
# need with one tolerant scan per object rather than parsing the whole line.
OBJ = re.compile(
    r'\{[^{}]*?"ItemID\\*":\s*(\d+)[^{}]*?"sName\\*":\s*"([^"]*)"'
    r'[^{}]*?\}',
    re.S,
)
FLD = {
    "EnhID": re.compile(r'"EnhID\\*":\s*(\d+)'),
    "EnhPatternID": re.compile(r'"EnhPatternID\\*":\s*(\d+)'),
    "sES": re.compile(r'"sES\\*":\s*"([^"]*)"'),
    "sType": re.compile(r'"sType\\*":\s*"([^"]*)"'),
    "iEnh": re.compile(r'"iEnh\\*":\s*(\d+)'),
}


def main() -> int:
    if not CAP.exists():
        print("no capture_logs/")
        return 1

    rows: dict[tuple, dict] = defaultdict(dict)
    for path in sorted(CAP.glob("*.jsonl")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for m in OBJ.finditer(text):
            iid, name = int(m.group(1)), m.group(2)
            # Fields can precede ItemID, so scan the whole record window.
            lo = max(0, m.start() - 700)
            hi = min(len(text), m.end() + 700)
            win = text[lo:hi]
            key = (iid, name)
            slot = FLD["sES"].search(win)
            enh = FLD["EnhID"].search(win)
            ienh = FLD["iEnh"].search(win)
            pat = FLD["EnhPatternID"].search(win)
            stype = FLD["sType"].search(win)
            if slot:
                rows[key]["sES"] = slot.group(1)
            if enh or ienh:
                rows[key]["EnhID"] = int((enh or ienh).group(1))
            if pat:
                rows[key]["EnhPatternID"] = int(pat.group(1))
            if stype:
                rows[key]["sType"] = stype.group(1)

    known = {k: v for k, v in rows.items() if "EnhID" in v and v["EnhID"]}
    print(f"items seen: {len(rows)}   with a socketed EnhID: {len(known)}")
    print()
    print(f"{'ItemID':>8} {'EnhID':>7} {'pat':>5} {'sES':<8} {'sType':<14} name")
    print("-" * 96)
    for (iid, name), v in sorted(known.items(), key=lambda kv: (kv[0][1].lower())):
        print(
            f"{iid:>8} {v.get('EnhID', 0):>7} {v.get('EnhPatternID', 0):>5} "
            f"{v.get('sES', '?'):<8} {v.get('sType', '?'):<14} {name}"
        )

    # Anything the ultra loadouts reference but we could not resolve.
    print()
    print("--- items seen WITHOUT a usable EnhID ---")
    none = [k for k, v in rows.items() if not v.get("EnhID")]
    for iid, name in sorted(none, key=lambda k: k[1].lower())[:60]:
        print(f"  {iid:>8} {name}")
    if len(none) > 60:
        print(f"  ... {len(none) - 60} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
