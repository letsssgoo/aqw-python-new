"""Enhancements for Ultra V2: wear what we own, otherwise buy it.

Two halves, both from the reference's ``PrepareEnhancements``:

1. **equip** -- :meth:`Command.equip_enhancement` finds whichever inventory item
   carries the named enhancement (inventory first, then bank).  This is the
   engine's existing path and is used unchanged;
2. **buy** -- when the account owns nothing carrying it, the enhancement is
   bought from the forge shop the enhancement registry records
   (``model.enhancement.find``), then equipped.  The weapon tries the preset's
   ``weapon_fallbacks`` in order, exactly like ``WeaponEnhancementFallbacks``.

A class/base enhancement has no shop entry when the account never captured that
shop, and a priced entry needs gold on hand: both are reported by name and stop
the run instead of fighting in the wrong gear.
"""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from bot.ultra.v2.presets import Preset

#: Preset field -> the equipment slot it is pinned to.
SLOTS: Tuple[Tuple[str, str], ...] = (
    ("base", "class"),
    ("cape", "cape"),
    ("helm", "helm"),
    ("weapon", "weapon"),
)

#: How long to wait for a bought enhancement to land in the inventory.
PURCHASE_WAIT_MS = 10_000

#: ``GetNormalEnhancementShop`` from the reference: a base (class-slot)
#: enhancement is named by its **type**, and applied from a fixed shop -- 765 is
#: Wizard at level 50+, 144 below it.  Our registry only knows shop item names
#: ("Lucky Armor Enhancement"), so "Wizard" never resolves there; this table is
#: how the reference resolves it.
NORMAL_ENHANCEMENT_SHOPS = {
    "Fighter": (768, 141),
    "Thief": (767, 142),
    "Hybrid": (766, 143),
    "Wizard": (765, 144),
    "Healer": (762, 145),
    "SpellBreaker": (764, 146),
    "Lucky": (763, 147),
}

#: ``sES`` codes of the class/armor slot an enhancement of this kind fits.
CLASS_SLOTS = ("ar", "co")

#: Where the normal (non-forge) enhancement shops are reachable from.
ENHANCEMENT_MAP = "battleontown"


async def prepare(cmd, preset: Preset) -> bool:
    """Wear every enhancement the preset names, buying a missing one."""
    for attribute, slot in SLOTS:
        wanted: Optional[str] = getattr(preset, attribute)
        if not wanted:
            if attribute != "helm":
                continue
            # No helm enhancement in the preset means "use the class's own
            # base type" (Lord of Order is the case in Tyndarius): the helm
            # takes "<Base> Helm Enhancement", not nothing.
            wanted = f"{preset.base} Helm Enhancement"
            if not best_entry(wanted, "helm"):
                continue
        candidates: Sequence[str] = (wanted,)
        if attribute == "weapon":
            candidates = (wanted, *preset.weapon_fallbacks)
        if not await _apply_one(cmd, slot, candidates):
            cmd.bot.log(f"[v2] no {slot} enhancement {wanted!r} is owned or "
                        f"buyable"
                        + (f" (fallbacks tried: "
                           f"{', '.join(preset.weapon_fallbacks)})"
                           if attribute == "weapon" and preset.weapon_fallbacks
                           else "")
                        + "; the run stops rather than fighting in the wrong "
                          "gear.")
            return False
    return True


