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

from bot.core_bots import (_find_shop, check_class_rank, load_shop_entry,
                           points_to_level)
from bot.core_farms import farm_experience, farm_faction, farm_gold, icestorm_arena
from core.command import Command, QUIET_PASSES

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


async def farm_quest_reward(cmd: Command, quest_id: int, item_name: str,
                            qty: int, farm_pass,
                            max_quiet_passes: int = QUIET_PASSES * 4,
                            is_temp: bool = False) -> bool:
    """``register_quest`` then run ``farm_pass`` until its reward is held.

    Every merge shop and story step needs at least one item it cannot buy, and
    the reference farms it with ``while (!CheckInventory(reward)) { ... }``.
    Ported literally that deadlocks: once the ingredients are complete every
    step of the pass returns before its first ``await``, so the loop never
    yields and the auto turn-in that grants the reward can never run.  The pass
    is yielded and bounded through :class:`PassGuard`, which names the quest, so
    a refused or already-completed one is visible instead of silent.

    The quiet allowance is four times the default on purpose: a quest reward
    arrives with the server's turn-in, not with the pass, so a few passes can
    end with nothing new in the bag while that turn-in is still in flight -- and
    the stock signature the guard reads cannot see a turn-in in flight.  At the
    plain default, a reward farm with a slow turn-in gave up early and reported
    the item as unobtainable.

    Args:
        cmd (Command): Facade to act through.
        quest_id (int): Quest whose turn-in gives the item.
        item_name (str): Reward to wait for.
        qty (int): How many are needed.
        farm_pass (Callable): ``async () -> None``, one full pass of the farm.
        max_quiet_passes (int): Give up after this many passes that changed
            nothing at all (four times ``QUIET_PASSES`` by default, for the
            turn-in latency above).
        is_temp (bool): The reward lands in the temporary bag.

    Returns:
        bool: True when the item is held.
    """
    if (await cmd.register_quest(quest_id)) is False and not await cmd.has_item(
            item_name, qty, isTemp=is_temp):
        # A registered quest that never got accepted drops nothing, and the
        # farm would spin its quiet passes before saying only "not acquired".
        cmd.bot.log(f'[farm] quest {quest_id} could not be accepted; '
                    f'"{item_name}" x{qty} is not farmable from it.')
        cmd.unregister_quest(quest_id)
        return False
    guard = cmd.pass_guard(f'"{item_name}" x{qty} (quest {quest_id})',
                           max_quiet_passes)
    while (cmd.is_still_connected()
           and not await cmd.has_item(item_name, qty, isTemp=is_temp)):
        await farm_pass()
        if not await guard.tick():
            return False
    return True


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
        find_ingredients (Callable | None): ``async (cmd, item_id, name,
            qty)``, the merge script's own farmer for items the shop does not
            sell.  The reference reaches it through its ``externalItem``
            fields; the same values are handed over as arguments instead, with
            the command facade first so the farmer can act.
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
    #: ``False`` until the requested entry is seen: a ``buy_only_this`` that the
    #: shop does not carry used to end the walk with no word at all, which reads
    #: exactly like a successful merge in the log.
    found = buy_only_this is None
    for entry in shop.items:
        name = entry.item_name
        if not name or name in seen:
            continue
        seen.add(name)
        if name.lower().endswith("insignia") or name.lower() in blocked:
            continue
        if buy_only_this and name.lower() != buy_only_this.lower():
            continue
        found = True
        if entry.is_upgrade and not cmd.get_player().is_member:
            cmd.bot.log(f'[merge] skipping "{name}" (member only).')
            continue
        if _held_by_id(cmd, entry.item_id) >= 1:
            cmd.bot.log(f'[merge] "{name}" is already owned.')
            continue
        if entry.merge_requirements:
            # The recipe comes from the live ``loadShop`` payload, never from
            # this file: printing it makes a shop's own numbers (30 vs 50) show
            # up in the run instead of only in the merge walk.
            cmd.bot.log(f'[merge] "{name}" recipe: ' + ", ".join(
                f"{n} x{q}" for _, n, q in entry.merge_requirements))
        cmd.bot.log(f'[merge] farming for "{name}"')
        await _merge_item(cmd, map_name, shop_id, entry, 1, find_ingredients, 0)
        if _held_by_id(cmd, entry.item_id) >= 1:
            # ``_merge_item`` buys the entry itself once its recipe is met, and
            # the merge *consumes* that recipe -- so re-reading the ingredients
            # here would report a completed merge as "not bought yet".
            continue
        await _open_shop(cmd, map_name, shop_id)
        missing = [f"{n} x{q}" for iid, n, q in entry.merge_requirements
                   if _held_by_id(cmd, iid) < q]
        if not missing:
            await buy_item(cmd, shop_id, name, 1, map_name=map_name,
                           shop_item_id=entry.shop_item_id)
        elif missing:
            cmd.bot.log(f'[merge] "{name}" not bought yet, missing: '
                        f'{", ".join(missing)}')

    if not found:
        cmd.bot.log(f'[merge] shop {shop_id} has no entry named '
                    f'"{buy_only_this}"; nothing merged.')


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
                await buy_item(cmd, shop_id, name, need, map_name=map_name,
                               shop_item_id=in_shop.shop_item_id)
            else:
                await _merge_item(cmd, map_name, shop_id, in_shop, need,
                                  find_ingredients, depth + 1)
        elif find_ingredients is not None:
            # Not sold here: the merge script's own farmer takes it.
            cmd.bot.log(f'[merge] "{name}" is not in shop {shop_id}; asking '
                        f'the merge script for x{need}')
            cmd.add_drop(name)
            await find_ingredients(cmd, item_id, name, need)
        else:
            cmd.bot.log(f'[merge] "{name}" is not in shop {shop_id} and no '
                        f'merge script was given; skipping it.')
            continue

        if _held_by_id(cmd, item_id) < need:
            cmd.bot.log(f"[merge] warning: {name} x{need} was not acquired.")

    await _open_shop(cmd, map_name, shop_id)
    held = [(n, _held_by_id(cmd, iid), q) for iid, n, q in entry.merge_requirements]
    if all([got >= need for _n, got, need in held]):
        await buy_item(cmd, shop_id, entry.item_name, qty, map_name=map_name,
                       shop_item_id=entry.shop_item_id)
        # A merge consumes its recipe on the server, so the three outcomes are
        # told apart here instead of leaving a silent "nothing happened":
        if await _await_item(cmd, entry.item_id, qty):
            return
        still_there = all([_held_by_id(cmd, iid) >= q
                           for iid, _n, q in entry.merge_requirements])
        if still_there:
            cmd.bot.log(f'[merge] "{entry.item_name}" was refused: the packet '
                        f'went out and the recipe is still in the bag (check '
                        f'gold and the entry\'s own requirement).')
        else:
            cmd.bot.log(f'[merge] "{entry.item_name}" was merged (the recipe is '
                        f'gone) but the item is not in the bag yet.')
    else:
        cmd.bot.log(f'[merge] "{entry.item_name}" not merged, short of: '
                    + ", ".join(f"{n} ({got}/{need})"
                                for n, got, need in held if got < need))


