"""``CoreAdvanced`` -- the core that re-implements several of ``CoreBots``' names.

Port of ``CoreAdvanced.cs``, and it matters *which* of the two a kit meant: the
reference's cores do not inherit from one another (there is no
``class CoreAdvanced : CoreBots``), so ``Adv.BuyItem`` and ``Core.BuyItem`` are two
separate methods that happen to share a name.  Only the ``CoreAdvanced`` one runs
``GetItemReq``, which farms what a shop entry asks for before the purchase.

Mapping a kit's ``Adv.X`` onto our ``CoreBots`` equivalent is therefore unsound --
that is exactly how Master Ranger's Sandsea requirement went missing -- so
everything a kit calls as ``Adv.`` lives here.

Ported so far:

========================  ==============================================
``buy_item``              ``CoreAdvanced.BuyItem``: the CoreBots purchase
                          plus ``GetItemReq``
``meet_shop_requirements`` ``CoreAdvanced.GetItemReq``: reputation, level, gold
========================  ==============================================

Still reported rather than faked, because the engine has no counterpart:
``SmartEnhance``, ``GearStore``, ``RankUpClass``, ``HasMinimalBoost`` and
``StartBuyAllMerge`` (the merge framework, which also owns ``GetItemReq``'s Gold
Voucher and merge-item steps).
"""
from typing import Optional, Union

from bot.core_bots import load_shop_entry, points_to_level
from bot.core_farms import farm_experience, farm_faction, farm_gold
from core.command import Command

#: ``GetItemReq`` caps its gold farm here (``Math.Min(cost * quant, 100000000)``).
GOLD_FARM_CAP = 100_000_000


async def meet_shop_requirements(cmd: Command, entry, qty: int = 1) -> None:
    """``CoreAdvanced.GetItemReq``: farm what a shop entry needs before buying.

    The reference runs this inside ``_BuyItem``, and it is what makes
    ``Adv.BuyItem`` work at all for an entry behind a faction: reputation first,
    then player level, then gold.  Its Gold Voucher and merge-item steps belong to
    ``StartBuyAllMerge``'s dependency walk, which is not ported.

    A faction this engine has no farm for is reported by ``farm_faction`` rather
    than quietly skipped -- the purchase would fail at the server either way.
    """
    faction = str(getattr(entry, "required_faction", "None") or "None").strip()
    required_rep = int(getattr(entry, "required_rep", 0) or 0)
    if faction and faction.lower() != "none" and required_rep > 0:
        rank = points_to_level(required_rep)
        if rank > cmd.get_faction_rank(faction):
            cmd.bot.log(f"Farming reputation for {faction} "
                        f"(Required: {required_rep})")
            await farm_faction(cmd, faction, rank)

    required_level = int(getattr(entry, "level", 0) or 0)
    if required_level > (cmd.get_player().LEVEL or 0):
        cmd.bot.log(f"Farming experience to reach level {required_level}")
        await farm_experience(cmd, min(required_level, 100))

    cost = int(getattr(entry, "cost", 0) or 0)
    if cost > 0 and not getattr(entry, "is_acs", False):
        await farm_gold(cmd, min(cost * qty, GOLD_FARM_CAP))


async def buy_item(cmd: Command, shop_id: int, item: Union[int, str],
                   qty: int = 1, map_name: Optional[str] = None,
                   shop_item_id: int = 0) -> bool:
    """``CoreAdvanced.BuyItem``: ``CoreBots.BuyItem`` plus ``GetItemReq``.

    Same arguments and the same reporting as :func:`bot.core_bots.buy_item`; the
    difference is that the entry's own requirements are farmed first.  A kit that
    the reference calls ``Adv.BuyItem`` from has to come through here.
    """
    if isinstance(item, int) and await cmd.has_item_id(item):
        return True

    entry = await load_shop_entry(cmd, shop_id, item, map_name, shop_item_id)
    if entry is None:
        return False

    await meet_shop_requirements(cmd, entry, qty)
    await cmd.buy_item(shop_id, entry.item_name, qty,
                       shop_item_id=entry.shop_item_id)
    return True


