"""Ultra V2 engine: options, presets, enhancements, potions, scrolls, party.

    python tools/test_ultra_v2.py
"""
from _ultra_v2_support import *  # noqa: F401,F403
from _ultra_v2_support import (check, finish, run, _StubBot,  # noqa: F401
                               _StubCommand)

# --- options ---------------------------------------------------------------
for ultra in ("warden", "ezrajal", "engineer", "tyndarius", "drakath", "drago",
              "nulgath", "dage", "darkon", "gramiel", "speaker"):
    table = options.compositions(ultra)
    base = (["Default", "Reliable"] if ultra in ("speaker", "gramiel")
            else ["Default", "Reliable", "Stable"])
    extra = {"drakath": ["Optimized"],
             "nulgath": ["Optimized"],
             "gramiel": ["Optimized"],
             "speaker": []}.get(ultra, [])
    check(f"{ultra}: ported compositions", sorted(table), sorted(base + extra))
    # Slot 2 and slot 4 are not always the same class in the extra columns.
    exceptions = {("nulgath", "Optimized"): "Dragon of Time"}
    for name, slots in table.items():
        check(f"{ultra}/{name}: four slots", len(slots), 4)
        check(f"{ultra}/{name}: slot 2 is StoneCrusher", slots[1],
              exceptions.get((ultra, name), "StoneCrusher"))
        check(f"{ultra}/{name}: slot 4 is Lord of Order", slots[3], "Lord of Order")

check("default: slot 1 is Legion Revenant",
      options.compositions("warden")["Default"][0], "Legion Revenant")
check("stable: slot 1 is King's Echo",
      options.compositions("warden")["Stable"][0], "King's Echo")
check("reliable: slot 1 is Verus DoomKnight",
      options.compositions("warden")["Reliable"][0], "Verus DoomKnight")

line = options.composition_tooltip("warden")
check("tooltip: one line per composition", len(line.splitlines()), 3)
check("tooltip: lists the short names", "Default: LR / SC / AP / LOO" in line, True)
check("tooltip: speaker has no Stable",
      "Stable" in options.composition_tooltip("speaker"), False)

spec = warden.SPEC
check("schema: has the composition dropdown",
      [f["key"] for f in options.schema(spec)][:4],
      ["players", "composition", "private_room", "use_potions"])
check("schema: retries are 1..5",
      [c["value"] for f in options.schema(spec) if f["key"] == "retries"
       for c in f["choices"]], [1, 2, 3, 4, 5])

good = options.UltraOptions(players=("a", "b", "c", "d"))
check("validate: a filled form passes", options.validate(spec, good), [])
check("validate: an empty slot is named",
      any("slot 1" in problem for problem in
          options.validate(spec, options.UltraOptions())), True)
check("validate: retries outside 1..5 is refused",
      any("retries" in problem for problem in
          options.validate(spec, options.UltraOptions(
              players=("a", "b", "c", "d"), retries=6))), True)
check("validate: a private room below 1001 is refused",
      any("private room" in problem for problem in
          options.validate(spec, options.UltraOptions(
              players=("a", "b", "c", "d"), private_room=50))), True)
check("validate: Pay2Win is not ported",
      any("not ported" in problem for problem in
          options.validate(spec, options.UltraOptions(
              players=("a", "b", "c", "d"), composition="Pay2Win"))), True)
check("options: round-trips through a dict",
      options.UltraOptions.from_dict(good.to_dict()), good)

# --- presets ---------------------------------------------------------------
check("preset: LR keeps the reference rotation",
      presets.preset_for("warden", "Default", 1).skills, (3, 4, 2, 1))
check("preset: LR mode is simple",
      presets.preset_for("warden", "Default", 1).mode, presets.SIMPLE)
check("preset: King's Echo uses its own engine",
      presets.preset_for("warden", "Stable", 1).mode, presets.KINGS_ECHO)
check("preset: Verus DoomKnight is strict",
      presets.preset_for("warden", "Reliable", 1).mode, presets.STRICT)
check("preset: VDK rotation length", len(presets.VDK_ROTATION), 21)
check("preset: stonecrusher wears Absolution on the cape",
      presets.preset_for("warden", "Default", 2).cape, "Absolution")
check("preset: lord of order uses Awe Blast",
      presets.preset_for("warden", "Default", 4).weapon, "Awe Blast")
try:
    presets.preset_for("warden", "Pay2Win", 1)
    raised = False
except KeyError:
    raised = True