async def _apply_one(cmd, slot: str, candidates: Sequence[str]) -> bool:
    """Wear one of ``candidates`` in ``slot``.

    The **class** slot is its own path (the user's rule, and Skua's): equip the
    class, look at the enhancement it carries, and enhance only when it differs.
    Nothing here asks the generic ``equip_enhancement`` by the base *type* name
    (``"Lucky"``) -- that name is not a registry item, so it only ever produced
    "no enhancement named 'Lucky'".

    Weapon, cape and helm keep the existing route: equip an item that already
    carries the enhancement, else apply it to the equipped piece, else buy it.
    """
    if slot == "class":
        for candidate in candidates:
            if await _apply_base(cmd, candidate):
                return True
        return False

    for candidate in candidates:
        if await cmd.equip_enhancement(candidate, slot=slot):
            cmd.bot.log(f"[v2] {slot} enhancement: {candidate}.")
            return True

    for candidate in candidates:
        if await cmd.equip_enhancement(candidate, slot=slot,
                                       enhance_if_missing=True):
            verified = bool(getattr(cmd, "last_enhancement_verified", False))
            cmd.bot.log(f"[v2] {slot} enhancement: {candidate} "
                        f"({'applied' if verified else 'sent, not verified'}).")
            return True

    for candidate in candidates:
        entry = best_entry(candidate, slot,
                           is_member=bool(getattr(cmd.bot.player,
                                                  "is_member", False)))
        if entry is None:
            continue
        cmd.bot.log(f"[v2] {slot} enhancement {candidate!r} is neither owned nor "
                    f"appliable; buying it from shop {entry.shop_id}.")
        if not await _buy(cmd, entry):
            continue
        if await cmd.equip_enhancement(candidate, slot=slot):
            cmd.bot.log(f"[v2] {slot} enhancement: {candidate} (bought).")
            return True
    return False


async def _apply_base(cmd, name: str) -> bool:
    """Class-slot enhancement: equip the class, compare, enhance only if different.

    The reference names this enhancement by *type* ("Wizard"); the shop item is
    called "Wizard Armor Enhancement", which is what the registry now carries
    for the class slot.  So:

    1. find the equipped class;
    2. resolve the wanted tier at or below the class's level;
    3. if the class already carries it, do nothing -- re-enhancing identical
       gear is a wasted packet;
    4. otherwise load the type's shop (``GetNormalEnhancementShop``) and socket
       it with ``enhanceItemShop``.
    """
    worn = next((item for item in cmd.bot.player.INVENTORY
                 if getattr(item, "is_equipped", False)
                 and str(getattr(item, "s_es", "")).lower() in CLASS_SLOTS),
                None)
    if worn is None:
        cmd.bot.log(f"[v2] nothing is equipped in the class slot, so {name} "
                    f"cannot be applied.")
        return False

    level = int(getattr(cmd.bot.player, "LEVEL", 0) or 0)
    is_member = bool(getattr(cmd.bot.player, "is_member", False))
    record = best_base(name, level, is_member)
    if record is None:
        # ``basic_enhancement.jsonl`` may ship without class-slot rows (the
        # stock file does); the shop is the reference's own source.
        record = await _base_from_shop(cmd, name, level, is_member)
    if record is None:
        cmd.bot.log(f"[v2] no class enhancement for {name!r} is registered "
                    f"or sold by its shop.")
        return False

    if _carries(worn, record):
        cmd.bot.log(f"[v2] class enhancement already {record.name} "
                    f"(item {worn.item_id}); nothing to change.")
        return True

    shop_id = record.shop_id or _shop_id_for(name)
    if not shop_id:
        return False
    # ``Lvl 50+ <Type> Enh`` is sold in battleontown (``Location:
    # Menu,battleontown,trainers``); asking for it from the ultra map returns
    # nothing, which is why the class stayed on its old enhancement.
    if cmd.is_not_in_map(ENHANCEMENT_MAP):
        await cmd.join_map(ENHANCEMENT_MAP)
    if not await cmd.ensure_load_shop(shop_id):
        cmd.bot.log(f"[v2] class enhancement shop {shop_id} did not load "
                    f"({name}).")
        return False
    await cmd.enhance_item(worn.item_id, record.item_id, shop_id)
    cmd.bot.log(f"[v2] class enhancement: {record.name} "
                f"(lvl {record.level}, shop {shop_id}).")
    return True