# ---------------------------------------------------------------------------
# SmartEnhance
# ---------------------------------------------------------------------------

#: ``EnhancementType`` -- the value is the enhancement pattern id.
ENHANCEMENT_TYPES = {
    "Fighter": 2, "Thief": 3, "Hybrid": 5, "Wizard": 6, "Healer": 7,
    "SpellBreaker": 8, "Lucky": 9,
}

#: ``CapeSpecial`` / ``HelmSpecial`` -- pattern ids.
CAPE_SPECIALS = {
    "None": 0, "Forge": 10, "Absolution": 11, "Avarice": 12, "Vainglory": 24,
    "Penitence": 29, "Lament": 30,
}
HELM_SPECIALS = {
    "None": 0, "Forge": 10, "Vim": 25, "Examen": 26, "Anima": 28, "Pneuma": 27,
    "Hearty": 32,
}

#: ``WeaponSpecial`` -- proc ids.
WEAPON_SPECIALS = {
    "None": 0, "Forge": 1, "Spiral_Carve": 2, "Awe_Blast": 3, "Health_Vamp": 4,
    "Mana_Vamp": 5, "Powerword_Die": 6, "Lacerate": 7, "Smite": 8,
    "Valiance": 9, "Arcanas_Concerto": 10, "Acheron": 11, "Elysium": 12,
    "Praxis": 13, "Dauntless": 14, "Ravenous": 15,
}

#: ``uXxx()`` -> (quests that must be completed, faction ranks that must hold).
UNLOCKS = {
    "Awe": ((2937,), ()),
    "ForgeWeapon": ((8738,), ()),
    "Lacerate": ((8739,), ()),
    "Smite": ((8740,), ()),
    "Valiance": ((8741,), ()),
    "ArcanasConcerto": ((8742,), ()),
    "Absolution": ((8743,), ()),
    "Vainglory": ((8744,), ()),
    "Avarice": ((8745,), ()),
    "ForgeCape": ((8758,), ()),
    "Acheron": ((8820,), ()),
    "Elysium": ((8821,), ()),
    "Penitence": ((8822,), ()),
    "Lament": ((8823,), ()),
    "Vim": ((8824,), ()),
    "Examen": ((8825,), ()),
    "Anima": ((8826,), ()),
    "Pneuma": ((8827,), ()),
    "ForgeHelm": ((8828,), ()),
    "Praxis": ((9171,), ()),
    "Dauntless": ((9172,), ()),
    "Hearty": ((9466,), (("Grimskull Trolling", 7),)),
    "Ravenous": ((9560,), ()),
}

#: EnhancementType -> (shop at level 50+, shop below it).
BODY_SHOPS = {
    "Fighter": (768, 141), "Thief": (767, 142), "Hybrid": (766, 143),
    "Wizard": (765, 144), "Healer": (762, 145), "SpellBreaker": (764, 146),
    "Lucky": (763, 147),
}

#: Weapon specials 1..6 -> the shop their enhancement is bought from, by type.
SPECIAL_WEAPON_SHOPS = {
    "Fighter": 635, "Thief": 637, "Hybrid": 633, "Wizard": 636,
    "SpellBreaker": 636, "Healer": 638, "Lucky": 639,
}

CAPE_SHOP = 2143
HELM_SHOP = 2164
FORGE_SHOP = 2142
FORGE_MAP = "forge"

CAPE_UNLOCK = {"Forge": "ForgeCape", "Absolution": "Absolution",
               "Avarice": "Avarice", "Vainglory": "Vainglory",
               "Penitence": "Penitence", "Lament": "Lament"}
HELM_UNLOCK = {"Vim": "Vim", "Examen": "Examen", "Forge": "ForgeHelm",
               "Anima": "Anima", "Pneuma": "Pneuma", "Hearty": "Hearty"}
