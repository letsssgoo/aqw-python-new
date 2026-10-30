"""Scroll crafting for Ultra V2 -- a port of ``CoreLoneWolf.PrepareScrolls``.

Three scrolls matter to the army fights:

==================  =======  =========  ==============  ==================================
scroll              quest    rank       stock           materials (per turn-in)
==================  =======  =========  ==============  ==================================
Scroll of Enrage    2330     SC 5       80              Gold Voucher 500k x2, Arcane Quill x10, Zealous Ink x1
Scroll of Decay     2331     SC 5       10              the quest's own requirement
Scroll of Mystify   2344     SC 8       10              the quest's own requirement
==================  =======  =========  ==============  ==================================

Two routes, exactly as the reference picks them:

* **gold** when the account holds >= 1,000,000 gold -- buy the vouchers, quills
  and ink at the /spellcraft shops (693 for quills, 549 for ink) and turn the
  quest in until the stock target is met;
* **farming** otherwise -- 2 Mystic Parchment from /underworld ``r2/Up`` plus
  ink from shop 549.  Mystify has no farming route in the reference either, so
  without gold it is refused.

The turn-in count for an optional scroll is read from the quest itself
(requirement quantity and reward quantity), which is what the reference does with
``Core.EnsureLoad(quest).Requirements``/``.Rewards``.  When the payload does not
name the requirement, the run says so instead of farming blind.
"""
from __future__ import annotations

import math
from typing import Optional, Sequence, Tuple

ENRAGE = "Scroll of Enrage"
DECAY = "Scroll of Decay"
MYSTIFY = "Scroll of Mystify"
SUPPORTED = (ENRAGE, DECAY, MYSTIFY)

#: Stock targets from the reference (``EnrageThreshold`` / ``OptionalScrollThreshold``).
ENRAGE_THRESHOLD = 80
OPTIONAL_SCROLL_THRESHOLD = 10

#: ``CoreLoneWolf``'s constants.
SPELLCRAFT_MAP = "spellcraft"
ARCANE_QUILL_SHOP = 693
ARCANE_QUILL_SHOP_ITEM = 7686
SPELL_INK_SHOP = 549
ENRAGE_QUEST = 2330
DECAY_QUEST = 2331
MYSTIFY_QUEST = 2344
ENRAGE_MAX_STACK = 1000
ENRAGE_REWARD_QUANTITY = 40
GOLD_ROUTE_MIN = 1_000_000
GOLD_VOUCHER = "Gold Voucher 500k"
ARCANE_QUILL = "Arcane Quill"
ZEALOUS_INK = "Zealous Ink"
MYSTIC_PARCHMENT = "Mystic Parchment"
PARCHMENT_MAP, PARCHMENT_CELL, PARCHMENT_PAD = "underworld", "r2", "Up"

QUESTS = {ENRAGE: ENRAGE_QUEST, DECAY: DECAY_QUEST, MYSTIFY: MYSTIFY_QUEST}
REQUIRED_RANK = {ENRAGE: 5, DECAY: 5, MYSTIFY: 8}
FARMABLE = (ENRAGE, DECAY)          # Mystify is gold-only in the reference


def threshold(name: str) -> int:
    return ENRAGE_THRESHOLD if name == ENRAGE else OPTIONAL_SCROLL_THRESHOLD


def route(gold: int) -> str:
    """``"gold"`` or ``"farm"`` -- the reference's one-line choice."""
    return "gold" if gold >= GOLD_ROUTE_MIN else "farm"


def turns_for(held: int, per_turn: int, target: int) -> int:
    """Turn-ins needed to reach ``target``; ``0`` when already there."""
    if per_turn <= 0:
        return 0
    return max(0, math.ceil((target - held) / per_turn))