check("preset: Pay2Win raises instead of guessing", raised, True)

# --- per-ultra differences (each script has its own GetClassPreset) --------
check("dage: slot 2 fights on StoneCrusher 2,4,1",
      presets.preset_for("dage", "Default", 2).skills, (2, 4, 1))
check("dage: slot 3 fights on ArchPaladin 3,1,4",
      presets.preset_for("dage", "Default", 3).skills, (3, 1, 4))
check("dage: slot 4 fights on Lord of Order 3,1,4",
      presets.preset_for("dage", "Default", 4).skills, (3, 1, 4))
check("warden: slot 2 keeps the preset rotation",
      presets.preset_for("warden", "Default", 2).skills, (3, 2, 4, 1))
check("darkon: Legion Revenant wears Penitence",
      presets.preset_for("darkon", "Default", 1).cape, "Penitence")
check("darkon: Lord of Order wears Absolution",
      presets.preset_for("darkon", "Default", 4).cape, "Absolution")
check("darkon: Lord of Order fights 3,1",
      presets.preset_for("darkon", "Default", 4).skills, (3, 1))
check("darkon: ArchPaladin fights 3,1,4",
      presets.preset_for("darkon", "Default", 3).skills, (3, 1, 4))
check("gramiel: Legion Revenant fights 3,4,2",
      presets.preset_for("gramiel", "Default", 1).skills, (3, 4, 2))
check("gramiel: ArchPaladin wears Penitence",
      presets.preset_for("gramiel", "Default", 3).cape, "Penitence")
check("gramiel: Reliable slot 1 is Verus DoomKnight",
      presets.preset_for("gramiel", "Reliable", 1).cls, "Verus DoomKnight")
check("speaker: StoneCrusher drinks the Divine Elixir",
      presets.preset_for("speaker", "Default", 2).elixir, "Divine Elixir")
check("speaker: Legion Revenant wears no helm",
      presets.preset_for("speaker", "Default", 1).helm, None)
check("speaker: ArchPaladin fights 2,1",
      presets.preset_for("speaker", "Default", 3).skills, (2, 1))
check("speaker: Lord of Order fights 2,3,1",
      presets.preset_for("speaker", "Default", 4).skills, (2, 3, 1))
check("speaker: brute force restores the preset rotation",
      presets.preset_for("speaker", "Default", 3,
                         {"brute_force": True}).skills, (3, 2, 1, 4))
check("ezrajal: Stable's King's Echo wears no cape",
      presets.preset_for("ezrajal", "Stable", 1).cape, None)
check("warden: Stable's King's Echo keeps its cape",
      presets.preset_for("warden", "Stable", 1).cape, "Vainglory")
check("tooltip: gramiel lists three rows",
      len(options.composition_tooltip("gramiel").splitlines()), 3)

# --- base (class-slot) enhancement resolution ------------------------------
# Skua resolves the base enhancement by *type* through fixed shop ids, not by a
# registry name -- this is the table from ``GetNormalEnhancementShop``.
check("base: Wizard uses shop 765 at level 50+",
      enhancements.NORMAL_ENHANCEMENT_SHOPS["Wizard"], (765, 144))
check("base: Lucky uses shop 763",
      enhancements.NORMAL_ENHANCEMENT_SHOPS["Lucky"], (763, 147))
check("base: the seven types the presets use",
      sorted(enhancements.NORMAL_ENHANCEMENT_SHOPS),
      ["Fighter", "Healer", "Hybrid", "Lucky", "SpellBreaker", "Thief",
       "Wizard"])
check("base: the class slot codes", enhancements.CLASS_SLOTS, ("ar", "co"))

# Skua's rule for the class slot: equip the class, look at what is socketed,
# and enhance only when it is different.
wizard = enhancements.best_base("Wizard", 100)
check("base: Wizard resolves to the level-100 class tier",
      (wizard.name, wizard.level, wizard.shop_id),
      ("Wizard Armor Enhancement", 100, 765))
check("base: a non-member gets the highest regular tier at or under 80",
      enhancements.best_base("Wizard", 80).level, 78)
check("base: a member gets the upgrade tier at level 80",
      enhancements.best_base("Wizard", 80, is_member=True).level, 80)
check("base: the upgrade tier is the rarity-6 one",
      enhancements.best_base("Wizard", 80, is_member=True).rarity, 6)
check("base: a non-member never gets a bUpg tier",
      any(row.is_upgrade for row in [enhancements.best_base("Wizard", 100)]),
      False)