WEAPON_UNLOCK = {"Forge": "ForgeWeapon", "Lacerate": "Lacerate",
                 "Smite": "Smite", "Valiance": "Valiance",
                 "Arcanas_Concerto": "ArcanasConcerto", "Elysium": "Elysium",
                 "Acheron": "Acheron", "Praxis": "Praxis",
                 "Dauntless": "Dauntless", "Ravenous": "Ravenous"}

#: The slots the reference's ``EnhanceableCatagories`` covers, as our sES codes.
ENHANCEABLE_SLOTS = ("Weapon", "he", "ba", "ar", "co")

#: Run-scoped memo of ``uXxx`` results, cleared by :func:`reset_unlock_cache`.
_unlock_cache: dict = {}


def reset_unlock_cache() -> None:
    """Drop the memoised unlock results (the reference re-reads them per call)."""
    _unlock_cache.clear()


async def enhancement_unlocked(cmd: Command, name: str) -> bool:
    """``CoreAdvanced.uXxx()``: is that enhancement unlocked on this account?

    Args:
        cmd (Command): Facade to act through.
        name (str): Flag name from :data:`UNLOCKS`, e.g. ``"Valiance"``.
    """
    if name in _unlock_cache:
        return _unlock_cache[name]

    quests, factions = UNLOCKS[name]
    unlocked = True
    for quest in quests:
        if not await cmd.is_completed_before(quest):
            unlocked = False
            break
    if unlocked:
        for faction, rank in factions:
            if cmd.get_faction_rank(faction) < rank:
                unlocked = False
                break
    _unlock_cache[name] = unlocked
    return unlocked


def _constant_names(*values) -> tuple:
    """String constants the table's lambdas read, e.g. ``unlocked["Valiance"]``."""
    names = set()
    for value in values:
        code = getattr(value, "__code__", None)
        if code is not None:
            names.update(c for c in code.co_consts if isinstance(c, str))
    return tuple(sorted(names))


def _current_special(cmd: Command, slot: str) -> str:
    """``CurrentCapeSpecial``/``CurrentHelmSpecial``/``CurrentWeaponSpecial``."""
    item = None
    for candidate in cmd.bot.player.INVENTORY:
        if candidate.s_es == slot and candidate.is_equipped:
            item = candidate
            break
    if item is None:
        return "None"
    if slot == "Weapon":
        for name, proc in WEAPON_SPECIALS.items():
            if proc == item.item_proc_id:
                return name
        return "None"
    table = CAPE_SPECIALS if slot == "ba" else HELM_SPECIALS
    for name, pattern in table.items():
        if pattern == item.enh_pattern_id:
            return name
    return "None"


async def _resolve_flags(cmd: Command, names) -> dict:
    """Evaluate the flags one table entry needs, as its lambdas expect them."""
    flags = {}
    for name in names:
        if name.startswith("__quest:"):
            flags[name] = await cmd.is_completed_before(int(name.split(":")[1]))
        elif name.startswith("__cur:"):
            flags[name] = _current_special(cmd, name.split(":", 1)[1])
        else:
            flags[name] = await enhancement_unlocked(cmd, name)
    return flags


def _value(value, flags):
    """A table value: the string itself, or its lambda's result."""
    return value(flags) if callable(value) else value


async def library_plan(cmd: Command, class_name: str):
    """The ``Plan`` for a class: the Forge table, else the Awe table.

    Args:
        cmd (Command): Facade to act through.
        class_name (str): Class name, as the tables spell it (lower-case).

    Returns:
        Plan | None: None when neither table covers the class, which is the
        reference's ``type == null`` case.
    """
    lowered = class_name.strip().lower()
    for library in (forge_library(), awe_library()):
        for plan in library:
            if lowered not in plan.classes:
                continue
            if plan.condition == "False":
                continue
            flags = await _resolve_flags(
                cmd, _constant_names(plan.condition, plan.type, plan.cape,
                                     plan.helm, plan.weapon))
            if plan.condition is not None and plan.condition in ("False",):
                continue
            if callable(plan.condition) and plan.condition(flags):
                continue
            if plan.requires and not all(flags.get(name) for name in plan.requires):
                continue
            return plan
    return None


