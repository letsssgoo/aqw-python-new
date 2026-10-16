"""Map the item names used by bot/ultra loadouts to their socketed enhancement.

Reads captured inventory payloads and reports, for each requested item name,
the EnhID / EnhPatternID / slot it carries.  That is the ground truth for
writing a Loadout as enhancements instead of item names.

Run:  python tools/resolve_ultra_items.py [item name ...]
      (with no args, resolves the default core_ultra constants)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAP = ROOT / "capture_logs"

DEFAULT_ITEMS = [
    # classes
    "ArchPaladin", "Legion Revenant", "Quantum Chronomancer", "Lord Of Order",
    "Legendary Hero", "StoneCrusher",
    "Obsidian Paladin Chronomancer", "LightCaster",
    # weapons
    "Greatblade of the Entwined Eclipse", "Exalted Apotheosis", "Higure",
    "Blade of the Bound Eclipse",
    # helms
    "Battle Oracle Hood", "Awescended Omni Cowl", "ShadowLord's Helm",
    "Ascendant Enlightened Vision",
    # capes
    "Arch DoomKnight Cape", "Category Five Hurricane Cloud",
    "Arch DoomKnight Cape Sword",
    # scrolls
    "Scroll of Enrage", "Scroll of Life Steal",
]

# Inventory objects arrive as a JSON string nested inside the capture line,
# so every quote is backslash-escaped (`\"ItemID\":1965`).  Unescaping once
# first makes the fields ordinary JSON and keeps the patterns below readable.
OBJ_SPLIT = re.compile(r'\}\s*,\s*\{')
FIELDS = {
    "sName": re.compile(r'"sName":\s*"([^"]*)"'),
    "ItemID": re.compile(r'"ItemID":\s*(\d+)'),
    "sES": re.compile(r'"sES":\s*"([^"]*)"'),
    "EnhID": re.compile(r'"EnhID":\s*(\d+)'),
    "iEnh": re.compile(r'"iEnh":\s*(\d+)'),
    "EnhPatternID": re.compile(r'"EnhPatternID":\s*(\d+)'),
    "EnhLvl": re.compile(r'"EnhLvl":\s*(\d+)'),
    "EnhRty": re.compile(r'"EnhRty":\s*(\d+)'),
    "sType": re.compile(r'"sType":\s*"([^"]*)"'),
}
TEXT_KEYS = {"sName", "sES", "sType"}


def scan() -> dict[str, dict]:
    """item name (lowercased) -> fields of the record seen for it."""
    found: dict[str, dict] = {}
    if not CAP.exists():
        return found
    for path in sorted(CAP.glob("*.jsonl")):
        raw = path.read_text(encoding="utf-8", errors="ignore")
        # One unescape pass: `\"` -> `"` turns the nested payload into plain
        # JSON text.  The inner-most level was already double-escaped, hence
        # the second replace for `\\"`.
        text = raw.replace('\\"', '"').replace('\\\\', '\\')
        for chunk in OBJ_SPLIT.split(text):
            if '"sName' not in chunk or '"EnhID' not in chunk:
                continue
            name_m = FIELDS["sName"].search(chunk)
            if not name_m:
                continue
            rec = {}
            for key, rx in FIELDS.items():
                m = rx.search(chunk)
                if m:
                    rec[key] = m.group(1) if key in TEXT_KEYS else int(m.group(1))
            if "EnhID" not in rec and "iEnh" not in rec:
                continue
            rec.setdefault("EnhID", rec.get("iEnh", 0))
            found[name_m.group(1).lower()] = rec
    return found


def main() -> int:
    wanted = [a.lower() for a in sys.argv[1:]] or [i.lower() for i in DEFAULT_ITEMS]
    found = scan()
    print(f"records with an EnhID in captures: {len(found)}")
    print()
    hdr = f"{'item':<42} {'ItemID':>7} {'EnhID':>7} {'pat':>4} {'lvl':>4} {'rty':>4} {'sES':<8} type"
    print(hdr)
    print("-" * len(hdr))
    missing = []
    for name in wanted:
        rec = found.get(name)
        if not rec:
            missing.append(name)
            print(f"{name:<42} {'-- not in captures --':>7}")
            continue
        print(f"{name:<42} {rec.get('ItemID', 0):>7} {rec.get('EnhID', 0):>7} "
              f"{rec.get('EnhPatternID', 0):>4} {rec.get('EnhLvl', 0):>4} "
              f"{rec.get('EnhRty', 0):>4} {rec.get('sES', '?'):<8} "
              f"{rec.get('sType', '?')}")
    if missing:
        print()
        print(f"not found in captures ({len(missing)}):")
        for m in missing:
            print(f"  {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
