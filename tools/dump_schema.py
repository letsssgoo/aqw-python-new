"""Inventory the fields the server actually sends for items, stats and skills.

    python tools/dump_schema.py [capture.jsonl ...]

Reports, from real payloads:
  * every `sta` key in `stu` with min/max/last  -> model/stats.py
  * every item field in addItems/dropItem/      -> model/inventory.py
    retrieveInventory/searchShops
  * every field on an sAct active skill         -> the skill model

The bot currently reads exactly two of these (`$tha`, `$cmc`), so this is the
gap list for modelling.
"""
import collections
import json
import pathlib
import sys

FILES = sys.argv[1:] or [
    "capture_logs/capture_20261004_195658.jsonl",
    "capture_logs/capture_20261004_210744.jsonl",
]

ITEM_CMDS = {"addItems", "dropItem", "retrieveInventory", "searchShops",
             "loadInventory", "buyItem", "getItemDrop"}


def walk_items(payload) -> collections.Counter:
    """Count keys on every nested item dict inside an items container."""
    found: collections.Counter = collections.Counter()

    def visit(node) -> None:
        if isinstance(node, dict):
            if any(k in node for k in ("ItemID", "sName")):
                for k in node:
                    found[k] += 1
            for v in node.values():
                visit(v)
        elif isinstance(node, list):
            for v in node:
                visit(v)

    visit(payload)
    return found


def main() -> None:
    sta: dict[str, list[float]] = collections.defaultdict(list)
    item_keys: collections.Counter = collections.Counter()
    skill_keys: collections.Counter = collections.Counter()
    cmds: collections.Counter = collections.Counter()

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
            if not isinstance(body, dict):
                continue
            inner = body.get("o")
            if not isinstance(inner, dict):
                continue
            cmd = inner.get("cmd")
            if not isinstance(cmd, str):
                continue
            cmds[cmd] += 1

            if cmd == "stu":
                s = inner.get("sta")
                if isinstance(s, dict):
                    for k, v in s.items():
                        if isinstance(v, (int, float)):
                            sta[k].append(float(v))
                        else:
                            sta[k].append(float("nan"))
            elif cmd == "sAct":
                for act in (inner.get("actions", {}).get("active") or []):
                    if isinstance(act, dict):
                        for k in act:
                            skill_keys[k] += 1
            elif cmd in ITEM_CMDS:
                item_keys.update(walk_items(inner))

    print("=" * 76)
    print("1. `stu` stat keys  (bot.py:443 reads only $tha and $cmc)")
    print("=" * 76)
    if not sta:
        print("  (none found)")
    for k in sorted(sta):
        vals = [v for v in sta[k] if v == v]  # drop NaN
        if vals:
            print(f"  {k:<10} n={len(vals):<6} min={min(vals):<10.4f} "
                  f"max={max(vals):<10.4f} last={vals[-1]:.4f}")
        else:
            print(f"  {k:<10} n={len(sta[k]):<6} (non-numeric)")

    print()
    print("=" * 76)
    print("2. ITEM fields  (model/inventory.py parses ~12 of these)")
    print("=" * 76)
    if not item_keys:
        print("  (none found)")
    for k, n in item_keys.most_common():
        print(f"  {k:<20} x{n}")

    print()
    print("=" * 76)
    print("3. sAct skill fields")
    print("=" * 76)
    if not skill_keys:
        print("  (none found)")
    for k, n in skill_keys.most_common():
        print(f"  {k:<20} x{n}")

    print()
    print("=" * 76)
    print("4. commands seen")
    print("=" * 76)
    for k, n in cmds.most_common():
        print(f"  {k:<24} x{n}")


if __name__ == "__main__":
    main()
