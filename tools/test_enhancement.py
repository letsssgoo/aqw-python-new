"""End-to-end test of the enhancement model against real captured data.

Builds an inventory from capture_logs/, loads forge_enhancement.jsonl, and
checks the question that matters: does "equip Valiance" pick the Valiance item,
or does it pick an arbitrary pattern-10 item?

    python tools/test_enhancement.py
"""
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from model import enhancement as enh                    # noqa: E402
from model.inventory import ItemInventory               # noqa: E402
from model.shop import Shop                             # noqa: E402
from core.player import Player                          # noqa: E402

PASSED = []
FAILED = []


def check(label, condition, detail=""):
    (PASSED if condition else FAILED).append(label)
    mark = "ok  " if condition else "FAIL"
    print(f"  {mark} {label}" + (f"   [{detail}]" if detail else ""))


def load_inventory():
    seen = {}
    for path in sorted((REPO / "capture_logs").glob("capture_*.jsonl")):
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
            inner = (msg.get("b") or {}).get("o")
            if not isinstance(inner, dict):
                continue
            if inner.get("cmd") not in ("loadInventoryBig", "retrieveInventory",
                                        "loadInventory", "addItems", "dropItem"):
                continue
            items = inner.get("items")
            if isinstance(items, dict):
                items = list(items.values())
            if not isinstance(items, list):
                continue
            for it in items:
                if isinstance(it, dict) and "sName" in it:
                    seen[(it.get("ItemID"), it.get("sName"))] = it
    return [ItemInventory(i) for i in seen.values()]


def find_item(items, name_fragment):
    for it in items:
        if name_fragment.lower() in it.s_name.lower():
            return it
    return None


def count_shop_items(path):
    """How many distinct ItemIDs a shop capture declares.

    Counted from the file rather than hardcoded, so adding a shop to
    ``basic_enhancement.jsonl`` moves the expected total with it instead of
    failing three assertions.  This is the number ``load()`` should register
    for that source -- shop ``ItemID`` *is* the inventory ``EnhID``.
    """
    seen = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        info = ((rec.get("b") or {}).get("o") or {}).get("shopinfo")
        if not isinstance(info, dict):
            continue
        for it in info.get("items") or []:
            if isinstance(it, dict) and it.get("ItemID") is not None:
                seen.add(it["ItemID"])
    return len(seen)


