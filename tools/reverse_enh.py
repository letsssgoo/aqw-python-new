"""Reverse lookup: which inventory items carry a given enhancement?

The forward map (item -> EnhID) lives in tools/resolve_ultra_items.py.  This
answers the question a config actually needs: "I want Valiance -- what do I
own that has it socketed?"  Also prints, for each of the four loadout roles,
the items the current core_ultra constants resolve to.

Run:  python tools/reverse_enh.py [enh_id ...]
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAP = ROOT / "capture_logs"

OBJ_SPLIT = re.compile(r"\}\s*,\s*\{")
FIELDS = {
    "sName": re.compile(r'"sName":\s*"([^"]*)"'),
    "ItemID": re.compile(r'"ItemID":\s*(\d+)'),
    "sES": re.compile(r'"sES":\s*"([^"]*)"'),
    "EnhID": re.compile(r'"EnhID":\s*(\d+)'),
    "iEnh": re.compile(r'"iEnh":\s*(\d+)'),
    "EnhPatternID": re.compile(r'"EnhPatternID":\s*(\d+)'),
    "sType": re.compile(r'"sType":\s*"([^"]*)"'),
    "bEquip": re.compile(r'"bEquip":\s*(true|false)'),
}
TEXT_KEYS = {"sName", "sES", "sType", "bEquip"}

# Enhancements the loadouts care about, keyed by the constant's intent.
WANTED = {
    70752: "Valiance (forge weapon)",
    70991: "Arcana's Concerto (forge weapon)",
    83500: "Ravenous (forge weapon)",
    70750: "Lacerate (forge weapon)",
    52369: "Awe Blast (basic weapon)",
    71537: "Forge (forge helm)",
    66436: "Wizard Helm Enhancement (basic helm)",
    66448: "Lucky Helm Enhancement (basic helm)",
    70968: "Vainglory (forge cape)",
    71543: "Lament (forge cape)",
    71542: "Penitence (forge cape)",
    70970: "Avarice (forge cape)",
    66435: "Wizard Armor (basic class)",
    66447: "Lucky Armor (basic class)",
}


def scan() -> dict[int, list[dict]]:
    by_enh: dict[int, list[dict]] = defaultdict(list)
    if not CAP.exists():
        return by_enh
    for path in sorted(CAP.glob("*.jsonl")):
        raw = path.read_text(encoding="utf-8", errors="ignore")
        text = raw.replace('\\"', '"').replace("\\\\", "\\")
        for chunk in OBJ_SPLIT.split(text):
            if '"sName' not in chunk or '"EnhID' not in chunk:
                continue
            rec: dict = {}
            for key, rx in FIELDS.items():
                m = rx.search(chunk)
                if m:
                    rec[key] = m.group(1) if key in TEXT_KEYS else int(m.group(1))
            if "EnhID" not in rec and "iEnh" not in rec:
                continue
            rec["EnhID"] = rec.get("EnhID", rec.get("iEnh", 0))
            if not rec.get("sName"):
                continue
            by_enh[rec["EnhID"]].append(rec)
    return by_enh


def main() -> int:
    by_enh = scan()
    args = [int(a) for a in sys.argv[1:]] or sorted(WANTED)

    print(f"distinct socketed EnhIDs in captures: {len(by_enh)}")
    print()
    for eid in args:
        label = WANTED.get(eid, "")
        rows = by_enh.get(eid, [])
        print(f"=== EnhID {eid}  {label} ===")
        if not rows:
            print("   (no item in captures carries this)")
            print()
            continue
        seen = set()
        for r in rows:
            key = (r.get("sName"), r.get("sES"), r.get("bEquip"))
            if key in seen:
                continue
            seen.add(key)
            eq = "  [EQUIPPED]" if r.get("bEquip") == "true" else ""
            print(f"   item {r.get('ItemID', 0):>6}  slot={r.get('sES', '?'):<8} "
                  f"{r.get('sType', '?'):<10} {r.get('sName')}{eq}")
        print()

    # What each core_ultra constant actually resolves to today.
    print("=== core_ultra constants: intended vs. actually socketed ===")
    fwd = {}
    for eid, rows in by_enh.items():
        for r in rows:
            if r.get("sName"):
                fwd.setdefault(r["sName"].lower(), []).append(eid)
    constants = {
        "greatblade of the entwined eclipse": "ARCANA",
        "exalted apotheosis": "VALIANCE",
        "higure": "LUCKAWEBLAST / LUCKMANAVAMP",
        "blade of the bound eclipse": "RAVENOUS",
        "battle oracle hood": "FORGEHELM",
        "awescended omni cowl": "LUCKHELM",
        "shadowlord's helm": "HEALERHELM",
        "ascendant enlightened vision": "WIZARDHELM",
        "arch doomknight cape": "VAINGLORY",
        "category five hurricane cloud": "LAMENT",
        "arch doomknight cape sword": "PENITENCE",
    }
    for item_name, const in constants.items():
        ids = sorted(set(fwd.get(item_name, [])))
        names = ", ".join(
            f"{i}={WANTED.get(i, '?')}" for i in ids) or "(none in captures)"
        print(f"   {const:<26} {item_name:<36} -> {names}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
