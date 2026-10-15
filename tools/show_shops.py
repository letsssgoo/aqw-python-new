"""Dump the structure of the two enhancement captures.

    python tools/show_shops.py             # both files
    python tools/show_shops.py forge       # one of them

Prints each line's shop header followed by the names it sells, grouped so a
shop that sells one name at every level 51..100 reads as one row.  This is
how you confirm which source a name comes from -- ``Valiance`` and
``Absolution`` are forge, ``Awe Blast`` and ``Healer Helm Enhancement`` are
basic.

Field meanings, from the raw records:

``ItemID``  the enhancement's identity (shop ``EnhID`` is always ``0``)
``iLvl``    the tier, 51..100 for basic names
``iRty``    rarity, which basic tiers also track
``sES``     the slot it sockets into: ``Weapon`` / ``he`` / ``ba`` / ``ar``
``sType``   ``Enhancement`` -- these are enhancements, not gear items
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = {
    "forge": ROOT / "forge_enhancement.jsonl",
    "basic": ROOT / "basic_enhancement.jsonl",
}


def main() -> int:
    wanted = sys.argv[1:] or list(FILES)

    for key in wanted:
        path = FILES[key]
        print("=" * 78)
        print(f"{path.name}   ({path.stat().st_size} bytes)")
        print("=" * 78)

        for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            rec = json.loads(line)
            inner = (rec.get("b") or {}).get("o") or {}
            info = inner.get("shopinfo") or {}

            print(f"\nline {lineno}: cmd={inner.get('cmd')!r} "
                  f"ShopID={info.get('ShopID')!r} "
                  f"sName={info.get('sName')!r} "
                  f"Location={info.get('Location')!r}")

            items = info.get("items") or []
            print(f"  {len(items)} items")

            # Grouped: a basic shop sells one name at every level 51..100 as
            # a separate ItemID, so listing them one by one buries the shape.
            groups: dict[str, list[dict]] = {}
            for it in items:
                groups.setdefault(str(it.get("sName")), []).append(it)
            for name, group in groups.items():
                slots = sorted({str(g.get("sES")) for g in group})
                ids = [g.get("ItemID") for g in group]
                lvls = sorted({g.get("iLvl") for g in group})
                rty = sorted({g.get("iRty") for g in group})
                print(f"    {name!r:<42} x{len(group):<4} "
                      f"sES={','.join(slots):<8} "
                      f"iLvl={lvls[0]}..{lvls[-1]} rty={rty} "
                      f"ids={min(ids)}..{max(ids)}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