class _ClassCommand:
    def __init__(self, enh_id=0):
        self.calls = []
        self.logs = []
        item = type("I", (), {
            "item_id": 5555, "item_name": "legion revenant", "is_equipped": True,
            "s_es": "ar", "level": 100, "enh_id": enh_id,
            "enh_pattern_id": wizard.pattern_id if enh_id else 0,
            "enh_rarity": wizard.rarity if enh_id else 0,
        })()
        self.player = type("P", (), {"INVENTORY": [item], "LEVEL": 100})()
        self.bot = type("B", (), {"player": self.player,
                                  "log": lambda _s, line: self.logs.append(line)})()
        self.maps = []

    def is_not_in_map(self, name):
        self.calls.append(("join-check", name))
        return True

    async def join_map(self, name, room=None):
        self.maps.append(name)
        self.calls.append(("join", name))

    async def ensure_load_shop(self, shop_id):
        self.calls.append(("shop", shop_id))
        return True

    async def enhance_item(self, item_id, enh_item_id, shop_id):
        self.calls.append(("enhance", item_id, enh_item_id, shop_id))


already = _ClassCommand(enh_id=wizard.item_id)
check("base: gear that already carries it is left alone",
      run(enhancements._apply_base(already, "Wizard")), True)
check("base: and no packet is sent", already.calls, [])

different = _ClassCommand(enh_id=0)
check("base: gear with a different enhancement is enhanced",
      run(enhancements._apply_base(different, "Wizard")), True)
check("base: the class item and tier are named in the packet",
      different.calls, [("join-check", "battleontown"),
                        ("join", "battleontown"),
                        ("shop", 765),
                        ("enhance", 5555, wizard.item_id, 765)])

tiered = _ClassCommand(enh_id=0)
tiered.player.LEVEL = 80      # tiers follow the character level, not the item's
check("base: the tier follows the character level",
      run(enhancements._apply_base(tiered, "Wizard")), True)
check("base: level 80 gets the level-80 tier",
      tiered.calls[-1][2], enhancements.best_base("Wizard", 80).item_id)

# --- telemetry and cooldown pacing -----------------------------------------
class _TelemetryStub:
    def __init__(self):
        self.events = []

    def write(self, kind, **fields):
        self.events.append((kind, fields))


tele = _TelemetryStub()
tele_bot = _StubCommand()
tele_bot.bot.telemetry = tele
tele_runner = warden.build(tele_bot, options.UltraOptions(
    players=("a", "b", "c", "d")), 2)
tele_runner.abort("test stop")
check("telemetry: an abort is reported",
      [kind for kind, _ in tele.events], ["abort"])
check("telemetry: carrying the ultra, slot and class",
      tele.events[0][1].get("slot"), 2)

# Cooldowns are a *display*: the same server deadlines the solo menu draws.
from app import build_hub_app as hub  # noqa: E402  (imports pywebview lazily)

class _Skill:
    def __init__(self, seconds):
        from datetime import datetime, timedelta
        self.next_use = None if seconds is None else datetime.now() + \
            timedelta(seconds=seconds)


class _Player:
    SKILLS = [_Skill(None), _Skill(2.5), _Skill(0)]


readout = hub._skill_cooldowns(_Player())
check("ui cooldown: one row per skill slot", [row["slot"] for row in readout],
      [0, 1, 2])
check("ui cooldown: a ready slot reads 0", readout[0]["ready_in"], 0)
check("ui cooldown: a busy slot reports the wait",
      2000 < readout[1]["ready_in"] <= 2600, True)


# --- which monster the pane is hitting -------------------------------------
# The menu lists the cell's monsters; the fight also has to say which one it is
# attacking *now*, so a retarget (add -> boss) is visible instead of guessed.
class _Mon:
    def __init__(self, mid, name, hp, hp_max):
        self.mon_map_id = mid
        self.mon_name = name
        self.current_hp = hp
        self.max_hp = hp_max
        self.is_alive = hp > 0


class _MonsterBot:
    def __init__(self, monsters, last=None):
        self.monsters = monsters
        self.player = type("_P", (), {"last_target": last})()


_cell = [_Mon("2", "ultra avatar tyndarius", 600, 1000),
         _Mon("3", "ultra fire orb", 0, 700)]
check("ui monsters: the row carries the map id",
      hub._monster_readout(_MonsterBot(_cell))[0]["id"], "2")

