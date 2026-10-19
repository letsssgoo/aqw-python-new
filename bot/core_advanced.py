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
# BuyAllMerge
# ---------------------------------------------------------------------------

#: ``CoreAdvanced.miscCatagories`` -- shop categories never worth merging.
#: This engine's item model carries no category field, so the filter is not
#: applied; it is recorded here for the day it does.
MISC_CATEGORIES = ("Note", "Item", "QuestItem", "ServerUse")

#: ``ProcessItemWithDependencies``' own recursion cap.
MAX_MERGE_DEPTH = 15


def _held_by_id(cmd: Command, item_id) -> int:
    """How many of an item id the account holds, temp bag included."""
    player = cmd.bot.player
    total = 0
    for getter in (player.get_item_inventory_by_id,
                   player.get_item_temp_inventory_by_id):
        found = getter(item_id)
        if found is not None:
            total += int(getattr(found, "qty", 0) or 0)
    return total


async def _open_shop(cmd: Command, map_name: str, shop_id: int) -> bool:
    """Stand in the shop's map and load it -- ``EnsureShopLoaded``."""
    if map_name and cmd.is_not_in_map(map_name):
        await cmd.join_map(map_name)
    return await cmd.ensure_load_shop(shop_id)


def _merge_shop(cmd: Command, shop_id: int):
    """The loaded shop, or None -- the same lookup ``BuyItem`` uses."""
    return _find_shop(cmd, shop_id)


def _merge_entry(shop, item_id):
    """The shop entry whose ItemID is ``item_id``, or None."""
    if shop is None:
        return None
    for entry in shop.items:
        if str(entry.item_id) == str(item_id):
            return entry
    return None


async def _merge_requirements(cmd: Command, entry):
    """``(item_id, name, qty)`` rows of an entry's merge recipe."""
    return [(iid, name, qty) for iid, name, qty in entry.merge_requirements]


async def start_buy_all_merge(cmd: Command, map_name: str, shop_id: int,
                              find_ingredients=None, buy_only_this: str = None,
                              item_blacklist=(), shop_item_id: int = 0) -> None:
    """``CoreAdvanced.StartBuyAllMerge``: merge everything a shop offers.

    The recipe comes from each entry's own payload (``turnin``, see
    :mod:`model.inventory`), so nothing is hard-coded per item: for every
    requirement the shop itself sells it is bought or recursed into, and
    anything else is handed to ``find_ingredients`` -- the merge script's own
    farmer, which is what the reference reaches through its ``externalItem``
    fields.  This port passes them as arguments instead.

    Args:
        cmd (Command): Facade to act through.
        map_name (str): Map the shop lives in.
        shop_id (int): Shop to empty.
        find_ingredients (Callable | None): ``async (item_id, qty) -> None``,
            the merge script's own farmer for items the shop does not sell.
        buy_only_this (str | None): The reference's ``buyOnlyThis``.
        item_blacklist (Sequence[str]): Names to skip.
        shop_item_id (int): Which entry to take when a name repeats.
    """
    await _open_shop(cmd, map_name, shop_id)
    shop = _merge_shop(cmd, shop_id)
    if shop is None:
        cmd.bot.log(f"[merge] shop {shop_id} never loaded; nothing merged.")
        return

    blocked = {name.lower() for name in item_blacklist}
    seen = set()
    for entry in shop.items:
        name = entry.item_name
        if not name or name in seen:
            continue
        seen.add(name)
        if name.lower().endswith("insignia") or name.lower() in blocked:
            continue
        if buy_only_this and name.lower() != buy_only_this.lower():
            continue
        if entry.is_upgrade and not cmd.get_player().is_member:
            cmd.bot.log(f'[merge] skipping "{name}" (member only).')
            continue
        if _held_by_id(cmd, entry.item_id) >= 1:
            cmd.bot.log(f'[merge] "{name}" is already owned.')
            continue
        cmd.bot.log(f'[merge] farming for "{name}"')
        await _merge_item(cmd, map_name, shop_id, entry, 1, find_ingredients, 0)
        await _open_shop(cmd, map_name, shop_id)
        missing = [f"{n} x{q}" for iid, n, q in entry.merge_requirements
                   if _held_by_id(cmd, iid) < q]
        if not missing:
            await cmd.buy_item(shop_id, name, 1,
                               shop_item_id=entry.shop_item_id)
        elif missing:
            cmd.bot.log(f'[merge] "{name}" not bought yet, missing: '
                        f'{", ".join(missing)}')