async def prepare(cmd, name: Optional[str]) -> bool:
    """Bring ``name`` up to the reference's stock level, crafting when short."""
    if not name:
        return True
    if name not in SUPPORTED:
        cmd.bot.log(f"[v2] scroll {name!r} is not supported; nothing prepared.")
        return False

    wanted = threshold(name)
    held = await _quantity(cmd, name)
    if held >= wanted:
        cmd.bot.log(f"[v2] {name} already available ({held}/{wanted}).")
        return True
    if cmd.is_in_bank(name):
        await cmd.bank_to_inv(name)
        held = await _quantity(cmd, name)
        if held >= wanted:
            cmd.bot.log(f"[v2] {name} withdrawn from the bank ({held}/{wanted}).")
            return True

    rank = REQUIRED_RANK[name]
    if cmd.get_faction_rank("SpellCrafting") < rank:
        cmd.bot.log(f"[v2] {name} needs SpellCrafting rank {rank}; the account "
                    f"has rank {cmd.get_faction_rank('SpellCrafting')}.")
        return False
    if not cmd.is_in_inventory(name):
        cmd.add_drop(name)

    if name == ENRAGE:
        return await _prepare_enrage(cmd, held)
    return await _prepare_optional(cmd, name, held)


async def equip(cmd, name: Optional[str]) -> bool:
    """Put a scroll in slot 5, saying why when it cannot."""
    if not name:
        return True
    if name not in SUPPORTED:
        cmd.bot.log(f"[v2] scroll {name!r} is not supported.")
        return False
    if not await cmd.has_item(name):
        if cmd.is_in_bank(name):
            await cmd.bank_to_inv(name)
        if not await cmd.has_item(name):
            cmd.bot.log(f"[v2] {name} is not in the inventory, so slot 5 keeps "
                        f"what it had.")
            return False
    equipped = await cmd.equip_scroll(name)
    if equipped:
        cmd.bot.log(f"[v2] {name} equipped.")
    else:
        cmd.bot.log(f"[v2] {name} could not be equipped.")
    return equipped


# ---------------------------------------------------------------------------
# Enrage
# ---------------------------------------------------------------------------

async def _prepare_enrage(cmd, held: int) -> bool:
    choice = route(cmd.bot.player.GOLD)
    await cmd.join_map(SPELLCRAFT_MAP)
    if not cmd.is_in_map(SPELLCRAFT_MAP):
        cmd.bot.log(f"[v2] {ENRAGE}: {SPELLCRAFT_MAP} could not be joined.")
        return False

    if choice == "gold":
        turns = turns_for(held, ENRAGE_REWARD_QUANTITY, ENRAGE_MAX_STACK)
        cmd.bot.log(f"[v2] {ENRAGE}: gold route, {turns} turn-in(s) of quest "
                    f"{ENRAGE_QUEST}.")
        if not await _ensure(cmd, GOLD_VOUCHER, 2):
            return False
        if not await _ensure(cmd, ARCANE_QUILL, 10,
                            shop_item_id=ARCANE_QUILL_SHOP_ITEM):
            return False
        if not await _ensure(cmd, ZEALOUS_INK, turns):
            return False
        if not await _complete(cmd, ENRAGE_QUEST, turns):
            return False
    else:
        cmd.bot.log(f"[v2] {ENRAGE}: farming route (under 1,000,000 gold).")
        if not await _farm_materials(cmd):
            return False
        if not await _complete(cmd, ENRAGE_QUEST, 1):
            return False

    held = await _quantity(cmd, ENRAGE)
    if held < ENRAGE_THRESHOLD:
        cmd.bot.log(f"[v2] {ENRAGE}: only {held}/{ENRAGE_THRESHOLD} after "
                    f"crafting.")
        return False
    cmd.bot.log(f"[v2] {ENRAGE} prepared ({held}).")
    return True


# ---------------------------------------------------------------------------
# Decay / Mystify
# ---------------------------------------------------------------------------