def forge_library():
    from bot.core_advanced_tables import FORGE_LIBRARY
    return FORGE_LIBRARY


def awe_library():
    from bot.core_advanced_tables import AWE_LIBRARY
    return AWE_LIBRARY


async def smart_enhance(cmd: Command, class_name: str,
                        force_enh: bool = False,
                        weapon_override: str = None) -> None:
    """``CoreAdvanced.SmartEnhance``: pick and apply a class's enhancement.

    The reference gates this on the CBO flag ``DisableAutoEnhance``; CBO is not
    ported, and that flag defaults to off, so the gate is not reproduced.

    Args:
        cmd (Command): Facade to act through.
        class_name (str): Class to enhance, and whose gear is enhanced with it.
        force_enh (bool): Also enhance a class that arrives unenhanced, then stop
            (the reference's ``ForceEnh`` for quest-reward classes).
        weapon_override (str): Weapon special to use instead of the table's pick.
    """
    if not class_name:
        cmd.bot.log("[advanced] SmartEnhance: className is null")
        return
    if not cmd.is_in_inventory(class_name):
        cmd.bot.log(f"[advanced] SmartEnhance Failed: Class {class_name} was not "
                    f"found in inventory")
        return

    lowered = class_name.strip().lower()
    selected = None
    for candidate in cmd.bot.player.INVENTORY:
        if (candidate.s_name.strip().lower() == lowered
                and candidate.s_es == "ar"):
            selected = candidate
            break
    if selected is None:
        cmd.bot.log(f"[advanced] SmartEnhance Failed: Class {class_name} was not "
                    f"found in inventory")
        return

    plan = await library_plan(cmd, lowered)
    if plan is None:
        cmd.bot.log(f"[advanced] SmartEnhance Failed: 'type' for {lowered} is NULL")
        return

    flags = await _resolve_flags(cmd, _constant_names(
        plan.type, plan.cape, plan.helm, plan.weapon))
    type_ = _value(plan.type, flags)
    cape = _value(plan.cape, flags) or "None"
    helm = _value(plan.helm, flags) or "None"
    weapon = _value(plan.weapon, flags) or "None"

    if selected.enh_level <= 0:
        await enhance_item(cmd, selected.s_name, type_, cape, helm, weapon)
        if force_enh:
            return

    await cmd.equip_item(selected.s_name)
    if weapon_override:
        weapon = weapon_override
    await enhance_equipped(cmd, type_, cape, helm, weapon)


async def enhance_item(cmd: Command, item: str, type_: str, cape: str = "None",
                       helm: str = "None", weapon: str = "None") -> None:
    """``CoreAdvanced.EnhanceItem``: enhance one item.

    Args:
        cmd (Command): Facade to act through.
        item (str): Name of the item to enhance.
        type_ (str): ``EnhancementType`` name for the body slot.
        cape (str): ``CapeSpecial`` name, or ``"None"``.
        helm (str): ``HelmSpecial`` name, or ``"None"``.
        weapon (str): ``WeaponSpecial`` name, or ``"None"``.
    """
    if not item or not await cmd.has_item(item):
        cmd.bot.log(f'[advanced] Enhancement Failed: Could not find "{item}"')
        return

    selected = None
    for candidate in cmd.bot.player.INVENTORY:
        if (candidate.s_name.strip().lower() == item.strip().lower()
                and candidate.s_es in ENHANCEABLE_SLOTS):
            selected = candidate
            break
    if selected is None:
        cmd.bot.log(f"[advanced] Enhancement Failed: {item} cannot be enhanced")
        return
    await auto_enhance(cmd, [selected], type_, cape, helm, weapon)