async def _merge_item(cmd: Command, map_name: str, shop_id: int, entry,
                      qty: int, find_ingredients, depth: int) -> None:
    """``ProcessItemWithDependencies``: satisfy one entry, then buy it."""
    if depth > MAX_MERGE_DEPTH:
        cmd.bot.log(f"[merge] recursion cap reached at "
                    f'"{entry.item_name}"; stopping this branch.')
        return
    if _held_by_id(cmd, entry.item_id) >= qty:
        return

    await _open_shop(cmd, map_name, shop_id)
    shop = _merge_shop(cmd, shop_id)

    for item_id, name, need in entry.merge_requirements:
        need = need * qty
        if _held_by_id(cmd, item_id) >= need:
            cmd.bot.log(f'[merge] {name} owned x{need}')
            continue

        in_shop = _merge_entry(shop, item_id)
        if in_shop is not None:
            need = min(need, int(in_shop.stackable or need))
            if not in_shop.merge_requirements:
                if in_shop.is_upgrade and not cmd.get_player().is_member:
                    cmd.bot.log(f'[merge] "{name}" is member only; cannot buy it.')
                    return
                await cmd.buy_item(shop_id, name, need,
                                   shop_item_id=in_shop.shop_item_id)
            else:
                await _merge_item(cmd, map_name, shop_id, in_shop, need,
                                  find_ingredients, depth + 1)
        elif find_ingredients is not None:
            # Not sold here: the merge script's own farmer takes it.
            cmd.bot.log(f'[merge] "{name}" is not in shop {shop_id}; asking '
                        f'the merge script for x{need}')
            cmd.add_drop(name)
            await find_ingredients(item_id, need)
        else:
            cmd.bot.log(f'[merge] "{name}" is not in shop {shop_id} and no '
                        f'merge script was given; skipping it.')
            continue

        if _held_by_id(cmd, item_id) < need:
            cmd.bot.log(f"[merge] warning: {name} x{need} was not acquired.")

    await _open_shop(cmd, map_name, shop_id)
    if all([_held_by_id(cmd, iid) >= q for iid, _, q in entry.merge_requirements]):
        await cmd.buy_item(shop_id, entry.item_name, qty,
                           shop_item_id=entry.shop_item_id)


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

async def enhancement_unlocked(cmd: Command, name: str) -> bool:
    """``CoreAdvanced.uXxx()``: is that enhancement unlocked on this account?

    Args:
        cmd (Command): Facade to act through.
        name (str): Flag name from :data:`UNLOCKS`, e.g. ``"Valiance"``.
    """
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


