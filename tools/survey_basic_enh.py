"""Summarise basic_enhancement.jsonl without dumping the raw payloads.

Three captured basic-enhancement shop packets.  Prints one row per
(shop, slot) group so the ItemID / EnhID / pattern a config entry needs is
visible at a glance.

Run:  python tools/survey_basic_enh.py [path]
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("basic_enhancement.jsonl")

# (shop, pattern, sES) -> info
groups: dict[tuple, dict] = defaultdict(
    lambda: {"ids": set(), "enh_ids": set(), "names": set(), "rty": set(), "lvl": set()}
)
n_shops = 0

for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
    line = line.strip()
    if not line:
        continue
    try:
        obj = json.loads(line)
    except ValueError as exc:
        print(f"line {line_no}: not valid JSON ({exc})")
        continue
    shop = obj.get("b", {}).get("o", {}).get("shopinfo")
    if not shop:
        print(f"line {line_no}: no shopinfo")
        continue
    n_shops += 1
    shop_name = shop.get("sName", "?")
    for item in shop.get("items", []):
        key = (shop_name, item.get("PatternID"), item.get("sES"))
        g = groups[key]
        g["ids"].add(item.get("ItemID"))
        g["enh_ids"].add(item.get("EnhID"))
        g["names"].add(item.get("sName"))
        g["rty"].add(item.get("iRty"))
        g["lvl"].add(item.get("iLvl"))

print(f"file : {path}")
print(f"shops: {n_shops}   groups: {len(groups)}")
print()
hdr = f"{'shop':<18} {'pat':>5} {'sES':<8} {'#id':>4}  {'ItemID range':<15} {'EnhID range':<15} {'rty':<6} {'lvl':<6} names"
print(hdr)
print("-" * len(hdr))
for key in sorted(groups, key=lambda k: (str(k[0]), str(k[1]), str(k[2]))):
    g = groups[key]
    ids = sorted(i for i in g["ids"] if i is not None)
    ehs = sorted(i for i in g["enh_ids"] if i is not None)
    idr = f"{ids[0]}-{ids[-1]}" if ids else "-"
    ehr = f"{ehs[0]}-{ehs[-1]}" if ehs else "-"
    rty = ",".join(str(x) for x in sorted(g["rty"], key=lambda v: (v is None, v)))
    lvl = ",".join(str(x) for x in sorted(g["lvl"], key=lambda v: (v is None, v)))
    print(
        f"{str(key[0]):<18} {str(key[1]):>5} {str(key[2]):<8} {len(ids):>4}  "
        f"{idr:<15} {ehr:<15} {rty:<6} {lvl:<6} "
        f"{', '.join(sorted(n for n in g['names'] if n))}"
    )

# Exact ItemID -> (name, slot, enh) so a config can be filled by id.
print()
print("=== ItemID -> name / sES (exact lookup) ===")
by_id: dict[int, tuple] = {}
for key, g in groups.items():
    pass  # names are per-item, rebuilt below

exact: dict[int, list] = defaultdict(list)
for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
    line = line.strip()
    if not line:
        continue
    shop = json.loads(line).get("b", {}).get("o", {}).get("shopinfo", {})
    for item in shop.get("items", []):
        exact[item.get("ItemID")].append(
            (item.get("sName"), item.get("sES"), item.get("PatternID"),
             item.get("EnhID"), shop.get("sName"))
        )
for iid in sorted(k for k in exact if k is not None):
    for name, ses, pat, enh, shop in exact[iid]:
        print(f"  {iid:>6}  slot={str(ses):<8} pat={str(pat):<4} enh={str(enh):<6} {shop:<18} {name}")