async def _prepare_optional(cmd, name: str, held: int) -> bool:
    quest_id = QUESTS[name]
    choice = route(cmd.bot.player.GOLD)
    if choice == "farm" and name not in FARMABLE:
        cmd.bot.log(f"[v2] {name}: the reference only has a gold route, which "
                    f"needs {GOLD_ROUTE_MIN} gold.")
        return False

    if await cmd.ensure_accept_quest(quest_id) is False:
        cmd.bot.log(f"[v2] {name}: quest {quest_id} could not be accepted, so "
                    f"its recipe is unknown.")
        return False
    recipe = _recipe(cmd, quest_id)
    if recipe is None:
        cmd.bot.log(f"[v2] {name}: quest {quest_id} did not send usable recipe "
                    f"data.")
        return False
    requirement, per_turn, target = recipe
    turns = turns_for(held, per_turn, target)
    cmd.bot.log(f"[v2] {name}: {choice} route, {turns} turn-in(s) of quest "
                f"{quest_id}.")

    await cmd.join_map(SPELLCRAFT_MAP)
    if not cmd.is_in_map(SPELLCRAFT_MAP):
        cmd.bot.log(f"[v2] {name}: {SPELLCRAFT_MAP} could not be joined.")
        return False

    if choice == "gold":
        if not await _ensure(cmd, GOLD_VOUCHER, 2):
            return False
        if not await _ensure(cmd, ARCANE_QUILL, 10,
                            shop_item_id=ARCANE_QUILL_SHOP_ITEM):
            return False
        if not await _ensure_requirement(cmd, requirement, turns * per_turn):
            return False
    else:
        if not await _farm_materials(cmd):
            return False
        if not await _ensure_requirement(cmd, requirement, per_turn):
            return False

    if not await _complete(cmd, quest_id, turns):
        return False
    held = await _quantity(cmd, name)
    cmd.bot.log(f"[v2] {name} prepared ({held}).")
    return held >= min(OPTIONAL_SCROLL_THRESHOLD, target)


def _recipe(cmd, quest_id: int) -> Optional[Tuple[object, int, int]]:
    """``(requirement, quantity per turn, stock target)`` from the quest itself.

    Returns ``None`` when the payload does not carry what it takes to buy the
    requirement -- farming blind is what the reference avoids too.
    """
    loaded = cmd.get_loaded_quest(quest_id)
    if loaded is None:
        return None
    requirements = loaded.turn_in_items
    rewards = loaded.reward_entries
    if not requirements or not rewards:
        return None
    requirement_id, per_turn = requirements[0]
    reward_id, _reward_name, max_stack = rewards[0]
    reward_quantity = next(
        (int(row.get("iQty") or 1) for row in loaded.rewards
         if int(row.get("ItemID") or 0) == reward_id), 1)
    target = max_stack or OPTIONAL_SCROLL_THRESHOLD
    requirement = _requirement_item(cmd, quest_id, requirement_id, reward_id,
                                    reward_quantity, per_turn, target)
    if requirement is None:
        return None
    return requirement, per_turn, target


def _requirement_item(cmd, quest_id, requirement_id, reward_id, reward_quantity,
                      per_turn, target):
    """The requirement with a usable name, or ``None`` when it has none."""
    for entry in cmd.get_loaded_quest(quest_id).items:
        if int(entry.get("ItemID") or 0) != requirement_id:
            continue
        name = str(entry.get("sName") or "").strip()
        if name:
            return _Requirement(item_id=requirement_id, name=name, qty=per_turn,
                                reward_id=reward_id,
                                reward_qty=reward_quantity, target=target)
    return None


class _Requirement:
    """What one optional-scroll recipe needs, with the reward's stack target."""

    def __init__(self, *, item_id: int, name: str, qty: int, reward_id: int,
                 reward_qty: int, target: int):
        self.item_id = item_id
        self.name = name
        self.qty = qty
        self.reward_id = reward_id
        self.reward_qty = reward_qty
        self.target = target


# ---------------------------------------------------------------------------
# shared steps
# ---------------------------------------------------------------------------

async def _farm_materials(cmd) -> bool:
    """2 Mystic Parchment from /underworld plus 5 Zealous Ink from shop 549."""
    if not await cmd.has_item(ZEALOUS_INK):
        # ``PrepareDecayByFarming`` buys these five at ``SpellInkShopId`` (549).
        if not await _ensure(cmd, ZEALOUS_INK, 5, shop=SPELL_INK_SHOP):
            return False
    if await cmd.has_item(MYSTIC_PARCHMENT, 2):
        return True
    cmd.add_drop(MYSTIC_PARCHMENT)
    await cmd.join_map(PARCHMENT_MAP)
    await cmd.jump_cell(PARCHMENT_CELL, PARCHMENT_PAD)
    from templates.hunt import hunt_item
    await hunt_item(cmd, MYSTIC_PARCHMENT, 2, PARCHMENT_MAP,
                    cell=PARCHMENT_CELL, pad=PARCHMENT_PAD, monster_name="*")
    if not await cmd.has_item(MYSTIC_PARCHMENT, 2):
        cmd.bot.log(f"[v2] {ENRAGE}: 2 {MYSTIC_PARCHMENT} could not be obtained.")
        return False
    return True


