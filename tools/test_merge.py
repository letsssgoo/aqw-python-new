"""Resep merge shop dibaca dari payload-nya sendiri.

    python tools/test_merge.py

Payload-nya payload nyata (``core/new_things.txt``): Seaview Souvenirs, ShopID
2273, dari capture ``loadShop``.  Yang dijaga di sini adalah bagian yang membuat
``BuyAllMerge`` bisa generik: sebuah entri merge membawa resepnya di ``turnin``
(field yang sama dengan syarat turn-in quest), jadi resepnya **tidak** perlu
ditulis manual per item.

Kalau nanti model berhenti membaca ``turnin``/``MergeID``, atau salah membaca
urutannya, tes ini gagal.
"""
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from core.utils import normalize                  # noqa: E402
from model.shop import Shop                       # noqa: E402

PASS = 0
FAIL = 0


def check(label: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok   {label}   [{got}]")
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, want {want!r}")


def main() -> int:
    print("=" * 74)
    print("merge shop: resep dari payload, bukan ditulis manual")
    print("=" * 74)

    # Payload-nya disimpan sebagai fixture, bukan dibaca dari
    # core/new_things.txt: berkas itu tempat menaruh capture dan isinya berganti
    # tiap kali -- begitu diganti capture fishing, tes ini ikut rusak.
    payload = json.loads((REPO / "tools" / "fixtures" /
                          "seaview_souvenirs_loadshop.json").read_text(
                              encoding="utf-8"))
    shop = Shop(payload)

    check("shop id", shop.shop_id, "2273")
    check("shop name", shop.shop_name, "Seaview Souvenirs")
    check("lokasi shop", shop.location, "ashray")
    check("bukan forge shop", shop.is_forge, False)

    # Shop.get_item compares the *normalised* name the model stores, which is
    # what CoreBots' own shop lookup does too.
    villager = shop.get_item(normalize("Ashray Villager"))
    check("entri ketemu", villager is not None, True)
    check("shop item id", villager.shop_item_id, 10490)
    check("merge id", villager.merge_id, "11671")
    check("merge item tanpa harga gold", villager.cost, 0)
    check("resep dibaca dari turnin", villager.merge_requirements,
          [("57304", "Gold Voucher 25k", 4),
           ("77882", "Sur-gion Token", 30),
           ("8940", "Treasure Chest", 30)])

    hook = shop.get_item(normalize("Ashray Mariner's Hook"))
    check("resep per item, bukan per shop", hook.merge_requirements,
          [("57304", "Gold Voucher 25k", 3),
           ("77882", "Sur-gion Token", 20),
           ("8940", "Treasure Chest", 20)])

    voucher = shop.get_item(normalize("Gold Voucher 25k"))
    check("bukan merge -> tanpa resep", voucher.merge_requirements, [])
    check("bukan merge -> punya harga", voucher.cost, 25000)

    print()
    print("=" * 74)
    print(f"passed {PASS}   failed {FAIL}")
    print("=" * 74)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
