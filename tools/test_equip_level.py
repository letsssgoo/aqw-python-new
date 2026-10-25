"""End-to-end test of Command.equip_enhancement(..., level=..., rarity=...).

Drives the real coroutine against a stub inventory, so this covers the
resolution, slot inference, tier narrowing and the packet that goes out --
not just the registry lookup.

Covers the basic-enhancement tiers from basic_enhancement.jsonl, where one
*name* spans 51 ids (levels 51..100) and level 100 exists at two rarities.

Run:  python tools/test_equip_level.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.command import Command                      # noqa: E402
from model import enhancement as enh                  # noqa: E402
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


def item(item_id, name, s_es, enh_id, pattern_id, equip=False):
    return ItemInventory({
        "ItemID": item_id, "sName": name, "sES": s_es, "iQty": 1,
        "iRty": 5, "iLvl": 100, "bTemp": False, "iStk": 1, "bUpg": False,
        "bCoins": False, "bStaff": False, "sLink": "", "PatternID": pattern_id,
        "iClass": 0, "iReqCP": 0, "FactionID": 1, "sFaction": "None",
        "iReqRep": 0, "iQSindex": -1, "iQSvalue": 0, "bHouse": False,
        "sType": "Class" if s_es == "ar" else ("Weapon" if s_es == "Weapon"
                                                else "Helm"),
        "sIcon": "none", "sES": s_es, "sElmt": "None", "EnhID": enh_id,
        "iDPS": 100, "EnhPatternID": pattern_id, "iEnh": enh_id,
        "EnhLvl": 100, "EnhRty": 5, "bEquip": bool(equip),
    })


class StubPlayer:
    ISDEAD = False
    CURRENT_HP = 5000
    MAX_HP = 5000
    CELL = "r1"

    def __init__(self, items):
        self.INVENTORY = items

    def get_items_by_enhancement(self, enh_id, slot=None):
        """Mirror of Player.get_items_by_enhancement -- same matching rules."""
        from model import enhancement as _enh
        return [i for i in self.INVENTORY
                if _enh.item_matches(i, enh_id, slot=slot)]

    @property
    def NAME(self):  # noqa: N802 - mirrors Player
        return "Tester"


class StubBot:
    def __init__(self, items):
        self.player = StubPlayer(items)
        self.sent: list[str] = []
        self.player_in_area = []
        self.monsters = []
        self.strMapName = "yulgar"
        self.areaId = "yulgar-1"
        self.user_id = 1

    async def ensure_leave_from_combat(self):
        return None

    def write_message(self, msg):
        self.sent.append(msg)

    def subscribe(self, *_):
        return None

    def unsubscribe(self, *_):
        return None


class StubCommand(Command):
    """Command with the decorators that need a live connection stubbed out."""

    def __init__(self, bot):
        self.bot = bot

    def is_still_connected(self):
        return True

    async def sleep(self, ms):
        return None


def equipped_name(bot):
    for it in bot.player.INVENTORY:
        if it.is_equipped:
            return it.item_name
    return None


def main() -> int:
    n = enh.load(force=True)
    print("=" * 74)
    print(f"equip_enhancement level/rarity tiers  (registry: {n})")
    print("=" * 74)

    # Inventory: two classes socketed with the two level-100 Wizard Armor
    # tiers, plus a helm socketed with Lucky Helm R6.
    items = [
        item(100, "Wizard Robe of Testing", "ar", 66435, 6),   # Wiz Armor L100 R5
        item(101, "Awoken Class Item", "ar", 52276, 6),        # Wiz Armor L100 R6
        item(102, "Omni Cowl", "he", 66448, 9),                # Lucky Helm L100 R6
        item(103, "Plain Sword", "Weapon", 1955, 1),           # uncaptured id
    ]
    bot = StubBot(items)
    cmd = StubCommand(bot)

    def run(coro):
        bot.sent.clear()
        for it in items:
            it.is_equipped = False
        return asyncio.run(coro)

    print("\n-- name + level + rarity pins exactly one tier --")
    ok = run(cmd.equip_enhancement("Wizard Armor Enhancement",
                                   level=100, rarity=5))
    check("level=100 rarity=5 succeeds", ok, True)
    check("...and equips the R5 class", equipped_name(bot),
          "wizard robe of testing", str(equipped_name(bot)))
    check("packet sent", len(bot.sent) == 1, True, str(bot.sent))

    ok = run(cmd.equip_enhancement("Wizard Armor Enhancement",
                                   level=100, rarity=6))
    check("level=100 rarity=6 succeeds", ok, True)
    check("...and equips the R6 class", equipped_name(bot),
          "awoken class item", str(equipped_name(bot)))

    print("\n-- level alone at the cap: 2 tiers, picks higher rarity --")
    ok = run(cmd.equip_enhancement("Wizard Armor Enhancement", level=100))
    check("level=100 (no rarity) succeeds", ok, True)
    check("...and picks the R6 tier", equipped_name(bot),
          "awoken class item", str(equipped_name(bot)))

    print("\n-- a level the shop does not sell fails loudly --")
    ok = run(cmd.equip_enhancement("Wizard Armor Enhancement", level=30))
    check("level=30 refused", ok, False)
    check("...and nothing was equipped", equipped_name(bot), None)
    check("...and no packet went out", bot.sent, [])

    ok = run(cmd.equip_enhancement("Wizard Armor Enhancement",
                                   level=100, rarity=9))
    check("level=100 rarity=9 (no such tier) refused", ok, False)
    check("...and nothing was equipped", equipped_name(bot), None)

    print("\n-- basic helm by name + level --")
    ok = run(cmd.equip_enhancement("Lucky Helm Enhancement", level=100))
    check("Lucky Helm level=100 succeeds", ok, True)
    check("...and equips the helm", equipped_name(bot), "omni cowl",
          str(equipped_name(bot)))

    print("\n-- forge names keep working, level is optional --")
    # No Forge-enhanced item in this inventory: must fail, not raise.
    ok = run(cmd.equip_enhancement("Valiance"))
    check("forge name with no owned item returns False", ok, False)
    ok = run(cmd.equip_enhancement("Valiance", level=100))
    check("forge name + matching level, still unowned -> False", ok, False)
    ok = run(cmd.equip_enhancement("Valiance", level=51))
    check("forge name + wrong level -> False (no tier)", ok, False)

    print("\n-- an uncaptured EnhID still selects by id --")
    ok = run(cmd.equip_enhancement(1955))
    check("uncaptured EnhID 1955 succeeds", ok, True)
    check("...and equips it", equipped_name(bot), "plain sword",
          str(equipped_name(bot)))

    print("\n-- bad slot is still rejected before any lookup --")
    ok = run(cmd.equip_enhancement("Wizard Armor Enhancement",
                                   slot="headpiece", level=100))
    check("unknown slot refused", ok, False)

    print("\n-- level on an id target is ignored, not an error --")
    ok = run(cmd.equip_enhancement(66435, level=100))
    check("id + level still succeeds", ok, True)
    check("...and equips the R5 class", equipped_name(bot),
          "wizard robe of testing", str(equipped_name(bot)))

    print("\n-- enhance_if_missing: socket it into what is already worn --")
    # A fresh account: a plain weapon is worn and nothing carries Valiance.
    for it in items:
        it.is_equipped = False
    sword = items[3]                       # plain sword, Weapon, lvl 100
    sword.is_equipped = True
    bot.sent.clear()
    ok = asyncio.run(cmd.equip_enhancement("Valiance",
                                          enhance_if_missing=True))
    check("nothing carries Valiance -> socketed instead", ok, True)
    check("...one enhanceItemShop packet", len(bot.sent), 1, str(bot.sent))
    fields = bot.sent[-1].split("%")[5:8] if bot.sent else []
    check("...onto the worn weapon, Valiance R7 from shop 2142", fields,
          [str(sword.item_id), "70752", "2142"],
          str(bot.sent[-1]) if bot.sent else "no packet")

    print("\n-- nothing worn in that slot -> refuse, no packet --")
    for it in items:
        it.is_equipped = False
    bot.sent.clear()
    ok = asyncio.run(cmd.equip_enhancement("Valiance",
                                          enhance_if_missing=True))
    check("no item in the slot -> False", ok, False)
    check("...and nothing was sent", bot.sent, [])

    print("\n-- the socketed tier stays at or under the item's level --")
    for it in items:
        it.is_equipped = False
    helm = items[2]                        # omni cowl, Helm
    helm.level = 70
    helm.is_equipped = True
    bot.sent.clear()
    ok = asyncio.run(cmd.equip_enhancement("Wizard Helm Enhancement",
                                          enhance_if_missing=True))
    check("helm at lvl 70 still succeeds", ok, True)
    fields = bot.sent[-1].split("%")[5:8] if bot.sent else []
    check("...and takes the lvl-70 R5 tier (39731), not lvl 100", fields,
          [str(helm.item_id), "39731", "765"],
          str(bot.sent[-1]) if bot.sent else "no packet")

    print()
    print("=" * 74)
    print(f"passed {PASS}   failed {FAIL}")
    print("=" * 74)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