async def _resolve_flags(cmd: Command, names, cache: dict = None) -> dict:
    """Evaluate the flags one table entry needs, as its lambdas expect them.

    Args:
        cmd (Command): Facade to act through.
        names: Flag names from the entry, incl. ``__quest:N``/``__cur:slot``.
        cache (dict): Optional per-lookup memo.  Without it every flag is read
            again, which is what the reference does.
    """
    flags = {}
    for name in names:
        if name in (cache or {}):
            flags[name] = cache[name]
            continue
        if name.startswith("__quest:"):
            flags[name] = await cmd.is_completed_before(int(name.split(":")[1]))
        elif name.startswith("__cur:"):
            flags[name] = _current_special(cmd, name.split(":", 1)[1])
        else:
            flags[name] = await enhancement_unlocked(cmd, name)
        if cache is not None:
            cache[name] = flags[name]
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
    from bot.core_advanced_tables import AWE_LIBRARY, FORGE_LIBRARY

    lowered = class_name.strip().lower()
    cache: dict = {}
    for library in (FORGE_LIBRARY, AWE_LIBRARY):
        for plan in library:
            if lowered not in plan.classes:
                continue
            if plan.condition == "False":
                continue
            flags = await _resolve_flags(cmd, _constant_names(
                plan.condition, plan.type, plan.cape, plan.helm, plan.weapon),
                cache)
            if callable(plan.condition) and plan.condition(flags):
                continue
            if plan.requires and not all(flags.get(name)
                                         for name in plan.requires):
                continue
            return plan
    return None


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
    for _ in range(40):
        equipped = cmd.get_equipped_class()
        if equipped is not None and equipped.s_name.strip().lower() == lowered:
            break
        await cmd.sleep(100)

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


async def _best_enhancement(cmd: Command, item, shop_id: int, cape: str = "None",
                            helm: str = "None", weapon: str = "None"):
    """The shop entry ``_AutoEnhance`` would pick for ``item``, or None.

    The entry has to name the wanted special (or the slot) and pass the member and
    level filters; of what is left, the highest level wins, then the upgrade flag.

    Args:
        cmd (Command): Facade to act through.
        item: The inventory item being enhanced.
        shop_id (int): Enhancement shop to search.
        cape (str): Wanted ``CapeSpecial``, or ``"None"``.
        helm (str): Wanted ``HelmSpecial``, or ``"None"``.
        weapon (str): Wanted ``WeaponSpecial``, or ``"None"``.
    """
    await cmd.ensure_load_shop(shop_id)
    shop = None
    for loaded in cmd.bot.loaded_shop_datas:
        if str(loaded.shop_id) == str(shop_id):
            shop = loaded
            break
    if shop is None:
        return None

    player = cmd.get_player()
    level = player.LEVEL or 0
    cape_on = cape != "None" and item.s_es == "ba"
    helm_on = helm != "None" and item.s_es == "he"
    weapon_on = weapon != "None" and item.s_es == "Weapon"

    available = []
    for entry in shop.items:
        if (not player.is_member and entry.is_upgrade) or entry.level > level:
            continue
        name = entry.item_name.replace(" ", "").replace("'", "")
        if cape_on and cape.replace("_", "").lower() in name:
            available.append(entry)
        elif weapon_on and weapon.replace("_", "").lower() in name:
            available.append(entry)
        elif helm_on and helm.replace("_", "").lower() in name:
            available.append(entry)
        elif item.s_es == "ar" and "armor" in name:
            available.append(entry)
        elif item.s_es == "he" and "helm" in name:
            available.append(entry)
        elif item.s_es == "ba" and "cape" in name:
            available.append(entry)
        elif item.s_es == "Weapon" and "weapon" in name:
            available.append(entry)

    if not available:
        return None
    if len(available) == 1:
        return available[0]
    return sorted(available,
                  key=lambda e: (e.level, 1 if e.is_upgrade else 0),
                  reverse=True)[0]


async def _auto_enhance(cmd: Command, item, shop_id: int,
                        map_name: str = None, cape: str = "None",
                        helm: str = "None", weapon: str = "None") -> None:
    """``CoreAdvanced._AutoEnhance``: search a shop and send the one packet."""
    if map_name and cmd.is_not_in_map(map_name):
        await cmd.join_map(map_name)

    best = await _best_enhancement(cmd, item, shop_id, cape, helm, weapon)
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
                await _auto_enhance(cmd, cape_item, CAPE_SHOP, FORGE_MAP,
                                    cape=cape)
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
                                    else None, helm=helm)
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
                                FORGE_MAP if special > 6 else None,
                                weapon=weapon)

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
