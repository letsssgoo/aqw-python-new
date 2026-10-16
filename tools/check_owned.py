"""Report which configured loadouts the account actually owns.

``check_loadouts`` proves every *name* resolves in the enhancement registry.
That is not the same as owning it.  This tool closes the gap, because the two
kinds of config value need two different checks:

``cls`` / ``scroll``   items -- matched by **name** against the captured
                       inventory and bank, which is what ``equip_item`` does
                       (it even walks to the bank when it finds one there).
``weapon`` / ``helm`` / ``cape``
                       enhancements -- never items named after themselves.
                       Valiance is the enhancement in a sword called "Blade
                       of the Bound Eclipse", so the check is the id: shop
                       ``ItemID`` against the inventory record's ``EnhID``.

A row marked NO means ``apply_loadout`` will call ``_abort`` and **stop the
bot** the moment that slot is reached -- which is the designed behaviour, and
also exactly what you want to know before launching.

Run:  python tools/check_owned.py
      python tools/check_owned.py --boss grammiel
Exit: 0 if every field is owned, 1 otherwise.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bot.ultra import config                       # noqa: E402
from model import enhancement as enh               # noqa: E402

from show_enh import owned_enh_ids                 # noqa: E402

#: Commands whose ``items`` payload lists what the account holds.
_ITEM_CMDS = ("loadInventoryBig", "retrieveInventory", "loadInventory",
              "addItems", "dropItem")


def captured_item_names() -> set[str]:
    """Every item name the captures show, lowercased, inventory *and* bank.

    Names are matched case-insensitively because ``equip_item`` normalises
    the same way -- the config writes "Lord Of Order" and the game reports
    "Lord of Order".
    """
    import json

    names: set[str] = set()
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
                if isinstance(it, dict) and isinstance(it.get("sName"), str):
                    names.add(it["sName"].lower())
    return names


def check_field(kind: str, value, have_names: set[str], have_ids: set[int]):
    """Return ``(status, detail)`` for one config field."""
    if value is None:
        return "-", "left untouched"

    if kind == "cls" or kind == "scroll":
        # Items: the name is the whole story.
        if str(value).lower() in have_names:
            return "ok", "in inventory/bank"
        return "NO", "no item by this name"

    # Enhancement: resolve first (check_loadouts covers this too, but a name
    # that resolves and a name you own are different questions).
    rows = enh.find(str(value))
    if not rows:
        return "??", "not in either capture"
    owned = [r for r in rows if r.item_id in have_ids]
    if not owned:
        return "NO", f"0 of {len(rows)} tier(s) owned"
    return "ok", f"{len(owned)}/{len(rows)} tier(s), " \
                 + ",".join(f"lvl{r.level}/r{r.rarity}" for r in owned)


def main() -> int:
    only = None
    if "--boss" in sys.argv:
        only = sys.argv[sys.argv.index("--boss") + 1]

    enh.load(force=True)
    have_ids = owned_enh_ids()
    have_names = captured_item_names()

    print("=" * 78)
    print("loadout ownership -- 'NO' = apply_loadout will stop the bot here")
    print("=" * 78)

    total = bad = 0
    rows_out = []

    for boss, slots in config.LOADOUTS.items():
        if only and only not in (boss, boss.rstrip("s")):
            continue
        for slot in sorted(slots):
            lo = slots[slot]
            for kind in ("cls", "weapon", "helm", "cape", "scroll"):
                value = getattr(lo, kind)
                status, detail = check_field(kind, value, have_names, have_ids)
                total += 1
                if status == "NO":
                    bad += 1
                rows_out.append((boss, str(slot), kind, value, status, detail))

    for cls_name, lo in config.SOLO_LOADOUTS.items():
        for kind in ("cls", "weapon", "helm", "cape", "scroll"):
            value = getattr(lo, kind)
            status, detail = check_field(kind, value, have_names, have_ids)
            total += 1
            if status == "NO":
                bad += 1
            rows_out.append((f"solo:{cls_name}", "-", kind, value,
                             status, detail))

    width = max(len(r[0]) for r in rows_out)
    for boss, slot, kind, value, status, detail in rows_out:
        flag = "  " if status == "NO" else "  "
        print(f"{flag}{boss:<{width}}  {slot:<3} {kind:<7} "
              f"{str(value):<34} {status:<4} {detail}")

    print("=" * 78)
    print(f"{total} fields checked, {bad} NOT owned")
    if bad:
        print("\nthese stop the bot -- either buy/forge them, or edit")
        print("bot/ultra/config.py to name something this account has:")
        seen = set()
        for boss, slot, kind, value, status, detail in rows_out:
            if status == "NO" and value not in seen:
                seen.add(value)
                print(f"  - {value!r}  ({kind}, first seen: {boss} slot {slot})")
    print("=" * 78)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