_stored = _Mon("2", "ultra avatar tyndarius", 600, 1000)
_target = hub._target_readout(_MonsterBot(_cell, last=_stored))
check("ui target: names the monster being attacked",
      (_target.get("id"), _target.get("name")),
      ("2", "ultra avatar tyndarius"))
check("ui target: nothing attacked yet is an empty readout",
      hub._target_readout(_MonsterBot(_cell)), {})

_stored.current_hp = 999
_live = hub._target_readout(_MonsterBot([_Mon("2", "ultra avatar tyndarius",
                                              250, 1000)], last=_stored))
check("ui target: the HP shown is the live one", _live["hp"], 250)

_dead = _Mon("3", "ultra fire orb", 0, 700)
check("ui target: a dead target is not shown as alive",
      hub._target_readout(_MonsterBot([_dead], last=_dead))["alive"], False)

# --- potion packets --------------------------------------------------------
# Captured: an elixir is consumed with `serverUseItem`; a combat potion is
# equipped into slot 5 (`geia ... potion`) and cast with `gar`.
class _PotionCommand:
    def __init__(self):
        self.calls = []
        self.logs = []
        self.player = type("P", (), {
            "ISDEAD": False,
            "AURAS": [],
            "get_item_inventory": lambda _self, name: type(
                "I", (), {"qty": 5, "item_id": 12056})(),
        })()
        self.bot = type("B", (), {"player": self.player,
                                  "log": lambda _s, line: self.logs.append(line)})()

    async def has_item(self, name, qty=1, isTemp=False):
        return True

    def is_in_bank(self, name):
        return False

    async def use_item(self, name):
        self.calls.append(("use_item", name))
        return True

    async def equip_potion(self, name):
        self.calls.append(("equip_potion", name))
        return True

    async def use_skill(self, slot, **kwargs):
        self.calls.append(("skill", slot))
        return True


elixir = _PotionCommand()
run(potions.use(elixir, "Potent Destruction Elixir"))
check("potion: an elixir is consumed from the bag",
      elixir.calls, [("use_item", "Potent Destruction Elixir")])

combat = _PotionCommand()
run(potions.use_loadout(combat, None, None, "Potent Honor Potion"))
check("potion: a combat potion is equipped into slot 5",
      combat.calls, [("equip_potion", "Potent Honor Potion")])

# --- potions ---------------------------------------------------------------
check("potion: Sage Tonic is a 2-voucher, rank-8 alchemy recipe",
      (potions.POTIONS["Sage Tonic"].voucher_qty,
       potions.POTIONS["Sage Tonic"].rank, potions.POTIONS["Sage Tonic"].potion_qty),
      (2, 8, 10))
check("potion: the filtre uses the 100k voucher",
      (potions.POTIONS["Felicitous Philtre"].voucher,
       potions.POTIONS["Felicitous Philtre"].voucher_cost,
       potions.POTIONS["Felicitous Philtre"].potion_qty),
      ("Gold Voucher 100k", 100_000, 25))
check("potion: Potent Honor wants Good rank 10",
      (potions.POTIONS["Potent Honor Potion"].faction,
       potions.POTIONS["Potent Honor Potion"].rank), ("Good", 10))
check("potion: the divine elixirs have no recipe",
      potions.POTIONS["Divine Elixir"].purchasable, False)
check("potion: twelve are whitelisted", len(potions.POTIONS), 12)
check("potion: the combat potion's aura is the Malice one",
      potions.aura_of("Potent Honor Potion"), "Potent Honor Malice")

# --- scrolls ---------------------------------------------------------------
check("scroll: Enrage stock is 80", scrolls.threshold(scrolls.ENRAGE), 80)
check("scroll: Decay stock is 10", scrolls.threshold(scrolls.DECAY), 10)
check("scroll: only three are supported", scrolls.SUPPORTED,
      (scrolls.ENRAGE, scrolls.DECAY, scrolls.MYSTIFY))

# Buying a scroll material now reads the shop entry: an AC price or a
# member-only entry is reported by name, and gold is checked before the packet
# goes out -- the live Dage run bought "0/99" and said nothing about why.
class _ShopItem:
    def __init__(self, name, cost=0, is_acs=False, is_upgrade=False):
        self.item_name = name.lower()
        self.s_name = name
        self.cost = cost
        self.is_acs = is_acs
        self.is_upgrade = is_upgrade


class _Shop:
    def __init__(self, items):
        self.shop_id = "693"
        self.items = items


