"""Potions for Ultra V2 -- the reference's twelve, prepared at shop 2036.

A port of ``CoreLoneWolf.PreparePotions`` / ``UsePotions`` / ``MaintainPotion``:

* a potion already in inventory is used as-is, one in the bank is withdrawn;
* otherwise the recipe is bought at **shop 2036, /alchemyacademy**, paying with
  a gold voucher (raised by spending gold), behind the faction rank the recipe
  carries;
* tonics and elixirs are consumed from the inventory and their aura is checked;
* a **combat potion takes equipment slot 5 -- the same slot as a scroll**, so a
  loadout may carry one or the other, never both.  :func:`use_loadout` therefore
  equips the combat potion only when the preset asks for one.

Divine Elixir / Unstable Divine Elixir have no recipe in the reference either --
they log "no purchase recipe is configured" and are skipped.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

TONIC = "tonic"
ELIXIR = "elixir"
COMBAT = "combat"

SHOP_MAP = "alchemyacademy"
SHOP_ID = 2036


@dataclass(frozen=True)
class Potion:
    """One whitelisted potion and how the reference obtains it."""

    name: str
    category: str
    aura: str
    voucher: str = "Gold Voucher 500k"
    voucher_qty: int = 0        # 0 = no purchase recipe in the reference
    voucher_cost: int = 500_000
    potion_qty: int = 0
    faction: Optional[str] = None
    rank: int = 0

    @property
    def purchasable(self) -> bool:
        return self.voucher_qty > 0 and self.potion_qty > 0


def _tonic(name: str, aura: str, voucher_qty: int) -> Potion:
    return Potion(name=name, category=TONIC, aura=aura, voucher_qty=voucher_qty,
                  potion_qty=10, faction="Alchemy", rank=8)


POTIONS: Dict[str, Potion] = {
    "Might Tonic": _tonic("Might Tonic", "Might", 2),
    "Body Tonic": _tonic("Body Tonic", "Body", 2),
    "Sage Tonic": _tonic("Sage Tonic", "Sage", 2),
    "Fate Tonic": _tonic("Fate Tonic", "Fate", 4),
    "Potent Battle Elixir": Potion("Potent Battle Elixir", ELIXIR,
                                   "Potent Battle Elixir",
                                   voucher_qty=4, potion_qty=8),
    "Potent Malevolence Elixir": Potion("Potent Malevolence Elixir", ELIXIR,
                                        "Potent Malevolence Elixir",
                                        voucher_qty=4, potion_qty=8),
    "Potent Destruction Elixir": Potion("Potent Destruction Elixir", ELIXIR,
                                        "Potent Destruction Elixir",
                                        voucher_qty=2, potion_qty=8),
    "Potent Revitalize Elixir": Potion("Potent Revitalize Elixir", ELIXIR,
                                       "Potent Revitalize Elixir",
                                       voucher_qty=2, potion_qty=8),
    "Divine Elixir": Potion("Divine Elixir", ELIXIR, "Divine Elixir"),
    "Unstable Divine Elixir": Potion("Unstable Divine Elixir", ELIXIR,
                                     "Unstable Divine Elixir"),
    "Potent Honor Potion": Potion("Potent Honor Potion", COMBAT,
                                  "Potent Honor Malice",
                                  voucher_qty=1, potion_qty=5,
                                  faction="Good", rank=10),
    "Felicitous Philtre": Potion("Felicitous Philtre", COMBAT,
                                 "Felicitous Philtre",
                                 voucher="Gold Voucher 100k",
                                 voucher_qty=2, voucher_cost=100_000,
                                 potion_qty=25),
}


def known(name: Optional[str]) -> bool:
    return bool(name) and name in POTIONS


def aura_of(name: str) -> str:
    """Aura the potion leaves behind, so a second cast can be skipped."""
    potion = POTIONS.get(name)
    return potion.aura if potion else name


async def prepare(cmd, name: Optional[str]) -> bool:
    """Make sure ``name`` is in the inventory, buying it the reference's way.

    Returns True when the potion is on hand afterwards.  A potion this engine
    cannot obtain is reported and skipped -- it must not stop the run, exactly
    like the reference's "skipped because ..." branches.
    """
    if not name:
        return True
    if name not in POTIONS:
        cmd.bot.log(f"[v2] potion {name!r} is not in the reference's list; "
                    f"skipping it.")
        return False
    potion = POTIONS[name]

    if await cmd.has_item(name):
        cmd.bot.log(f"[v2] {name} already available.")
        return True
    if cmd.is_in_bank(name):
        await cmd.bank_to_inv(name)
        if await cmd.has_item(name):
            cmd.bot.log(f"[v2] {name} moved from the bank.")
            return True

    if not potion.purchasable:
        cmd.bot.log(f"[v2] {name} has no purchase recipe in the reference; "
                    f"bring it yourself.")
        return False

    if potion.faction and cmd.get_faction_rank(potion.faction) < potion.rank:
        cmd.bot.log(f"[v2] {name} needs {potion.faction} rank {potion.rank}; "
                    f"skipping it.")
        return False

    from bot.core_bots import buy_item as core_buy

    held_vouchers = await _quantity(cmd, potion.voucher)
    missing = max(0, potion.voucher_qty - held_vouchers)
    if missing:
        gold_needed = missing * potion.voucher_cost
        if cmd.bot.player.GOLD < gold_needed:
            cmd.bot.log(f"[v2] {name} skipped: {gold_needed} gold is needed for "
                        f"{potion.voucher} x{missing}, the account has "
                        f"{cmd.bot.player.GOLD}.")
            return False
        await core_buy(cmd, SHOP_ID, potion.voucher, missing, map_name=SHOP_MAP)
        if await _quantity(cmd, potion.voucher) < potion.voucher_qty:
            cmd.bot.log(f"[v2] {name} skipped: {potion.voucher} could not be "
                        f"obtained.")
            return False

    await core_buy(cmd, SHOP_ID, name, potion.potion_qty, map_name=SHOP_MAP)
    if await cmd.has_item(name):
        cmd.bot.log(f"[v2] {name} x{potion.potion_qty} purchased.")
        return True
    cmd.bot.log(f"[v2] {name} could not be purchased.")
    return False


async def _quantity(cmd, name: str) -> int:
    """How many of ``name`` the account holds in the inventory."""
    item = cmd.bot.player.get_item_inventory(name)
    return int(getattr(item, "qty", 0) or 0) if item else 0


async def use(cmd, name: Optional[str]) -> bool:
    """Drink one potion of its category, skipping what is already active."""
    if not name or name not in POTIONS:
        return False
    potion = POTIONS[name]
    if cmd.bot.player.ISDEAD:
        return False

    if potion.category == COMBAT:
        # Slot 5: the run equips it once per attempt (see use_loadout).
        return await cmd.use_skill(5)

    if _has_aura(cmd, potion.aura):
        cmd.bot.log(f"[v2] {name} already active.")
        return True
    if not await cmd.has_item(name):
        cmd.bot.log(f"[v2] {name} is not in the inventory; skipped.")
        return False
    item = cmd.bot.player.get_item_inventory(name)
    item_id = int(getattr(item, "item_id", 0) or 0)
    if not item_id:
        cmd.bot.log(f"[v2] {name} has no item id; skipped.")
        return False
    await cmd.use_potion(item_id)
    cmd.bot.log(f"[v2] used {name}.")
    return True


async def use_loadout(cmd, tonic: Optional[str], elixir: Optional[str],
                     combat: Optional[str]) -> None:
    """The reference's ``UsePotions(tonic, elixir, combat)``."""
    await use(cmd, tonic)
    await use(cmd, elixir)
    if combat and combat in POTIONS:
        # A combat potion lives in slot 5, so it is *equipped*; the engine's
        # skill loop presses 5 when it is off cooldown.
        if cmd.bot.player.get_item_inventory(combat) is None:
            if cmd.is_in_bank(combat):
                await cmd.bank_to_inv(combat)
            else:
                return
        if await cmd.equip_scroll(combat):
            cmd.bot.log(f"[v2] {combat} equipped in slot 5.")


def _has_aura(cmd, aura: str) -> bool:
    from core.utils import normalize
    wanted = normalize(aura)
    for active in getattr(cmd.bot.player, "AURAS", []) or []:
        if normalize(getattr(active, "name", "")) == wanted:
            return True
    return False


def maintain(cmd, name: Optional[str]) -> bool:
    """``MaintainPotion``: recast a combat potion when its aura is about to fade."""
    if not name or name not in POTIONS or POTIONS[name].category != COMBAT:
        return False
    if cmd.bot.player.ISDEAD or not _has_aura(cmd, POTIONS[name].aura):
        return False
    if not cmd.bot.player.canUseSkill(5):
        return False
    return True
