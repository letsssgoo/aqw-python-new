"""Enhancements for Ultra V2: base / cape / helm / weapon, with fallbacks.

The reference's ``PrepareEnhancements`` buys a missing enhancement from its shop.
That purchase half is **not ported**: this module resolves the enhancement to an
item the account already owns (inventory or bank) and stops the run by name when
it owns none, instead of silently fighting in the wrong gear.  The weapon tries
the preset's ``weapon_fallbacks`` in order, exactly like ``WeaponEnhancement
Fallbacks`` in the source.

``equip_enhancement`` already knows which slot a name belongs to when the name is
unique; the slot is passed explicitly anyway, because ``Forge`` alone exists as a
weapon, a cape and a helm tier.
"""
from __future__ import annotations

from typing import Optional, Sequence, Tuple

from bot.ultra.v2.presets import Preset

#: Preset field -> the equipment slot it is pinned to.
SLOTS: Tuple[Tuple[str, str], ...] = (
    ("base", "class"),
    ("cape", "cape"),
    ("helm", "helm"),
    ("weapon", "weapon"),
)


async def prepare(cmd, preset: Preset) -> bool:
    """Wear every enhancement the preset names; False stops the run."""
    for attribute, slot in SLOTS:
        wanted: Optional[str] = getattr(preset, attribute)
        if not wanted:
            continue
        candidates: Sequence[str] = (wanted,)
        if attribute == "weapon":
            candidates = (wanted, *preset.weapon_fallbacks)
        if not await _apply_one(cmd, slot, candidates):
            cmd.bot.log(f"[v2] no {slot} enhancement {wanted!r} in the inventory "
                        f"or bank"
                        + (f" (fallbacks tried: "
                           f"{', '.join(preset.weapon_fallbacks)})"
                           if attribute == "weapon" and preset.weapon_fallbacks
                           else "")
                        + "; the run stops rather than fighting in the wrong "
                          "gear.")
            return False
    return True


async def _apply_one(cmd, slot: str, candidates: Sequence[str]) -> bool:
    """Try each name for one slot; log which one landed."""
    for candidate in candidates:
        if await cmd.equip_enhancement(candidate, slot=slot):
            cmd.bot.log(f"[v2] {slot} enhancement: {candidate}.")
            return True
    return False


def describe(preset: Preset) -> str:
    """One line for the log: what the preset wants to wear."""
    bits = [f"base {preset.base}"]
    if preset.cape:
        bits.append(f"cape {preset.cape}")
    if preset.helm:
        bits.append(f"helm {preset.helm}")
    if preset.weapon:
        fallbacks = f" (then {', '.join(preset.weapon_fallbacks)})" \
            if preset.weapon_fallbacks else ""
        bits.append(f"weapon {preset.weapon}{fallbacks}")
    return " / ".join(bits)
