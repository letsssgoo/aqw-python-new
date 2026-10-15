"""Validate bot/ultra/config.py against the enhancement registries and captures.

Walks every loadout in ``config.LOADOUTS`` (boss x launcher slot) and in
``config.SOLO_LOADOUTS`` (Ultra Speaker's per-class gear), answering three
questions per gear slot:

1. does the enhancement **name** resolve in either capture, and does it have a
   tier in the slot the config field implies?  (if not, this is a hard
   failure -- no inventory could satisfy it, exit 1)
2. does this account **own** an item carrying it, and are the class/scroll in
   inventory?  (if not, ``apply_loadout()`` stops the bot; checked against
   ``capture_logs/``, which is only ONE account, so exit 0 with a list)
3. is the name shared with other slots?  (harmless -- ``apply_loadout()``
   pins the slot from the config field)

Run:  python tools/check_loadouts.py
Exit: 0 when every enhancement name resolves, 1 when any does not.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bot.ultra import config                                  # noqa: E402
from model import enhancement as enh                          # noqa: E402

CAP = ROOT / "capture_logs"

# Slot each config field is pinned to -- read from config so there is one
# source of truth for apply_loadout() and this check alike.
FIELD_SLOT = config.GEAR_SLOTS

OBJ_SPLIT = re.compile(r"\}\s*,\s*\{")
FIELD_RX = {
    "EnhID": re.compile(r'"EnhID":\s*(\d+)'),
    "iEnh": re.compile(r'"iEnh":\s*(\d+)'),
}


def captured_inventory() -> tuple[set[str], set[int]]:
    """(lowercased item names, socketed EnhIDs) seen in capture_logs.

    Names are collected from *every* record, not just those carrying an
    EnhID -- classes and scrolls are not enhancement-bearing, so filtering on
    EnhID first would report them all as missing.
    """
    names: set[str] = set()
    enh_ids: set[int] = set()
    if not CAP.exists():
        return names, enh_ids
    for path in sorted(CAP.glob("*.jsonl")):
        raw = path.read_text(encoding="utf-8", errors="ignore")
        text = raw.replace('\\"', '"').replace("\\\\", "\\")
        for m in re.finditer(r'"sName":\s*"([^"]{1,60})"', text):
            names.add(m.group(1).lower())
        for chunk in OBJ_SPLIT.split(text):
            if '"EnhID' not in chunk and '"iEnh' not in chunk:
                continue
            rec = {}
            for key in ("EnhID", "iEnh"):
                m = FIELD_RX[key].search(chunk)
                if m:
                    rec[key] = int(m.group(1))
            eid = rec.get("EnhID", rec.get("iEnh", 0))
            if eid:
                enh_ids.add(eid)
    return names, enh_ids


def main() -> int:
    n = enh.load(force=True)
    inv_names, inv_enh_ids = captured_inventory()

    print("=" * 78)
    total = (sum(len(t) for t in config.LOADOUTS.values())
             + len(config.SOLO_LOADOUTS))
    print(f"loadouts in config: {len(config.LOADOUTS)} bosses "
          f"({total} entries, {len(config.SOLO_LOADOUTS)} speaker)   "
          f"registry: {n} entries   "
          f"captured inventory: {len(inv_names)} items")
    print("=" * 78)

    # Account-independent: the name does not resolve in either capture, so no
    # inventory could ever satisfy it.  These fail the run.
    bad: list[str] = []
    # Account-specific: the name resolves but this account's captured
    # inventory has nothing carrying it, so apply_loadout() stops.  Captures
    # are ONE account, so these are a strong hint rather than proof.
    will_stop: list[str] = []
    # Harmless, but worth knowing about.
    info: list[str] = []
    seen: set[tuple] = set()

    def check_one(label: str, lo) -> None:
        """Validate a single loadout; ``label`` is its heading and message prefix."""
        print(f"\n-- {label}: {lo.cls} --")

        # ---- class: an item name, so match against inventory --------
        if lo.cls.lower() not in inv_names:
            will_stop.append(f"{label}: class {lo.cls!r} is in "
                             f"neither captured inventory nor bank")
            print(f"   class   {lo.cls:<34} *** NOT IN INV OR BANK ***")

        # ---- gear: enhancement names --------------------------------
        for field_name in ("weapon", "helm", "cape"):
            spec = getattr(lo, field_name)
            if spec is None:
                continue
            name = spec.name if isinstance(spec, config.Enhance) else spec
            level = spec.level if isinstance(spec, config.Enhance) else None
            key = (field_name, name, level)
            rows = enh.find(name) if isinstance(name, str) else []

            if not rows:
                bad.append(f"{label} {field_name}: "
                           f"{name!r} is in neither enhancement capture")
                print(f"   {field_name:<7} {name:<34} *** UNKNOWN NAME ***")
                continue

            slots = {r.slot for r in rows}
            # The config field IS the slot: apply_loadout() passes it
            # explicitly, so "Forge" -- which exists for Weapon, ba and
            # he alike -- is never ambiguous.  Only a name with no tier in
            # the slot the field implies is a hard failure.
            want = FIELD_SLOT[field_name]
            if want not in slots:
                bad.append(f"{label} {field_name}: {name!r} has "
                           f"no {want!r} tier (registry: {sorted(slots)})")
            elif len(slots) > 1:
                info.append(f"{label} {field_name}: {name!r} also "
                            f"exists in {sorted(slots - {want})}; "
                            f"slot is pinned by config")

            owned = {i for i in inv_enh_ids
                     if (r := enh.get(i)) and r.name == name}
            if not owned:
                will_stop.append(f"{label} {field_name}: owns no "
                                 f"item carrying {name!r}")
                owned_note = "*** NOT OWNED -> stops ***"
            else:
                owned_note = f"owned x{len(owned)}"

            src = rows[0].source
            lvl = f", level {level}" if level is not None else ""
            if key not in seen:
                seen.add(key)
                print(f"   {field_name:<7} {name:<34} "
                      f"{len(rows)} tier(s), {src}, {owned_note}{lvl}")

        # ---- scroll: an item name (equip_scroll has no bank path) ----
        if lo.scroll and lo.scroll.lower() not in inv_names:
            will_stop.append(f"{label}: scroll {lo.scroll!r} "
                             f"not in captured inventory")
            print(f"   scroll  {lo.scroll:<34} *** NOT IN INVENTORY ***")

    for boss, table in config.LOADOUTS.items():
        for slot in sorted(table):
            check_one(f"{boss} / slot {slot}", table[slot])

    for class_name, lo in config.SOLO_LOADOUTS.items():
        check_one(f"speaker / {class_name}", lo)

    print()
    print("=" * 78)
    if bad:
        print(f"FAILURES ({len(bad)}) -- the name does not resolve at all:")
        for b in bad:
            print(f"  - {b}")
        print("=" * 78)
        return 1

    if will_stop:
        print(f"STOPS AT RUNTIME ({len(will_stop)}) -- apply_loadout() aborts "
              f"on these.")
        print("  Checked against capture_logs/, which is ONE account's inventory;\n"
              "  another account may own them.  Either change the config to an\n"
              "  enhancement you own, or acquire it.\n")
        for w in will_stop:
            print(f"  - {w}")
        print()
    if info:
        print(f"NOTES ({len(info)}) -- harmless:")
        for i in info:
            print(f"  - {i}")
        print()
    print("every enhancement name in config resolves. OK")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