async def _await_item(cmd: Command, item_id, qty: int,
                      timeout_ms: int = 5000) -> bool:
    """Bounded wait for a bought item's inventory packet to land."""
    waited = 0
    while cmd.is_still_connected() and waited < timeout_ms:
        if _held_by_id(cmd, item_id) >= qty:
            return True
        await cmd.sleep(500)
        waited += 500
    return _held_by_id(cmd, item_id) >= qty


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

#: ``SpecialIdMapper.WeaponFromId``: **legacy** proc ids -> ``WeaponSpecial``.
#: Deliberately not the inverse of :data:`WEAPON_SPECIALS`: the reference keeps
#: this for ids persisted by older builds, where 0 meant Forge and 1 meant None.
LEGACY_WEAPON_IDS = {
    0: "Forge", 1: "None", 2: "Spiral_Carve", 3: "Awe_Blast", 4: "Health_Vamp",
    5: "Mana_Vamp", 6: "Powerword_Die", 7: "Lacerate", 8: "Smite",
    9: "Valiance", 10: "Arcanas_Concerto", 11: "Acheron", 12: "Elysium",
    13: "Praxis", 14: "Dauntless", 15: "Ravenous",
}

#: ``SpecialIdMapper.HelmFromId``: the helm pattern ids, by the same legacy ids.
LEGACY_HELM_IDS = {
    0: "None", 10: "Forge", 25: "Vim", 26: "Examen", 27: "Pneuma",
    28: "Anima", 32: "Hearty",
}


def weapon_from_id(item_id: int) -> str:
    """``SpecialIdMapper.WeaponFromId``: legacy id -> weapon special name."""
    return LEGACY_WEAPON_IDS.get(int(item_id), "None")