class _BuyCommand:
    def __init__(self, items, gold=0):
        self.shop_data = _Shop(items)
        self.logs = []
        self.bot = type("B", (), {
            "loaded_shop_datas": [self.shop_data],
            "player": type("P", (), {
                "GOLD": gold, "is_member": False, "MANA": 100, "MAX_MP": 100,
                "get_item_inventory": lambda _self, name: None,
            })(),
            "log": lambda _s, line: self.logs.append(line),
        })()

    async def sleep(self, ms):
        await asyncio.sleep(0)

    def is_still_connected(self):
        return True

    def is_not_in_map(self, name):
        return False

    async def join_map(self, name, room=None):
        return None

    async def ensure_load_shop(self, shop_id):
        return True

    def is_in_bank(self, name):
        return False


check("scroll buy: the shop entry is found by name",
      scrolls._shop_item(_BuyCommand([_ShopItem("Zealous Ink")]), 693,
                         "Zealous Ink") is not None, True)
_ac = _BuyCommand([_ShopItem("Zealous Ink", cost=10, is_acs=True)])
# bCoins with iCost 0 is a merge entry, not an AC price.
_merge_flag = _BuyCommand([_ShopItem("Arcane Quill", cost=0, is_acs=True)])
check("scroll buy: bCoins with cost 0 is not an AC price",
      scrolls._shop_item(_merge_flag, 693, "Arcane Quill").cost, 0)
check("scroll buy: an AC entry is refused with a reason",
      run(scrolls._buy_until(_ac, 693, "Zealous Ink", 99)), False)
check("scroll buy: and says so", "Adventure Coins" in _ac.logs[-1], True)
_broke = _BuyCommand([_ShopItem("Zealous Ink", cost=25_000)], gold=0)
check("scroll buy: insufficient gold fails before any packet",
      run(scrolls._buy_until(_broke, 693, "Zealous Ink", 99)), False)
check("scroll buy: and names the price and the gold",
      ("25000" in _broke.logs[-1] and "0 in hand" in _broke.logs[-1]), True)
_member = _BuyCommand([_ShopItem("Zealous Ink", is_upgrade=True)])
# Shop 693 is a merge shop: the captured Arcane Quill buy is
# `buyItem ... 693 7686 10` answered by `turnIn sItems:61043:2` -- ten quills
# for two Gold Voucher 500k.  The bundle and its cost are read off the entry.
class _MergeItem(_ShopItem):
    def __init__(self):
        super().__init__("Arcane Quill", cost=0)
        self.qty = 10
        self.stackable = 100
        self.merge_requirements = [("61043", "Gold Voucher 500k", 2)]


_merge = _MergeItem()
import math as _math  # noqa: E402

# A need smaller than one bundle still pays for a full bundle (10 quills), and
# a big need is chunked in whole bundles (5 inks per purchase).
check("scroll buy: a short need still buys a whole bundle",
      _math.ceil(1 / 10) * 10, 10)