def best_base(name: str, level: int = 0, is_member: bool = False):
    """The class-slot record for a type name ("Wizard"), at or under ``level``.

    ``level`` is the **character** level: enhancement tiers are gated by it, not
    by the class item's own level (a class item reports level 1, and using that
    picked the worst tier).  Each tier also ships in two flavours -- the
    ``bUpg`` (member/LEGEND) one and the regular one -- so a non-member account
    only ever sees the regular entries; handing it the member tier is a packet
    the server refuses.
    """
    from model import enhancement as registry
    for candidate in (f"{name} Armor Enhancement", name):
        try:
            rows = registry.find(candidate, "class")
        except (KeyError, ValueError):
            rows = []
        rows = [row for row in rows if is_member or not row.is_upgrade]
        if not rows:
            continue
        fit = [row for row in rows if not level or row.level <= level]
        # Fallback is the highest tier the account can actually take (the
        # reference's behaviour), never one above its level.
        return max(fit or rows, key=lambda row: (row.level, row.rarity))
    return None


class _ShopBase:
    """A class enhancement read off the normal enhancement shop itself.

    The registry comes from ``basic_enhancement.jsonl``; a deployment that ships
    the stock file has no class-slot rows in it, and then every class-slot
    enhancement looked "unregistered".  The reference never needs that file: it
    loads ``GetNormalEnhancementShop`` and reads the shop's own items.
    """

    def __init__(self, name: str, item_id: int, pattern_id: int, rarity: int,
                 level: int, shop_id: int):
        self.name = name
        self.item_id = int(item_id)
        self.pattern_id = int(pattern_id)
        self.rarity = int(rarity)
        self.level = int(level)
        self.shop_id = int(shop_id)


async def _base_from_shop(cmd, name: str, level: int, is_member: bool):
    """The class enhancement the shop sells at or under ``level``."""
    shops = NORMAL_ENHANCEMENT_SHOPS.get(name)
    if not shops:
        return None
    high, low = shops
    order = [high if level >= 50 else low, low, high]
    seen = []
    for shop_id in order:
        if shop_id in seen:
            continue
        seen.append(shop_id)
        if cmd.is_not_in_map(ENHANCEMENT_MAP):
            await cmd.join_map(ENHANCEMENT_MAP)
        if not await cmd.ensure_load_shop(shop_id):
            continue
        wanted = f"{name} Armor Enhancement".lower()
        found = None
        for shop in getattr(cmd.bot, "loaded_shop_datas", []) or []:
            if str(getattr(shop, "shop_id", "")) != str(shop_id):
                continue
            for item in getattr(shop, "items", []) or []:
                if str(getattr(item, "s_name", "")).lower() != wanted:
                    continue
                if int(getattr(item, "level", 0) or 0) > level:
                    continue
                if getattr(item, "is_upgrade", False) and not is_member:
                    continue
                if found is None or item.level > found.level:
                    found = item
        if found is not None:
            return _ShopBase(found.s_name, found.item_id,
                             getattr(found, "enh_pattern_id", 0),
                             getattr(found, "rarity", 0), found.level, shop_id)
    return None


def _carries(item, record) -> bool:
    """True when ``item`` already has ``record`` socketed.

    The item's ``EnhID`` is authoritative; the pattern+rarity pair is only a
    fallback for a client that omits ``EnhID``.  Comparing patterns alone is
    wrong: Wizard and Fighter are both class enhancements, and a stale item can
    report one while wearing the other.
    """
    item_enh = int(getattr(item, "enh_id", 0) or 0)
    if item_enh:
        return item_enh == int(record.item_id)
    return (int(getattr(item, "enh_pattern_id", 0) or 0) == int(record.pattern_id)
            and int(getattr(item, "enh_rarity", 0) or 0) == int(record.rarity))


def _shop_id_for(name: str) -> int:
    shops = NORMAL_ENHANCEMENT_SHOPS.get(name)
    if shops is None:
        return 0
    return shops[0]


