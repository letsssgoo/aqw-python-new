"""Test Command.equip_item()'s inventory -> bank -> neither lookup order.

Covers the rule: equip if held, withdraw from the bank if banked, stop (return
False) only when it is in neither.  Drives the real coroutines, including the
real ``bank_to_inv`` packet path and the local INVENTORY/BANK bookkeeping it
performs.

Run:  python tools/test_equip_bank.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.command import Command                      # noqa: E402
from core.utils import normalize                      # noqa: E402
from model.inventory import ItemInventory             # noqa: E402

PASS = 0
FAIL = 0


def check(label: str, got, want, extra: str = "") -> None:
    global PASS, FAIL
    ok = got == want
    if ok:
        PASS += 1
        print(f"  ok   {label}   [{got}]" if extra == "" else
              f"  ok   {label}   [{extra}]")
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, want {want!r} {extra}")


def item(name: str, item_id: int, *, equipped: bool = False, bank: bool = False
         ) -> ItemInventory:
    """An inventory/bank record.  Bank items omit fields to prove the code
    only needs name + ids to withdraw."""
    data = {
        "ItemID": item_id,
        "sName": name,
        "sES": "ar",
        "sType": "Class",
        "iQty": 1,
        "iLvl": 100,
        "iRty": 5,
        "bEquip": equipped,
        "CharItemID": 9000 + item_id,
        "EnhID": 66435,
        "EnhPatternID": 6,
    }
    if bank:
        data.pop("EnhID", None)
        data.pop("EnhPatternID", None)
    return ItemInventory(data)


class StubPlayer:
    ISDEAD = False
    CURRENT_HP = 5000
    MAX_HP = 5000
    CELL = "r1"

    def __init__(self, inventory, bank=()):
        self.INVENTORY = list(inventory)
        self.BANK = list(bank)

    # --- mirrors of core.player.Player -------------------------------
    def get_item_bank(self, itemName: str):
        for i in self.BANK:
            if i.item_name == normalize(itemName):
                return i
        return None

    def isInBank(self, itemName: str, qty: int = 1, operator: str = ">="):
        found = 0
        for i in self.BANK:
            if i.item_name == normalize(itemName):
                found = i.qty
                break
        return [found >= qty, found]

    @property
    def NAME(self):  # noqa: N802
        return "Tester"


class StubBot:
    def __init__(self, inventory, bank=()):
        self.player = StubPlayer(inventory, bank)
        self.sent: list[str] = []
        self.areaId = "ultratyndarius-1"
        self.player_in_area = []
        self.monsters = []
        self.strMapName = "ultratyndarius"
        self.user_id = 1
        self.scroll_id = 0

    async def ensure_leave_from_combat(self):
        return None

    def write_message(self, msg):
        self.sent.append(msg)

    def subscribe(self, *_):
        return None

    def unsubscribe(self, *_):
        return None


class StubCommand(Command):
    def __init__(self, bot):
        self.bot = bot

    def is_still_connected(self):
        return True


def names(items):
    return [i.item_name for i in items]


def main() -> int:
    print("=" * 74)
    print("equip_item: inventory -> bank -> neither")
    print("=" * 74)

    # --- 1. already equipped: True, nothing sent -----------------------
    print("\n-- already equipped --")
    held = item("Legion Revenant", 48571, equipped=True)
    bot = StubBot([held])
    cmd = StubCommand(bot)
    ok = asyncio.run(cmd.equip_item("Legion Revenant"))
    check("returns True", ok, True)
    check("no packet sent", bot.sent, [], str(bot.sent))

    # --- 2. in inventory, not equipped: equips it ----------------------
    print("\n-- in inventory, not yet equipped --")
    held = item("Legion Revenant", 48571)
    other = item("ArchPaladin", 36920, equipped=True)
    bot = StubBot([held, other])
    cmd = StubCommand(bot)
    ok = asyncio.run(cmd.equip_item("Legion Revenant"))
    check("returns True", ok, True)
    check("equip packet sent", len(bot.sent) == 1, True, str(bot.sent))
    check("class is now marked equipped", held.is_equipped, True)
    check("previous class unequipped", other.is_equipped, False)

    # --- 3. in bank only: withdrawn, then equipped ---------------------
    print("\n-- in bank only: withdraw then equip --")
    in_inv = item("ArchPaladin", 36920, equipped=True)
    banked = item("Quantum Chronomancer", 30001, bank=True)
    bot = StubBot([in_inv], bank=[banked])
    cmd = StubCommand(bot)
    check("bank starts with the class", names(bot.player.BANK),
          ["quantum chronomancer"])
    check("inventory does not have it", "quantum chronomancer"
          in names(bot.player.INVENTORY), False)

    ok = asyncio.run(cmd.equip_item("Quantum Chronomancer"))
    check("returns True", ok, True)
    check("withdrawn out of the bank", names(bot.player.BANK), [])
    check("now present in inventory", "quantum chronomancer"
          in names(bot.player.INVENTORY), True)
    check("bankToInv packet sent first",
          any("bankToInv" in p for p in bot.sent), True, str(bot.sent))
    check("equip packet sent after", any("equipItem" in p for p in bot.sent),
          True, str(bot.sent))
    check("exactly 2 packets (withdraw + equip)", len(bot.sent), 2,
          str(bot.sent))
    check("marked equipped after withdraw", banked.is_equipped, True)
    check("old class unequipped", in_inv.is_equipped, False)

    # --- 4. in neither: False, nothing sent ---------------------------
    print("\n-- in neither inventory nor bank --")
    bot = StubBot([item("ArchPaladin", 36920, equipped=True)],
                  bank=[item("Legion Revenant", 48571, bank=True)])
    cmd = StubCommand(bot)
    ok = asyncio.run(cmd.equip_item("LightCaster"))
    check("returns False", ok, False)
    check("nothing was equipped",
          [i.item_name for i in bot.player.INVENTORY if i.is_equipped],
          ["archpaladin"])
    check("no packet sent", bot.sent, [], str(bot.sent))
    check("bank untouched", names(bot.player.BANK), ["legion revenant"])

    # --- 5. case-insensitive, as the config spells it ------------------
    print("\n-- config spells 'Lord Of Order', inventory has 'Lord of Order' --")
    held = item("Lord of Order", 50741)
    bot = StubBot([held])
    cmd = StubCommand(bot)
    ok = asyncio.run(cmd.equip_item("Lord Of Order"))
    check("returns True", ok, True)
    check("marked equipped", held.is_equipped, True)

    # --- 6. banked but withdrawn into a full match still works ---------
    print("\n-- bank lookup is exact-name, not fuzzy --")
    bot = StubBot([], bank=[item("Scroll of Enrage", 12917, bank=True)])
    cmd = StubCommand(bot)
    ok = asyncio.run(cmd.equip_item("Scroll of Enrage"))
    check("banked scroll withdrawn", ok, True)
    check("moved to inventory", names(bot.player.INVENTORY),
          ["scroll of enrage"])

    print()
    print("=" * 74)
    print(f"passed {PASS}   failed {FAIL}")
    print("=" * 74)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