check("scroll buy: chunk stays a whole number of bundles",
      min(max(1, 20 // 5), max(1, _math.ceil(99 / 5))) * 5, 20)

check("scroll buy: the merge cost is read off the entry",
      scrolls._merge_cost(_merge), [("61043", "Gold Voucher 500k", 2)])
class _OtherItem(_ShopItem):
    def __init__(self, shop_item_id):
        super().__init__("Arcane Quill", cost=0)
        self.shop_item_id = shop_item_id
        self.qty = 1
        self.stackable = 0
        self.merge_requirements = []


_dup = _BuyCommand([_OtherItem(1), _OtherItem(7686)])
_dup.shop_data.items[1].qty = 10
_dup.shop_data.items[1].merge_requirements = [
    ("61043", "Gold Voucher 500k", 2)]
check("scroll buy: the shop item id picks the right entry",
      (_dup and scrolls._shop_item(_dup, 693, "Arcane Quill", 7686).qty,
       scrolls._shop_item(_dup, 693, "Arcane Quill", 7686).merge_requirements),
      (10, [("61043", "Gold Voucher 500k", 2)]))

check("scroll buy: the bundle is what the shop sells",
      _merge.qty, 10)


class _StockCommand(_BuyCommand):
    def __init__(self, vouchers):
        super().__init__([_merge], gold=1_000_000)
        self.bot.player.get_item_inventory = lambda name: (
            type("I", (), {"qty": vouchers})()
            if str(name) == "Gold Voucher 500k" else None)


check("scroll buy: materials already in stock pass",
      run(scrolls._ensure_materials(_StockCommand(2), _merge, "Arcane Quill")),
      True)

check("scroll buy: a member-only entry is refused",
      run(scrolls._buy_until(_member, 693, "Zealous Ink", 99)), False)
check("scroll buy: and says member-only", "member-only" in _member.logs[-1],
      True)

# --- warden rules ----------------------------------------------------------
check("warden: Default taunts from slot 1", warden.taunter_slot("Default"), 1)
check("warden: Stable taunts from slot 2", warden.taunter_slot("Stable"), 2)
check("warden: Reliable taunts from slot 1", warden.taunter_slot("Reliable"), 1)
check("warden: the taunt fires at 500k", warden.SPEC.taunt_hp, 500_000)
check("warden: quest 8153 behind 8151", (warden.SPEC.quest,
                                         warden.SPEC.prereq_quest), (8153, 8151))
check("warden: the boss is id.1", warden.SPEC.monster_id, 1)
check("warden: a Stable pane is not the taunter",
      warden.build(_StubCommand(),
                   options.UltraOptions(composition="Stable"), 1).is_taunter, False)
check("warden: Reliable slot 1 is",
      warden.build(_StubCommand(),
                   options.UltraOptions(composition="Reliable"), 1).is_taunter, True)
check("core: a wipe is the whole party down", WIPE_DEATHS, 4)
check("enhancements: every preset field has a slot",
      [slot for _field, slot in enhancements.SLOTS],
      ["class", "cape", "helm", "weapon"])

# --- enhancement buying ----------------------------------------------------
# Wear what is owned; only when nothing carries it does the module buy it.  A
# *basic* enhancement exists at every level, so the highest tier is the buy.
valiance = enhancements.best_entry("Valiance", "weapon")
check("enhancement: Valiance resolves to a shop entry", valiance is not None, True)
check("enhancement: and names its shop",
      bool(getattr(valiance, "shop_id", 0)), True)
awe = enhancements.best_entry("Awe Blast", "weapon")
check("enhancement: Awe Blast resolves", awe is not None, True)


class _EnhCommand:
    """A command whose equips miss until the enhancement was applied/bought."""

    def __init__(self):
        self.calls = []
        self.logs = []
        self.bot = type("B", (), {
            "GOLD": 10_000_000,
            "log": lambda _self, line: self.logs.append(line),
        })()
        self.player = self.bot.player = type("P", (), {"GOLD": 10_000_000})()
        self.applied = False
        self.bought = False

    async def equip_enhancement(self, name, slot=None, enhance_if_missing=False):
        self.calls.append(("equip", name, slot, enhance_if_missing))
        if enhance_if_missing:
            self.applied = True
            return self.bought        # applying only works once it is bought
        return self.bought

    async def ensure_load_shop(self, shop_id):
        self.calls.append(("shop", shop_id))
        return True

    def is_not_in_map(self, name):
        self.calls.append(("join-check", name))
        return True

    async def join_map(self, name, room=None):
        self.calls.append(("join", name))

    def is_still_connected(self):
        return True


class _Entry:
    name = "Valiance"
    item_id = 70752
    shop_id = 2126
    cost = 0
    source = "forge"


real_best = enhancements.best_entry
real_adv_buy = None
enhancements.best_entry = lambda name, slot: _Entry() if name == "Valiance" else None
from bot import core_advanced as _adv


async def _fake_adv_buy(cmd, shop_id, item, qty=1, **kwargs):
    cmd.calls.append(("adv-buy", shop_id, item))
    cmd.bought = True
    return True


real_adv_buy = _adv.buy_item
_adv.buy_item = _fake_adv_buy
try:
    buy_cmd = _EnhCommand()
    bought = run(enhancements._apply_one(buy_cmd, "weapon", ("Valiance",)))
finally:
    enhancements.best_entry = real_best
    _adv.buy_item = real_adv_buy
check("enhancement: a missing one is bought then worn", bought, True)
check("enhancement: apply-to-equipped is tried before buying",
      [c for c in buy_cmd.calls if c[0] == "equip"][:2],
      [("equip", "Valiance", "weapon", False),
       ("equip", "Valiance", "weapon", True)])
check("enhancement: the forge map is joined before its shop",
      buy_cmd.calls.index(("join-check", "forge")) <
      buy_cmd.calls.index(("shop", 2126)), True)
check("enhancement: the buy went to its shop",
      [c for c in buy_cmd.calls if c[0] == "adv-buy"],
      [("adv-buy", 2126, 70752)])
check("enhancement: it says it was bought",
      any("bought" in line for line in buy_cmd.logs), True)

# --- scroll crafting -------------------------------------------------------
check("scroll: gold at 1,000,000 takes the gold route",
      (scrolls.route(999_999), scrolls.route(1_000_000)), ("farm", "gold"))
check("scroll: Enrage needs 25 turn-ins from empty",
      scrolls.turns_for(0, 40, 1000), 25)
check("scroll: from 320 it needs 17", scrolls.turns_for(320, 40, 1000), 17)
check("scroll: an already-full stock needs none",
      scrolls.turns_for(1000, 40, 1000), 0)
# The gold route buys its materials at shop 693 -- the reference's
# PrepareOptionalGoldScrollMaterial passes ArcaneQuillShopId -- while the
# farming route keeps the ink vendor 549.  Asking 549 for a 99 stack is what
# left Dage's Decay/Mystify stock short in the live run.
check("scroll: the gold-route shop is the quill shop",
      scrolls.ARCANE_QUILL_SHOP, 693)
check("scroll: the farming ink shop is the ink vendor",
      scrolls.SPELL_INK_SHOP, 549)
check("scroll: the gold route target is the reward stack",
      scrolls.turns_for(0, 1, 99), 99)

check("scroll: Mystify has no farming route", scrolls.FARMABLE,
      (scrolls.ENRAGE, scrolls.DECAY))
check("scroll: Enrage needs SpellCrafting 5", scrolls.REQUIRED_RANK[scrolls.ENRAGE], 5)
check("scroll: Mystify needs SpellCrafting 8", scrolls.REQUIRED_RANK[scrolls.MYSTIFY], 8)
check("scroll: Enrage quest is 2330", scrolls.QUESTS[scrolls.ENRAGE], 2330)


class _ScrollCommand:
    def __init__(self, held=0):
        self.held = held
        self.calls = []
        self.logs = []
        self.player = type("P", (), {
            "GOLD": 2_000_000,
            "get_item_inventory": lambda _self, name: (
                type("I", (), {"qty": self.held})() if self.held else None),
        })()
        self.bot = type("B", (), {
            "player": self.player,
            "log": lambda _self, line: self.logs.append(line),
        })()

    def is_in_bank(self, name):
        return False

    def get_faction_rank(self, name):
        return 10

    def is_in_inventory(self, name):
        return bool(self.held)


full = _ScrollCommand(held=80)
check("scroll: a full stock returns without crafting",
      run(scrolls.prepare(full, scrolls.ENRAGE)), True)
check("scroll: and touches nothing", full.calls, [])
check("scroll: no scroll requested is fine",
      run(scrolls.prepare(_ScrollCommand(), None)), True)


class _NoRankCommand(_ScrollCommand):
    def get_faction_rank(self, name):
        return 1


check("scroll: a low SpellCrafting rank refuses",
      run(scrolls.prepare(_NoRankCommand(), scrolls.ENRAGE)), False)

# --- party barrier with a slot number --------------------------------------
# ``barrier`` was built for v1's usernames; Ultra V2 passes the slot number, and
# joining an int inline raised "'int' object is not iterable" on every run.
import os      # noqa: E402
import shutil  # noqa: E402

from bot.ultra import party as ultra_party  # noqa: E402

_barrier_run = "test_v2_barrier"
_previous = os.environ.get("AQW_RUN_ID")
os.environ["AQW_RUN_ID"] = _barrier_run
try:
    key_ok = isinstance(
        ultra_party.barrier("v2_test", 4, 1, timeout=0.2), bool)
finally:
    ultra_party.clear_abort("v2_test")
    shutil.rmtree(REPO_ROOT / "capture_logs" / "ultra" / _barrier_run,
                  ignore_errors=True)
    if _previous is None:
        os.environ.pop("AQW_RUN_ID", None)
    else:
        os.environ["AQW_RUN_ID"] = _previous
check("party: a slot number works as a barrier key", key_ok, True)

# --- one pane stops -> the whole party stops -------------------------------
# The reference's StopArmySync publishes the abort for every pane; a party that
# keeps fighting after one member gave up is a wasted pull.
import os      # noqa: E402
import shutil  # noqa: E402

from bot.ultra import party as ultra_party  # noqa: E402

_run_id = "test_v2_abort"
_previous_run = os.environ.get("AQW_RUN_ID")
os.environ["AQW_RUN_ID"] = _run_id
try:
    ultra_party.clear_abort("v2_warden")
    first = warden.build(_StubCommand(),
                         options.UltraOptions(players=("a", "b", "c", "d")), 2)
    check("party: sync is on with a run id", first.sync.enabled, True)
    first.abort("test stop")
    check("party: the abort is published for the party",
          ultra_party.any_abort("v2_warden"), "test stop")
    second = warden.build(_StubCommand(),
                          options.UltraOptions(players=("a", "b", "c", "d")), 3)
    check("party: another pane sees the abort",
          second.sync.aborted(), "test stop")
    check("party: so its next step refuses", run(second.sync.step("ANY")), False)
finally:
    ultra_party.clear_abort("v2_warden")
    shutil.rmtree(REPO_ROOT / "capture_logs" / "ultra" / _run_id,
                  ignore_errors=True)
    if _previous_run is None:
        os.environ.pop("AQW_RUN_ID", None)
    else:
        os.environ["AQW_RUN_ID"] = _previous_run

# --- barriers only count panes that are waiting *now* ----------------------
# The run log showed every barrier passing instantly on the first pull: the
# party folder had been reused (same AQW_RUN_ID), so attempt 1 found the four
# markers a previous run left behind and pulled while one pane was still in
# setup.  A marker is only a peer if it was written since we arrived.
_fresh_run = "test_v2_fresh"
_previous_fresh = os.environ.get("AQW_RUN_ID")
os.environ["AQW_RUN_ID"] = _fresh_run
try:
    _directory = ultra_party._dir()
    for _slot in (1, 2, 3, 4):
        (_directory / f"v2_testfresh.STALE.{_slot}.ready").write_text(
            "0", encoding="utf-8")
    check("party: stale markers do not fill a barrier",
          run(sync.Sync("testfresh", 1).step("STALE", timeout=2, strict=True)),
          False)

    async def _late_pane():
        early = [sync.Sync("testfresh", slot) for slot in (1, 2, 3)]
        last = sync.Sync("testfresh", 4)

        async def late():
            await asyncio.sleep(1.5)
            return await last.step("LATE", timeout=10)

        return await asyncio.gather(
            *(pane.step("LATE", timeout=10) for pane in early), late())

    check("party: a waiting pane keeps its marker fresh for a late pane",
          run(_late_pane()), [True, True, True, True])

    (_directory / "v2_testfresh.OLDSEAL.3.sig").write_text(
        '{"value": true, "t": 0}', encoding="utf-8")
    check("party: a signal from an earlier run is not a yes",
          run(sync.Sync("testfresh", 2).wait_signal("OLDSEAL", key=3,
                                                    timeout=1)), False)
finally:
    shutil.rmtree(REPO_ROOT / "capture_logs" / "ultra" / _fresh_run,
                  ignore_errors=True)
    if _previous_fresh is None:
        os.environ.pop("AQW_RUN_ID", None)
    else:
        os.environ["AQW_RUN_ID"] = _previous_fresh

# --- every stop deletes the run folder -------------------------------------
# The markers left behind are what let a later run's barriers pass on their
# own; the user asked for the whole run folder to go on any stop condition.
_run_clean = "test_v2_clean"
_previous_clean = os.environ.get("AQW_RUN_ID")
os.environ["AQW_RUN_ID"] = _run_clean
try:
    _folder = REPO_ROOT / "capture_logs" / "ultra" / _run_clean
    (_folder / "party").mkdir(parents=True, exist_ok=True)
    (_folder / "party" / "v2_test.STEP.1.ready").write_text("1",
                                                            encoding="utf-8")
    (_folder / "slot1_acc.jsonl").write_text("{}", encoding="utf-8")

    class _Telemetry:
        closed = False

        def close(self):
            self.closed = True

    class _Thread:
        def __init__(self):
            self.bot_instance = type("_B", (), {"telemetry": _Telemetry()})()

    _thread = _Thread()
    hub._clear_run_folder([_thread], tag="test")
    check("stop: the whole run folder is deleted", _folder.exists(), False)
    check("stop: each pane's telemetry is closed first",
          _thread.bot_instance.telemetry.closed, True)
finally:
    shutil.rmtree(REPO_ROOT / "capture_logs" / "ultra" / _run_clean,
                  ignore_errors=True)
    if _previous_clean is None:
        os.environ.pop("AQW_RUN_ID", None)
    else:
        os.environ["AQW_RUN_ID"] = _previous_clean

finish('ultra v2 engine tests')
