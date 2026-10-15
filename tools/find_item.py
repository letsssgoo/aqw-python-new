"""List captured item names matching a substring.

Quick way to confirm whether a class/scroll the config names is really in the
account's inventory, or whether the config spells it differently.

Run:  python tools/find_item.py "quantum"
      python tools/find_item.py            # dump every captured name
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAP = ROOT / "capture_logs"

NAME_RX = re.compile(r'"sName":\s*"([^"]{1,60})"')


def main() -> int:
    needle = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    names: set[str] = set()
    for path in sorted(CAP.glob("*.jsonl")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        text = text.replace('\\"', '"')
        names.update(m.group(1) for m in NAME_RX.finditer(text))

    hits = sorted(n for n in names if needle in n.lower())
    print(f"captured names: {len(names)}   matching {needle!r}: {len(hits)}")
    for n in hits:
        print(f"   {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