async def enhance_equipped(cmd: Command, type_: str, cape: str = "None",
                           helm: str = "None", weapon: str = "None") -> None:
    """``CoreAdvanced.EnhanceEquipped``: enhance every equipped, enhanceable item.

    Args:
        cmd (Command): Facade to act through.
        type_ (str): ``EnhancementType`` name for the body slot.
        cape (str): ``CapeSpecial`` name, or ``"None"``.
        helm (str): ``HelmSpecial`` name, or ``"None"``.
        weapon (str): ``WeaponSpecial`` name, or ``"None"``.
    """
    equipped = [item for item in cmd.bot.player.INVENTORY
                if item.is_equipped and item.s_es in ENHANCEABLE_SLOTS]
    await auto_enhance(cmd, equipped, type_, cape, helm, weapon)


def already_has_requested(item, player_level: int, type_: str, cape: str,
                          helm: str, weapon: str) -> bool:
    """``CoreAdvanced.AlreadyHasRequestedEnhancement`` for one item."""
    if item is None or item.enh_level <= 0 \
            or item.enh_level != player_level:
        return False

    if item.s_es == "ba":
        wanted = CAPE_SPECIALS.get(cape, 0) if cape != "None" \
            else ENHANCEMENT_TYPES.get(type_, 0)
        return wanted == item.enh_pattern_id
    if item.s_es == "he":
        wanted = HELM_SPECIALS.get(helm, 0) if helm != "None" \
            else ENHANCEMENT_TYPES.get(type_, 0)
        return wanted == item.enh_pattern_id
    if item.s_es == "Weapon":
        if weapon == "None":
            return ENHANCEMENT_TYPES.get(type_, 0) == item.enh_pattern_id
        return _weapon_already_has(item, type_, weapon)
    if item.s_es == "ar":
        return ENHANCEMENT_TYPES.get(type_, 0) == item.enh_pattern_id
    return False


def _weapon_already_has(item, type_: str, weapon: str) -> bool:
    """``CoreAdvanced.WeaponAlreadyHasRequestedEnhancement``."""
    if item is None or item.s_es != "Weapon" or item.enh_level <= 0:
        return False

    pattern = item.enh_pattern_id
    proc = item.item_proc_id
    special = WEAPON_SPECIALS.get(weapon, 0)

    if weapon == "None":
        return pattern == ENHANCEMENT_TYPES.get(type_, 0)
    if 0 < special <= 6:
        return pattern == ENHANCEMENT_TYPES.get(type_, 0) and proc == special
    if weapon == "Forge":
        return proc == 0 and pattern in (ENHANCEMENT_TYPES.get(type_, 0), 10)
    return proc == special


async def _best_enhancement(cmd: Command, item, shop_id: int):
    """The shop entry ``_AutoEnhance`` would pick for ``item``, or None."""
    from bot.core_bots import load_shop_entry  # noqa: F401  (kept for parity)

    await cmd.ensure_load_shop(shop_id)
    shop = None
    for loaded in cmd.bot.loaded_shop_datas:
        if str(loaded.shop_id) == str(shop_id):
            shop = loaded
            break
    if shop is None:
        return None

    level = cmd.get_player().LEVEL or 0
    available = []
    for entry in shop.items:
        if (not cmd.get_player().is_member and entry.is_upgrade)                 or entry.level > level:
            continue
        available.append(entry)
    if not available:
        return None
    if len(available) == 1:
        return available[0]
    ordered = sorted(available,
                     key=lambda e: (e.level, 1 if e.is_upgrade else 0),
                     reverse=True)
    return ordered[0]


async def _auto_enhance(cmd: Command, item, shop_id: int,
                        map_name: str = None) -> None:
    """``CoreAdvanced._AutoEnhance``: search a shop and send the one packet."""
    if map_name and cmd.is_not_in_map(map_name):
        await cmd.join_map(map_name)

    best = await _best_enhancement(cmd, item, shop_id)
    if best is None:
        return
    if (best.item_id == item.enh_id and item.enh_level > 0
            and best.level == item.enh_level):
        return
    await cmd.enhance_item(int(item.item_id), int(best.item_id), shop_id)