def helm_from_id(item_id: int) -> str:
    """``SpecialIdMapper.HelmFromId``: legacy id -> helm special name."""
    return LEGACY_HELM_IDS.get(int(item_id), "None")


def is_weapon(item) -> bool:
    """``CoreAdvanced.isWeapon``: whether an item fills the weapon slot."""
    return getattr(item, "s_es", "") == "Weapon"

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


def current_class_enh(cmd: Command) -> str:
    """``CoreAdvanced.CurrentClassEnh``: the equipped class's enhancement type.

    Patterns 1 and 23 are the aliases the reference folds into 9 (Lucky), and a
    pattern that is not one of the enhancement types reads Lucky as well -- the
    same answer ``Enum.IsDefined ? ... : Lucky`` gives.
    """
    equipped = cmd.get_equipped_class()
    pattern = int(getattr(equipped, "enh_pattern_id", 0) or 0) if equipped else 0
    if pattern in (1, 23):
        pattern = 9
    for name, value in ENHANCEMENT_TYPES.items():
        if value == pattern:
            return name
    return "Lucky"


def current_cape_special(cmd: Command) -> str:
    """``CoreAdvanced.CurrentCapeSpecial``."""
    return _current_special(cmd, "ba")


def current_helm_special(cmd: Command) -> str:
    """``CoreAdvanced.CurrentHelmSpecial``."""
    return _current_special(cmd, "he")


def current_weapon_special(cmd: Command) -> str:
    """``CoreAdvanced.CurrentWeaponSpecial``."""
    return _current_special(cmd, "Weapon")


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


#: Rank points a class item needs before it reads "Rank 10".
CLASS_RANK_MAX = 302500
#: Classes the reference refuses to rank past Rank 1.
UNRANKABLE_CLASSES = ("hobo highlord", "no class", "obsidian no class")


async def gear_store(cmd: Command, restore: bool = False,
                     enh_after: bool = False) -> None:
    """``CoreAdvanced.GearStore``: remember the worn gear, then put it back.

    The reference keeps this on the instance; one ``Bot`` owns one state here,
    so it is stored on ``cmd.bot`` under ``gear_store_saved``.

    Args:
        cmd (Command): Facade to act through.
        restore (bool): True to re-equip what was saved instead of saving.
        enh_after (bool): Re-apply the saved enhancements after restoring.
    """
    if not restore:
        equipped = [item for item in cmd.bot.player.INVENTORY if item.is_equipped]
        saved = {
            "items": [item.item_name for item in equipped],
            "class_enh": current_class_enh(cmd),
            "weapon": current_weapon_special(cmd),
            "cape": (current_cape_special(cmd)
                     if any(item.s_es == "ba" for item in equipped)
                     else "None"),
            "helm": (current_helm_special(cmd)
                     if any(item.s_es == "he" for item in equipped)
                     else "None"),
        }
        cmd.bot.gear_store_saved = saved
        cmd.bot.log("GearStore: Saved current equipment state")
        cmd.bot.log(f" - Items: {', '.join(saved['items'])}")
        cmd.bot.log(f" - Class Enh: {saved['class_enh']}")
        if saved["cape"] != "None":
            cmd.bot.log(f" - Cape Special: {saved['cape']}")
        if saved["helm"] != "None":
            cmd.bot.log(f" - Helm Special: {saved['helm']}")
        if saved["weapon"] != "None":
            cmd.bot.log(f" - Weapon Special: {saved['weapon']}")
        return

    saved = getattr(cmd.bot, "gear_store_saved", None)
    if not saved or not saved.get("items"):
        cmd.bot.log("GearStore: nothing was saved, so there is nothing to "
                    "restore.")
        return

    cmd.bot.log("GearStore: Restoring saved equipment state")
    cmd.bot.log(f" - Items: {', '.join(saved['items'])}")
    if enh_after:
        cmd.bot.log(f" - Enhancements -> Class: {saved['class_enh']}"
                    f", Cape: {saved['cape']}, Helm: {saved['helm']}"
                    f", Weapon: {saved['weapon']}")
    for name in saved["items"]:
        if not await cmd.equip_item(name):
            cmd.bot.log(f"[advanced] GearStore: {name!r} could not be put back "
                        f"on.")
    if enh_after:
        await enhance_equipped(cmd, saved["class_enh"], saved["cape"],
                               saved["helm"], saved["weapon"])


