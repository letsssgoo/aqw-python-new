"""Show how a name resolves in the enhancement registries.

Usage:
    python tools/show_enh.py Awe Blast
    python tools/show_enh.py            # every distinct name in both files

Prints, per name, the slot(s) it appears in, the source file (forge/basic),
and how many tiers -- which is how you tell a forge name (one tier) from a
basic one (a level for every step from 51 to 100).
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from model import enhancement as enh   # noqa: E402

#: Inventory commands whose ``items`` payload lists what the account holds.
_ITEM_CMDS = ("loadInventoryBig", "retrieveInventory", "loadInventory",
              "addItems", "dropItem")


def owned_enh_ids() -> set[int]:
    """Every enhancement id the captures show socketed on some item.

    Name search cannot answer this.  A forge enhancement is never an item
    *named* after itself -- ``Valiance`` is the enhancement sitting in a
    sword called "Blade of the Bound Eclipse" -- so grepping the inventory
    for "Valiance" finds nothing even when the account owns it.  The link is
    the id: the shop record's ``ItemID`` is what an inventory record carries
    as ``EnhID`` (and ``iEnh``).

    Includes items sitting in the bank (``bBank: 1``): the config is allowed
    to reach those, because ``equip_item`` moves them to the inventory.
    """
    ids: set[int] = set()
    for path in sorted((ROOT / "capture_logs").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8",
                                   errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            raw = rec.get("raw")
            if not isinstance(raw, str) or not raw.startswith("{"):
                continue
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            inner = (msg.get("b") or {}).get("o")
            if not isinstance(inner, dict) or inner.get("cmd") not in _ITEM_CMDS:
                continue
            items = inner.get("items")
            if isinstance(items, dict):
                items = list(items.values())
            if not isinstance(items, list):
                continue
            for it in items:
                if not isinstance(it, dict):
                    continue
                for key in ("EnhID", "iEnh"):
                    val = it.get(key)
                    if isinstance(val, int) and val:
                        ids.add(val)
    return ids


def main() -> int:
    enh.load(force=True)
    owned = owned_enh_ids()

    needle = " ".join(sys.argv[1:]).strip()

    if not needle:
        # Every distinct name the two captures register.
        names = enh.names()
        print(f"{len(names)} distinct enhancement names\n")
        for name in names:
            rows = enh.find(name)
            slots = sorted({r.slot for r in rows})
            print(f"  {name:<34} {len(rows):>3} tier(s) "
                  f"{rows[0].source:<6} {slots}")
        return 0

    rows = enh.find(needle)
    if not rows:
        print(f"{needle!r}: NOT FOUND in either capture")
        return 1

    print(f"{needle!r}: {len(rows)} tier(s)\n")
    print(f"  {'slot':<8} {'source':<7} {'level':<6} {'rarity':<7} "
          f"{'owned':<6} item_id")
    for r in sorted(rows, key=lambda r: (r.slot, r.level, r.rarity)):
        print(f"  {r.slot:<8} {r.source:<7} {r.level:<6} {r.rarity:<7} "
              f"{'yes' if r.item_id in owned else 'NO':<6} {r.item_id}")

    have = [r for r in rows if r.item_id in owned]
    print()
    print(f"  slots    : {dict(Counter(r.slot for r in rows))}")
    print(f"  levels   : {sorted({r.level for r in rows})}")
    print(f"  sources  : {sorted({r.source for r in rows})}")
    print(f"  owned    : {len(have)} of {len(rows)} tier(s)"
          + (f" -> {sorted((r.level, r.rarity) for r in have)}" if have else ""))
    if not have:
        print("  ** the account owns none of these tiers -- equipping this "
              "name stops the bot **")
    if len({r.slot for r in rows}) > 1:
        print("  NOTE: spans several slots -- pin the slot when equipping "
              "(config does this via GEAR_SLOTS).")
    return 0 if have else 1


if __name__ == "__main__":
    raise SystemExit(main())