async def _ensure(cmd, name: str, quantity: int, *, shop_item_id: int = 0,
                  shop: Optional[int] = None) -> bool:
    """Bring ``quantity`` of ``name`` into the inventory, buying the rest.

    The gold route buys every material -- voucher, quill and ink -- from the
    spellcraft shop **693**, which is what the reference's
    ``PrepareOptionalGoldScrollMaterial`` passes as ``ArcaneQuillShopId``.  Shop
    549 is the ink vendor the *farming* route uses, and asking it for a stack of
    99 is what left Dage's Decay/Mystify stock short.
    """
    if cmd.is_in_bank(name) and await _quantity(cmd, name) < quantity:
        await cmd.bank_to_inv(name)
    if await _quantity(cmd, name) >= quantity:
        return True
    shop = shop or ARCANE_QUILL_SHOP
    if await _buy_until(cmd, shop, name, quantity, shop_item_id):
        return True
    cmd.bot.log(f"[v2] {name!r} could not be obtained (shop {shop}, "
                f"{await _quantity(cmd, name)}/{quantity}).")
    return False


def _shop_item(cmd, shop_id: int, name: str, shop_item_id: int = 0):
    """The shop entry for ``name``, so its bundle, cost and flags can be read.

    ``shop_item_id`` picks the exact entry when the shop lists the same name
    more than once -- the captured Arcane Quill buy is entry **7686**, and the
    first same-named entry is a different one (bundle 1, no merge cost), which
    is why the purchase kept asking for one quill instead of ten.
    """
    try:
        shops = cmd.bot.loaded_shop_datas
    except Exception:
        return None
    fallback = None
    for shop in shops:
        if str(getattr(shop, "shop_id", "")) != str(shop_id):
            continue
        for item in getattr(shop, "items", []) or []:
            if str(getattr(item, "item_name", "")).lower() != name.lower():
                continue
            if shop_item_id and str(getattr(item, "shop_item_id", "")) == \
                    str(shop_item_id):
                return item
            fallback = fallback or item
    return fallback


#: Guards the recursive path: a merge material may itself need buying.
_BUYING: set = set()


def _merge_cost(item):
    """``[(item_id, name, qty)]`` the shop entry charges per purchase."""
    return list(getattr(item, "merge_requirements", []) or [])


async def _ensure_materials(cmd, item, name: str) -> bool:
    """Stock what the shop entry charges per purchase (e.g. 2 Gold Vouchers)."""
    for _item_id, material, qty in _merge_cost(item):
        material = str(material or "").strip()
        if not material or qty <= 0:
            continue
        if await _ensure(cmd, material, qty):
            continue
        cmd.bot.log(f"[v2] {name!r} needs {qty} {material} per purchase and "
                    f"there are not enough.")
        return False
    return True


