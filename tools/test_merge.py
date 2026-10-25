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

    # Hook merge: farmer milik script merge dipanggil dengan cmd lebih dulu.
    # Waktu call site-nya cuma mengirim tiga argumen, tiap merge shop mati
    # dengan "_find_ingredients() missing 1 required positional argument:
    # 'quant'" tepat setelah log "asking the merge script for x50".
    src = (REPO / "bot" / "core_advanced.py").read_text(encoding="utf-8")
    check("call site mengirim cmd",
          "await find_ingredients(cmd, item_id, name, need)" in src, True)

    import importlib
    import inspect
    for mod_name in ("abyssal_zone_merge", "midnight_zone_merge",
                     "seaview_souvenirs_merge", "sea_voice_merge",
                     "trench_observe_merge", "twilight_zone_merge",
                     "undine_commissary_merge"):
        mod = importlib.import_module(f"bot.other.merge_shops.{mod_name}")
        try:
            inspect.signature(mod._find_ingredients).bind(
                object(), "77882", "Sur-gion Token", 50)
            ok = True
        except TypeError:
            ok = False
        check(f"{mod_name} hook (cmd, item_id, name, quant)", ok, True)

    print()
    print("-" * 74)
    print("loop reward: yield tiap pass, berhenti kalau tidak ada kemajuan")

    import asyncio
    from core.command import PassGuard
    from bot.core_advanced import QUIET_PASSES, farm_quest_reward

    class _Item:
        def __init__(self, qty):
            self.qty = qty

    class _Player:
        def __init__(self):
            self.INVENTORY = []
            self.TEMPINVENTORY = []
            self.GOLD = 0

    class _Bot:
        def __init__(self):
            self.player = _Player()
            self.lines = []

        def log(self, text):
            self.lines.append(str(text))

    class _Cmd:
        def __init__(self, reward_after=None):
            self.bot = _Bot()
            self.reward_after = reward_after
            self.passes = 0
            self.quest = None

        def is_still_connected(self):
            return True

        async def sleep(self, ms):
            await asyncio.sleep(0)

        def pass_guard(self, label, max_quiet_passes=QUIET_PASSES):
            return PassGuard(self, label, max_quiet_passes)

        async def register_quest(self, quest_id):
            self.quest = quest_id

        async def has_item(self, name, qty=1, **kwargs):
            return (self.reward_after is not None
                    and self.passes >= self.reward_after)

    async def quiet_scenario():
        cmd = _Cmd()
        ticks = []

        async def farm_pass():
            cmd.passes += 1

        async def other_work():
            while True:
                ticks.append(1)
                await asyncio.sleep(0)

        watcher = asyncio.create_task(other_work())
        try:
            got = await asyncio.wait_for(
                farm_quest_reward(cmd, 9235, "Sur-gion Token", 5, farm_pass),
                timeout=5)
        finally:
            watcher.cancel()
        return cmd, got, len(ticks)

    quiet, got, ticks = asyncio.run(quiet_scenario())
    check("pass tanpa hasil berhenti, tidak menggantung", got, False)
    check("berhenti setelah QUIET_PASSES pass", quiet.passes, QUIET_PASSES)
    check("quest-nya disebut di log",
          any("9235" in line for line in quiet.bot.lines), True)
    check("event loop tetap jalan selama loop", ticks > 0, True)

    async def success_scenario():
        cmd = _Cmd(reward_after=2)

        async def farm_pass():
            cmd.passes += 1
            await asyncio.sleep(0)

        got = await farm_quest_reward(cmd, 9235, "Sur-gion Token", 5, farm_pass)
        return cmd, got

    done, got = asyncio.run(success_scenario())
    check("reward datang -> loop selesai", got, True)
    check("berhenti begitu reward ada", done.passes, 2)

    merge_dir = REPO / "bot" / "other" / "merge_shops"
    raw = [path.name for path in merge_dir.glob("*.py")
           if "while cmd.is_still_connected() and not await cmd.has_item"
           in path.read_text(encoding="utf-8")]
    check("tidak ada loop reward mentah di merge shop", raw, [])

    print()
    print("=" * 74)
    print(f"passed {PASS}   failed {FAIL}")
    print("=" * 74)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