def best_entry(name: str, slot: str, is_member: Optional[bool] = None):
    """The registry record to buy for ``name`` in ``slot``, or ``None``.

    A *basic* enhancement is one name at every level 51-100, so the highest
    tier is the right purchase; a forge enhancement has exactly one.
    ``is_member=False`` skips the ``bUpg`` (member/LEGEND) tiers, which the
    server refuses to apply on a free account.
    """
    from model import enhancement as registry
    try:
        records: List = registry.find(name, slot)
    except (KeyError, ValueError):
        return None
    if not records:
        return None
    if is_member is False:
        regular = [record for record in records if not record.is_upgrade]
        if regular:
            records = regular
    return max(records, key=lambda record: (record.level, record.rarity))


#: Awe shops sell the same weapon specials per armour family.  The captured
#: shops carry the family in ``PatternID``: Lucky = 639/pattern 9, Wizard =
#: 636/pattern 6, Fighter = 635/pattern 2.  That is what makes "the Health Vamp
#: that matches Lucky armour" different from the Wizard/Fighter one.
AWE_SHOP_BY_BASE = {"Lucky": 639, "Wizard": 636, "Fighter": 635}
AWE_PATTERN_BY_BASE = {"Lucky": 9, "Wizard": 6, "Fighter": 2}


def awe_variant(name: str, base: str, level: int = 0):
    """The ``name`` weapon special sold for ``base``'s armour family."""
    from model import enhancement as registry
    try:
        rows: List = registry.find(name, "weapon")
    except (KeyError, ValueError):
        return None
    pattern = AWE_PATTERN_BY_BASE.get(base)
    if pattern:
        rows = [row for row in rows if row.pattern_id == pattern] or rows
    if not rows:
        return None
    fit = [row for row in rows if not level or row.level <= level]
    return max(fit or rows, key=lambda row: (row.level, row.rarity))


async def _buy(cmd, entry) -> bool:
    """Buy one enhancement entry and wait for it to arrive.

    Forge enhancements are sold from the **forge map**, exactly as
    ``equip_enhancement(enhance_if_missing=True)`` does: the server serves the
    shop only there, so the map is joined before the load.
    """
    if not entry.shop_id:
        cmd.bot.log(f"[v2] {entry.name!r} has no shop recorded, so it cannot "
                    f"be bought automatically.")
        return False
    if entry.cost and cmd.bot.player.GOLD < entry.cost:
        cmd.bot.log(f"[v2] {entry.name!r} costs {entry.cost} gold; the account "
                    f"has {cmd.bot.player.GOLD}. Not farming gold for gear.")
        return False

    if getattr(entry, "source", "") == "forge":
        from bot import core_advanced as adv
        if cmd.is_not_in_map(adv.FORGE_MAP):
            await cmd.join_map(adv.FORGE_MAP)
    elif cmd.is_not_in_map(ENHANCEMENT_MAP):
        await cmd.join_map(ENHANCEMENT_MAP)

    if not await cmd.ensure_load_shop(entry.shop_id):
        cmd.bot.log(f"[v2] shop {entry.shop_id} did not load; {entry.name!r} "
                    f"was not bought.")
        return False

    from bot.core_advanced import buy_item as adv_buy
    if await adv_buy(cmd, entry.shop_id, entry.item_id, 1):
        return True
    cmd.bot.log(f"[v2] {entry.name!r} did not arrive after the buy (shop "
                f"{entry.shop_id}); the server refused it.")
    return False


def describe(preset: Preset) -> str:
    """One line for the log: what the preset wants to wear."""
    bits = [f"base {preset.base}"]
    if preset.cape:
        bits.append(f"cape {preset.cape}")
    if preset.helm:
        bits.append(f"helm {preset.helm}")
    if preset.weapon:
        weapon = preset.weapon
        if isinstance(weapon, int):
            from model import enhancement as registry
            record = registry.get(weapon)
            weapon = record.name if record else weapon
        fallbacks = f" (then {', '.join(preset.weapon_fallbacks)})" \
            if preset.weapon_fallbacks else ""
        bits.append(f"weapon {weapon}{fallbacks}")
    return " / ".join(bits)