def main() -> None:
    n = enh.load(force=True)
    # The registry now holds BOTH captures (forge + basic).  The forge-only
    # assertions below keep their original exact counts by filtering on
    # `source`, so a change in either file shows up as a real failure.
    forge = [r for r in enh.all_enhancements() if r.source == "forge"]
    basic = [r for r in enh.all_enhancements() if r.source == "basic"]
    f_ids = {r.item_id for r in forge}
    f_names = lambda slot=None: sorted(
        {r.name for r in forge if slot is None or r.slot == slot})
    f_by_slot = lambda slot: [r for r in forge if r.slot == slot]

    print("=" * 74)
    print(f"registry loaded: {n} entries "
          f"({len(forge)} forge, {len(basic)} basic)")
    print("=" * 74)
    forge_expected = count_shop_items(REPO / "forge_enhancement.jsonl")
    basic_expected = count_shop_items(REPO / "basic_enhancement.jsonl")
    check(f"registry loaded {forge_expected + basic_expected} entries "
          f"({forge_expected} forge + {basic_expected} basic)",
          n == forge_expected + basic_expected, f"got {n}")
    check(f"forge file contributed {forge_expected}",
          len(forge) == forge_expected, f"got {len(forge)}")
    check(f"basic file contributed {basic_expected}",
          len(basic) == basic_expected, f"got {len(basic)}")

    print("\n-- lookup --")
    check("find('Valiance') returns one", len(enh.find("Valiance")) == 1)
    v = enh.best("Valiance")
    check("Valiance is a weapon enhancement",
          v is not None and v.slot == "Weapon", v.describe() if v else "-")
    check("find is case-insensitive", len(enh.find("valiance")) == 1)
    check("find('Nope') is empty", enh.find("Nope") == [])
    # names() is distinct enhancements; by_slot() is rarity tiers (a cape shop
    # sells 8 Forge tiers + 2 each of 5 others = 18 entries, 6 names).
    check("forge names() has 20 distinct (Forge spans 3 slots)",
          len(f_names()) == 20, f"got {len(f_names())}")
    check("forge by_slot('ba') has 18 cape tiers",
          len(f_by_slot("ba")) == 18, f"got {len(f_by_slot('ba'))}")
    check("forge names('ba') has 6 distinct cape enhancements",
          len(f_names("ba")) == 6, str(f_names("ba")))
    check("forge by_slot('Weapon') has 33 tiers",
          len(f_by_slot("Weapon")) == 33,
          f"got {len(f_by_slot('Weapon'))}")
    check("by_slot('cape') readable alias works",
          len(enh.by_slot("cape")) == len(enh.by_slot("ba")))
    check("slots_of('Forge') spans 3 slots",
          enh.slots_of("Forge") == ["Cape", "Helm", "Weapon"],
          str(enh.slots_of("Forge")))

    print("\n-- EnhID is the identity, EnhPatternID is not --")
    check("EnhID 70752 -> Valiance",
          enh.get(70752) is not None and enh.get(70752).name == "Valiance")
    check("EnhID 71542 -> Penitence",
          enh.get(71542) is not None and enh.get(71542).name == "Penitence")
    check("pattern 10 is NOT unique", not enh.is_pattern_unique(10))
    check("pattern 10 covers 7 names",
          len({r.name for r in enh.by_pattern(10)}) == 7,
          str(sorted({r.name for r in enh.by_pattern(10)})))
    check("pattern 29 IS unique (Penitence)", enh.is_pattern_unique(29))
    check(f"all {forge_expected} forge EnhIDs are distinct",
          len(forge) == forge_expected and len(f_ids) == forge_expected,
          f"{len(forge)} entries / {len(f_ids)} ids")
    all_ids = {r.item_id for r in enh.all_enhancements()}
    check(f"all {n} EnhIDs across both files are distinct",
          len(all_ids) == n, f"got {len(all_ids)}")

    print("\n-- basic enhancements (basic_enhancement.jsonl) --")
    check("52369 -> Awe Blast (basic weapon)",
          enh.get(52369) is not None and enh.get(52369).name == "Awe Blast",
          enh.get(52369).describe() if enh.get(52369) else "None")
    check("66435 -> Wizard Armor Enhancement (basic, slot ar)",
          enh.get(66435) is not None
          and enh.get(66435).name == "Wizard Armor Enhancement"
          and enh.get(66435).slot == "ar",
          enh.get(66435).describe() if enh.get(66435) else "None")
    check("66446 -> Lucky Cape Enhancement (basic, slot ba)",
          enh.get(66446) is not None
          and enh.get(66446).name == "Lucky Cape Enhancement"
          and enh.get(66446).slot == "ba",
          enh.get(66446).describe() if enh.get(66446) else "None")
    check("forge entries are tagged source='forge'",
          all(r.source == "forge" for r in forge))
    check("basic entries are tagged source='basic'",
          all(r.source == "basic" for r in basic))

    # One basic NAME spans 51 ids (levels 51..100), so name alone cannot pick
    # a tier -- `level` is what disambiguates.  Forge names are one-per-id.
    wiz_armor = enh.find("Wizard Armor Enhancement")
    check("basic name maps to 51 tiers (levels 51-100)",
          len(wiz_armor) == 51, f"got {len(wiz_armor)}")
    check("their levels run 51..100",
          sorted({r.level for r in wiz_armor}) == list(range(51, 101)),
          str(sorted({r.level for r in wiz_armor})[:5]))
    check("level 100 is NOT unique: two rarity tiers",
          len(enh.by_name_level("Wizard Armor Enhancement", 100)) == 2,
          str([r.item_id for r in enh.by_name_level(
              "Wizard Armor Enhancement", 100)]))
    check("rarity pins down the R6 one (52276)",
          [r.item_id for r in enh.by_name_level(
              "Wizard Armor Enhancement", 100, rarity=6)] == [52276],
          str([r.item_id for r in enh.by_name_level(
              "Wizard Armor Enhancement", 100, rarity=6)]))
    check("rarity pins down the R5 one (66435)",
          [r.item_id for r in enh.by_name_level(
              "Wizard Armor Enhancement", 100, rarity=5)] == [66435],
          str([r.item_id for r in enh.by_name_level(
              "Wizard Armor Enhancement", 100, rarity=5)]))
    check("best_tier(100) picks the stronger R6",
          enh.best_tier("Wizard Armor Enhancement", 100).item_id == 52276,
          enh.best_tier("Wizard Armor Enhancement", 100).describe())
    check("by_name_level(..., 51) -> 19638",
          [r.item_id for r in enh.by_name_level(
              "Wizard Armor Enhancement", 51)] == [19638],
          str([r.item_id for r in enh.by_name_level(
              "Wizard Armor Enhancement", 51)]))
    check("by_name_level with a level the shop lacks is empty",
          enh.by_name_level("Wizard Armor Enhancement", 30) == [])
    check("forge name + matching level still resolves (Valiance, 100)",
          [r.item_id for r in enh.by_name_level("Valiance", 100)] == [70752],
          str([r.item_id for r in enh.by_name_level("Valiance", 100)]))
    check("forge name + wrong level is empty (Valiance, 51)",
          enh.by_name_level("Valiance", 51) == [])

    # Pattern 6 is now genuinely shared across the two files: forge Elysium
    # and basic Wizard.  This is the same class of ambiguity as pattern 10.
    check("pattern 6 now spans forge + basic (Elysium vs Wizard)",
          len({r.name for r in enh.by_pattern(6)}) > 1,
          str(sorted({r.name for r in enh.by_pattern(6)})[:8]))
    check("pattern 6 is NOT unique", not enh.is_pattern_unique(6))

    print("\n-- slot normalisation --")
    for given, want in (("cape", "ba"), ("Cape", "ba"), ("ba", "ba"),
                        ("helm", "he"), ("HELM", "he"), ("weapon", "Weapon"),
                        (None, None), ("", None)):
        check(f"slot_code({given!r}) == {want!r}",
              enh.slot_code(given) == want, str(enh.slot_code(given)))
    try:
        enh.slot_code("headpiece")
    except ValueError:
        check("slot_code('headpiece') raises ValueError", True)
    else:
        check("slot_code('headpiece') raises ValueError", False)

    print("\n-- real inventory: does the right item get picked? --")
    items = load_inventory()
    print(f"  inventory items: {len(items)}")
    malgor = find_item(items, "Malgor's ShadowFlame")
    check("found Malgor's ShadowFlame Blade in captures", malgor is not None)
    if malgor:
        check("it carries EnhID 70752", malgor.enh_id == 70752,
              str(malgor.enh_id))
        check("it reports pattern 10", malgor.enh_pattern_id == 10)
        check("its .enhancement resolves to Valiance",
              malgor.enhancement_name == "Valiance",
              str(malgor.enhancement_name))
        check("enhancement slot is Weapon",
              malgor.enhancement_slot == "Weapon")

        # The whole point: Valiance matches it, Forge does not, even though
        # both share pattern 10.
        check("matches 'Valiance'", enh.item_matches(malgor, "Valiance"))
        check("does NOT match 'Forge' (same pattern, different enhancement)",
              not enh.item_matches(malgor, "Forge"))
        check("does NOT match 'Lacerate' (same pattern, different enhancement)",
              not enh.item_matches(malgor, "Lacerate"))
        check("does NOT match 'Penitence'",
              not enh.item_matches(malgor, "Penitence"))
        check("matches by EnhID 70752", enh.item_matches(malgor, 70752))
        check("slot filter: matches when slot=weapon",
              enh.item_matches(malgor, "Valiance", slot="weapon"))
        check("slot filter: rejected when slot=cape",
              not enh.item_matches(malgor, "Valiance", slot="cape"))

    archmage = find_item(items, "ArchMage's Cowl")
    if archmage:
        check("ArchMage's Cowl carries Forge (helm)",
              archmage.enhancement_name == "Forge",
              str(archmage.enhancement_name))
        check("and it does NOT match 'Valiance'",
              not enh.item_matches(archmage, "Valiance"))

    print("\n-- Player lookups --")
    player = Player()
    player.INVENTORY = items
    got = player.get_items_by_enhancement("Valiance")
    check("get_items_by_enhancement('Valiance') finds 1 item",
          len(got) == 1 and got[0].s_name.startswith("Malgor"),
          ", ".join(i.s_name for i in got))
    check("by name helper agrees",
          len(player.items_by_enhancement_name("Valiance")) == 1)
    check("no owned item has Penitence",
          player.get_item_inventory_by_enhance_id("Penitence") is None)
    legacy = player.get_item_inventory_by_enhance_id(29)
    check("legacy pattern id 29 also finds nothing", legacy is None)
    check("inventory_by_slot('cape') non-empty",
          len(player.inventory_by_slot("cape")) > 0,
          str(len(player.inventory_by_slot("cape"))))
    check("inventory_by_slot('Cape') same result",
          len(player.inventory_by_slot("Cape"))
          == len(player.inventory_by_slot("cape")))

    print("\n-- runtime registration from a live loadShop packet --")
    raw = None
    for line in (REPO / "forge_enhancement.jsonl").read_text(
            encoding="utf-8").splitlines():
        if line.strip():
            raw = line
            break
    payload = json.loads(raw)["b"]["o"]["shopinfo"]
    shop = Shop(payload)
    check("shop recognised as forge", shop.is_forge)
    check("shop parsed 33 items", len(shop.items) == 33, str(len(shop.items)))
    check("shop item keeps original casing (sName)",
          shop.items[0].s_name == "Forge", shop.items[0].s_name)
    check("shop item exposes normalized item_name for lookups",
          shop.items[0].item_name == "forge")
    count = shop.register_enhancements()
    check("register_enhancements() registered 33", count == 33, str(count))
    check("registry still resolves Valiance",
          enh.get(70752) is not None and enh.get(70752).name == "Valiance")

    # a non-forge shop must not be treated as one
    plain = Shop({"ShopID": 1, "sName": "Weapon Shop", "bUpgrd": False,
                  "items": [{"ItemID": 1, "sName": "Stick", "sType": "Sword"}]})
    check("ordinary shop is not a forge", not plain.is_forge)
    check("ordinary shop registers nothing", plain.register_enhancements() == 0)

    print("\n" + "=" * 74)
    print(f"passed {len(PASSED)}   failed {len(FAILED)}")
    if FAILED:
        print("FAILURES:")
        for f in FAILED:
            print("  -", f)
    print("=" * 74)
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
