"""Cross-check forge_enhancement.jsonl against the player's real inventory.

Question: which item field actually identifies an enhancement?

  * EnhPatternID (= PatternID in loadShop) -- is it unique per enhancement?
  * EnhID / iEnh  (= ItemID in loadShop)  -- unique per name+rarity?

Prints both answers, plus which shop entries the account already owns.

    python tools/xcheck_enh.py
"""
import json
import pathlib
from collections import Counter, defaultdict

FORGE = pathlib.Path("forge_enhancement.jsonl")
CAPTURES = sorted(pathlib.Path("capture_logs").glob("capture_*.jsonl"))
INVENTORY_CMDS = {"loadInventoryBig", "retrieveInventory", "loadInventory",
                  "addItems", "dropItem", "searchShops", "buyItem"}

SLOT_NAMES = {"Weapon": "Weapon", "he": "Helm", "ba": "Cape",
              "ar": "Class", "co": "Armor"}


def load_forge():
    """-> (by_item_id, by_pattern) from the three forge shops."""
    by_item, by_pattern = {}, defaultdict(list)
    for line in FORGE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        si = json.loads(line)["b"]["o"]["shopinfo"]
        for it in si.get("items") or []:
            rec = {
                "item_id": it["ItemID"],
                "name": it["sName"],
                "pattern": it.get("PatternID"),
                "slot": it.get("sES"),
                "rty": it.get("iRty"),
                "lvl": it.get("iLvl"),
                "cost": it.get("iCost"),
                "shop": si["ShopID"],
                "shop_name": si["sName"],
            }
            by_item[rec["item_id"]] = rec
            by_pattern[rec["pattern"]].append(rec)
    return by_item, by_pattern


def load_inventory_items():
    """Every inventory-shaped item seen in the captures."""
    seen = {}
    for path in CAPTURES:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            raw = rec.get("raw")
            if not isinstance(raw, str) or not raw.startswith("{"):
                continue
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            body = msg.get("b") if isinstance(msg, dict) else None
            inner = body.get("o") if isinstance(body, dict) else None
            if not isinstance(inner, dict) or inner.get("cmd") not in INVENTORY_CMDS:
                continue
            items = inner.get("items")
            if isinstance(items, dict):
                items = list(items.values())
            if not isinstance(items, list):
                continue
            for it in items:
                if isinstance(it, dict) and "sName" in it:
                    seen[(it.get("ItemID"), it.get("sName"))] = it
    return list(seen.values())


def main() -> None:
    by_item, by_pattern = load_forge()

    print("=" * 78)
    print("Q1  Is EnhPatternID / PatternID unique per enhancement name?")
    print("=" * 78)
    names_per_pattern = {pid: sorted({r["name"] for r in rows})
                         for pid, rows in by_pattern.items()}
    ok = True
    for pid, names in sorted(names_per_pattern.items(), key=lambda kv: kv[0]):
        flag = "" if len(names) == 1 else "   <-- NOT UNIQUE"
        if len(names) != 1:
            ok = False
        print(f"  pattern {pid:>3}: {', '.join(names)}{flag}")
    print()
    print("  verdict:", "pattern id IS unique per name"
          if ok else
          "pattern id is NOT a safe identity -- several names share one "
          "pattern (weapon pattern 10 in particular)")

    print()
    print("=" * 78)
    print("Q2  Is EnhID / iEnh (= shop ItemID) unique per enhancement+rarity?")
    print("=" * 78)
    dupe = Counter(r["item_id"] for r in by_item.values())
    print(f"  {len(by_item)} distinct shop item ids, all unique: "
          f"{all(v == 1 for v in dupe.values())}")

    print()
    print("=" * 78)
    print("Q3  Which shop enhancements does the account already own?")
    print("=" * 78)
    items = load_inventory_items()
    print(f"  {len(items)} distinct inventory items scanned")

    owned_by_id, owned_by_pattern = [], Counter()
    unknown_ids = Counter()
    for it in items:
        enh = it.get("EnhID") or it.get("iEnh") or 0
        pat = it.get("EnhPatternID", 0)
        if not enh and not pat:
            continue
        owned_by_pattern[pat] += 1
        if enh in by_item:
            r = by_item[enh]
            owned_by_id.append((it.get("sName"), it.get("sES"),
                                SLOT_NAMES.get(r["slot"], r["slot"]),
                                r["name"], r["rty"], r["lvl"], enh, pat))
        elif enh:
            unknown_ids[enh] += 1

    print()
    print(f"  {'item':<26} {'slot':<8} {'fits':<7} {'enhancement':<20} "
          f"{'rty':>3} {'lvl':>4} {'EnhID':>7} {'pat':>4}")
    print("  " + "-" * 88)
    for row in sorted(owned_by_id, key=lambda r: (r[3], r[5])):
        print(f"  {str(row[0])[:25]:<26} {str(row[1]):<8} {row[2]:<7} "
              f"{row[3]:<20} {row[4]:>3} {row[5]:>4} {row[6]:>7} {row[7]:>4}")

    print()
    print(f"  owned EnhIDs found in forge shops : {len(owned_by_id)}")
    print(f"  EnhIDs not in the forge shops     : {len(unknown_ids)} distinct "
          f"(older / non-forge enhancements, e.g. "
          f"{', '.join(str(k) for k in list(unknown_ids)[:8])})")

    print()
    print("=" * 78)
    print("Q4  Does EnhPatternID alone pick the right item in this inventory?")
    print("=" * 78)
    for pid in (10, 29, 23, 25):
        matches = [it for it in items if it.get("EnhPatternID") == pid]
        if not matches:
            print(f"  pattern {pid:>3}: 0 items")
            continue
        # what equip_item_by_enhancement would do: first match wins
        first = matches[0]
        enh = first.get("EnhID") or first.get("iEnh") or 0
        r = by_item.get(enh)
        label = r["name"] if r else f"unknown enh {enh}"
        print(f"  pattern {pid:>3}: {len(matches)} item(s); first-match would "
              f"equip {first.get('sName')!r} with {label}")

    print()
    print("=" * 78)
    print("Q5  Enhancement names, grouped by the slot they fit")
    print("=" * 78)
    by_slot = defaultdict(dict)
    for r in by_item.values():
        by_slot[SLOT_NAMES.get(r["slot"], r["slot"])][r["name"]] = r
    for slot in ("Weapon", "Helm", "Cape"):
        print(f"  {slot}:")
        for name, r in sorted(by_slot.get(slot, {}).items()):
            print(f"      {name:<20} pattern {r['pattern']:>3}  "
                  f"item ids {r['item_id']}  (rty {r['rty']} lvl {r['lvl']})")


if __name__ == "__main__":
    main()