async def auto_enhance(cmd: Command, items, type_: str, cape: str = "None",
                       helm: str = "None", weapon: str = "None") -> None:
    """``CoreAdvanced.AutoEnhance``: enhance a list of items.

    Args:
        cmd (Command): Facade to act through.
        items: Inventory items to enhance (already filtered to enhanceable ones).
        type_ (str): ``EnhancementType`` name for the body slot.
        cape (str): ``CapeSpecial`` name, or ``"None"``.
        helm (str): ``HelmSpecial`` name, or ``"None"``.
        weapon (str): ``WeaponSpecial`` name, or ``"None"``.
    """
    if not type_ or not items:
        return

    level = cmd.get_player().LEVEL or 0
    remaining = list(items)
    cape_item = helm_item = weapon_item = None

    if cape != "None":
        cape_item = next((i for i in remaining if i.s_es == "ba"), None)
        if cape_item is not None:
            remaining.remove(cape_item)
    if helm != "None":
        helm_item = next((i for i in remaining if i.s_es == "he"), None)
        if helm_item is not None:
            remaining.remove(helm_item)
    if weapon != "None":
        weapon_item = next((i for i in remaining if i.s_es == "Weapon"), None)
        if weapon_item is not None:
            remaining.remove(weapon_item)

    if cape_item is not None:
        flag = CAPE_UNLOCK.get(cape)
        if flag is None:
            cmd.bot.log(f'[advanced] Enhancement Failed:\tInvalid "CapeSpecial" '
                        f'given, received {cape}')
            return
        if await enhancement_unlocked(cmd, flag):
            if not already_has_requested(cape_item, level, type_, cape, helm,
                                         weapon):
                await _auto_enhance(cmd, cape_item, CAPE_SHOP, FORGE_MAP)
        else:
            cmd.bot.log(f"[advanced] Enhancement Failed:\tYou did not unlock the "
                        f"{cape} Enhancement yet")

    if helm_item is not None:
        flag = HELM_UNLOCK.get(helm)
        if flag is None:
            cmd.bot.log(f'[advanced] Enhancement Failed:\tInvalid "HelmSpecial" '
                        f'given, received {helm}')
            return
        if await enhancement_unlocked(cmd, flag):
            if not already_has_requested(helm_item, level, type_, cape, helm,
                                         weapon):
                await _auto_enhance(cmd, helm_item, HELM_SHOP,
                                    FORGE_MAP if HELM_SPECIALS.get(helm, 0)
                                    else None)
        else:
            cmd.bot.log(f"[advanced] Enhancement Failed:\tYou did not unlock the "
                        f"{helm} Enhancement yet")

    if weapon_item is not None:
        special = WEAPON_SPECIALS.get(weapon, 0)
        can = True
        if 0 < special <= 6:
            shop_id = SPECIAL_WEAPON_SHOPS.get(type_, 0)
        else:
            shop_id = FORGE_SHOP
            flag = WEAPON_UNLOCK.get(weapon)
            if flag and not await enhancement_unlocked(cmd, flag):
                can = False
        if can and shop_id and not already_has_requested(
                weapon_item, level, type_, cape, helm, weapon):
            await _auto_enhance(cmd, weapon_item, shop_id,
                                FORGE_MAP if special > 6 else None)

    if remaining:
        shop_id = BODY_SHOPS.get(type_, (0, 0))
        chosen = shop_id[0] if level >= 50 else shop_id[1]
        if not chosen:
            cmd.bot.log(f"[advanced] Enhancement Failed: Invalid EnhancementType "
                        f"given, received {type_}")
            return
        for item in remaining:
            if already_has_requested(item, level, type_, cape, helm, weapon):
                continue
            await _auto_enhance(cmd, item, chosen)