async def _buy_until(cmd, shop: int, name: str, quantity: int,
                     shop_item_id: int = 0, chunk_size: int = 20,
                     wait_ms: int = 5000) -> bool:
    """Buy and **verify**, the way the shop really charges.

    Shop 693 is a merge shop: its entries cost *materials* per purchase -- the
    captured Arcane Quill buy is ``buyItem ... 693 7686 10`` answered by
    ``turnIn sItems:61043:2``, i.e. **2 Gold Voucher 500k for 10 quills**.  So
    the purchase quantity is the entry's own bundle, and the materials are
    stocked first; asking for an arbitrary stack is what the server dropped.
    """
    from bot.core_bots import buy_item as core_buy
    import time as _time

    if name in _BUYING:
        return False
    item = _shop_item(cmd, shop, name, shop_item_id)
    if item is not None:
        if getattr(item, "is_acs", False):
            cmd.bot.log(f"[v2] {name!r} is sold for Adventure Coins in shop "
                        f"{shop}; the gold route cannot buy it.")
            return False
        if getattr(item, "is_upgrade", False) and not getattr(
                getattr(cmd.bot, "player", None), "is_member", False):
            cmd.bot.log(f"[v2] {name!r} is member-only in shop {shop}.")
            return False

    bundle = int(getattr(item, "qty", 0) or 0) if item is not None else 0
    if bundle <= 0:
        # Shop 693 sells in tens: the captured Arcane Quill buy is
        # ``buyItem ... 693 7686 10``.  An entry that omits ``iQty`` is still
        # sold by the ten.
        bundle = 10 if shop == ARCANE_QUILL_SHOP else 1
        cmd.bot.log(f"[v2] {name!r}: shop entry has no bundle size; using "
                    f"{bundle} like the spellcraft shop does.")
    stack = int(getattr(item, "stackable", 0) or 0) if item is not None else 0
    per_purchase = max(1, bundle)
    if stack > 0:
        per_purchase = min(per_purchase, stack)

    have = await _quantity(cmd, name)
    _BUYING.add(name)
    try:
        while have < quantity:
            need = quantity - have
            # Whole bundles only: the shop sells 10 quills or 5 inks and drops
            # any other quantity, which is why "Arcane Quill x1" never arrived.
            bundles_needed = max(1, math.ceil(need / per_purchase))
            max_bundles = max(1, chunk_size // per_purchase)
            chunk = min(bundles_needed, max_bundles) * per_purchase
            if chunk <= 0:
                break
            price = (int(getattr(item, "cost", 0) or 0)
                     if item is not None else 0)
            gold = int(getattr(getattr(cmd.bot, "player", None), "GOLD", 0) or 0)
            if price > 0 and gold < price * chunk:
                cmd.bot.log(f"[v2] {name!r}: not enough gold ({price} each, "
                            f"{gold} in hand, {have}/{quantity}).")
                break
            if not await _ensure_materials(cmd, item, name):
                break

            moved = False
            for _try in range(3):
                await core_buy(cmd, shop, name, chunk, map_name=SPELLCRAFT_MAP,
                               shop_item_id=shop_item_id)
                deadline = _time.time() + wait_ms / 1000.0
                while _time.time() < deadline:
                    await cmd.sleep(500)
                    now = await _quantity(cmd, name)
                    if now >= quantity:
                        return True
                    if now != have:
                        have = now
                        moved = True
                        break
                if moved:
                    break
                await cmd.sleep(3000)
            if not moved:
                cost = ", ".join(f"{qty} {material}"
                                 for _id, material, qty in _merge_cost(item))
                cmd.bot.log(f"[v2] {name!r}: the shop accepted nothing for "
                            f"{chunk} after 3 tries (bundle {bundle}, stack "
                            f"{stack or '?'}, cost {cost or 'none'}, "
                            f"{have}/{quantity}).")
                break
    finally:
        _BUYING.discard(name)
    return have >= quantity


async def _ensure_requirement(cmd, requirement, quantity: int) -> bool:
    """Buy the optional-scroll requirement (ink) at the spellcraft shop 693.

    The reference's gold route calls ``PrepareOptionalGoldScrollMaterial`` for
    the requirement too, and that one buys at ``ArcaneQuillShopId`` (693); shop
    549 is only used by the farming route.
    """
    if cmd.is_in_bank(requirement.name) and \
            await _quantity(cmd, requirement.name) < quantity:
        await cmd.bank_to_inv(requirement.name)
    if await _quantity(cmd, requirement.name) >= quantity:
        return True
    if await _buy_until(cmd, ARCANE_QUILL_SHOP, requirement.name, quantity):
        return True
    cmd.bot.log(f"[v2] {requirement.name!r} could not be obtained "
                f"(shop {ARCANE_QUILL_SHOP}, "
                f"{await _quantity(cmd, requirement.name)}/{quantity}).")
    return False


async def _complete(cmd, quest_id: int, turns: int) -> bool:
    """Accept + turn the crafting quest in ``turns`` times."""
    for index in range(1, turns + 1):
        if await cmd.ensure_accept_quest(quest_id) is False:
            cmd.bot.log(f"[v2] quest {quest_id} could not be accepted "
                        f"(turn-in {index}/{turns}).")
            return False
        if await cmd.ensure_turn_in_quest(quest_id) is False:
            cmd.bot.log(f"[v2] quest {quest_id} could not be turned in "
                        f"(turn-in {index}/{turns}).")
            return False
        await cmd.sleep(1000)
    return True


async def _quantity(cmd, name: str) -> int:
    item = cmd.bot.player.get_item_inventory(name)
    return int(getattr(item, "qty", 0) or 0) if item else 0