async def rank_up_class(cmd: Command, class_name: str = "", item_id: int = 0,
                        gear_restore: bool = True) -> None:
    """``CoreAdvanced.RankUpClass``: carry one class to Rank 10 in the arena.

    Unlike :func:`bot.core_farms.icestorm_arena` this must keep the *ranked*
    class on, so the arena is entered with ``keep_class=True``; the reference
    equips the class before the run for the same reason.

    Args:
        cmd (Command): Facade to act through.
        class_name (str): Class to rank, or ``"(Current)"`` for the worn one.
        item_id (int): Class item id; wins over ``class_name`` when set.
        gear_restore (bool): Put the previously worn gear back afterwards.
    """
    if class_name == "(Current)":
        equipped = cmd.get_equipped_class()
        class_name = getattr(equipped, "item_name", "") if equipped else ""
        if not class_name:
            cmd.bot.log("CurrentClass is null or has no name. Cannot rank up.")
            return

    def matches(item) -> bool:
        if item.s_es != "ar":
            return False
        if item_id:
            return str(item.item_id) == str(item_id)
        return item.item_name.strip().lower() == class_name.strip().lower()

    item = next((i for i in cmd.bot.player.INVENTORY if matches(i)), None)
    if item is None and item_id:
        banked = cmd.bot.player.get_item_bank_by_id(item_id)
    elif item is None:
        banked = cmd.bot.player.get_item_bank(class_name)
    else:
        banked = None
    if item is None and banked is not None:
        await cmd.bank_to_inv(banked.item_name)
        item = next((i for i in cmd.bot.player.INVENTORY if matches(i)), None)
        if item is None and item_id:
            # The class is already in the inventory: the bank move can refuse
            # (a full stack, or the item was pulled over while it ran), and then
            # the lookup by id is the one that still finds it.
            item = cmd.bot.player.get_item_inventory_by_id(item_id)
        if item is None:
            item = cmd.bot.player.get_item_inventory(banked.item_name)
        if item is not None:
            cmd.bot.log(f"[class] {item.item_name} is in the inventory already")
    if item is None:
        equipped = cmd.get_equipped_class()
        if equipped is not None and matches(equipped):
            # Wearing it is enough to rank it -- the arena keeps the worn class.
            item = equipped
            cmd.bot.log(f"[class] {item.item_name} is already equipped")
    if item is None:
        cmd.bot.log(f"Can't level up "
                    f"{item_id if item_id else class_name!r} because you don't "
                    f"own it.")
        return

    if item.is_upgrade and not cmd.bot.player.is_member:
        cmd.bot.log(f"{item.item_name!r} requires membership to rank up.")
        return
    if int(item.qty) >= CLASS_RANK_MAX:
        cmd.bot.log(f"{item.item_name!r} is already Rank 10")
        return
    if item.item_name.strip().lower() in UNRANKABLE_CLASSES:
        cmd.bot.log(f"{item.item_name!r} cannot be leveled past Rank 1")
        return

    if gear_restore:
        await gear_store(cmd)

    rank_now = check_class_rank(cmd, item.item_name)
    cmd.bot.log(f"[class] Ranking {item.item_name} (rank {rank_now} -> 10)")

    await smart_enhance(cmd, item.item_name)

    item = next((i for i in cmd.bot.player.INVENTORY if matches(i)), None)
    if item is None:
        cmd.bot.log("Class item not found in inventory after enhance.")
        return
    if item.enh_level <= 0:
        cmd.bot.log(f"Can't level up {item.item_name!r} because it's not "
                    f"enhanced.")
        return
    if not item.is_equipped:
        await cmd.equip_item(item.item_name)
        worn = cmd.get_equipped_class()
        if worn is None or not matches(worn):
            # The arena ranks whatever is worn, so entering it without the class
            # on would rank something else and report success for the wrong one.
            cmd.bot.log(f"[class] could not equip {item.item_name}; the arena is "
                        f"not entered.")
            return

    # The reference toggles a class boost here; this engine has no boosts.
    await icestorm_arena(cmd, cmd.get_player().LEVEL, rank_up_class=True,
                         keep_class=True)

    item = next((i for i in cmd.bot.player.INVENTORY if matches(i)), None)
    if item is None:
        cmd.bot.log("Class item missing after arena.")
        return
    if int(item.qty) >= CLASS_RANK_MAX:
        cmd.bot.log(f"{item.item_name!r} is now Rank 10")
    else:
        cmd.bot.log(f"{item.item_name!r} is somehow... not rank 10??")

    if gear_restore:
        await gear_store(cmd, restore=True)


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
