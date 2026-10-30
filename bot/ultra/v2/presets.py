"""The class presets Ultra V2 needs -- the six classes the three compositions use.

A direct port of the reference's ``ClassPreset`` factories, trimmed to what the
ported compositions ask for.  ``Simple`` / ``Strict`` / ``KingsEcho`` are the only
skill modes needed:

* ``Simple`` cycles ``skills`` and casts whatever is off cooldown,
* ``Strict`` walks a long fixed rotation,
* ``KingsEcho`` reads residual energy, mana and health.

The reference's enhancement *purchasing* is not ported: a preset names the
enhancement and :mod:`bot.ultra.v2.enhancements` either wears it or stops the run
with its name.  Weapon fallbacks are honoured in order, exactly as the source
does (``WeaponEnhancementFallbacks``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

SIMPLE = "simple"
STRICT = "strict"
KINGS_ECHO = "kings_echo"


@dataclass(frozen=True)
class Preset:
    """One class as the reference's ``ClassPreset`` describes it.

    Args:
        cls: Class item name.
        skills: Slots the engine casts, in order (skill 0 is the auto attack).
        mode: ``simple``, ``strict`` or ``kings_echo``.
        base: Enhancement for the class slot.
        cape: Cape enhancement, ``None`` when the preset names none.
        helm: Helm enhancement, ``None`` when the preset names none.
        weapon: Weapon enhancement.
        weapon_fallbacks: Weapons to try, in order, when ``weapon`` is missing.
        tonic, elixir, combat_potion: Potion loadout; ``None`` leaves it out.
    """

    cls: str
    skills: Tuple[int, ...]
    mode: str = SIMPLE
    base: str = "Lucky"
    cape: Optional[str] = None
    helm: Optional[str] = None
    weapon: Optional[str] = None
    weapon_fallbacks: Tuple[str, ...] = ()
    tonic: Optional[str] = None
    elixir: Optional[str] = None
    combat_potion: Optional[str] = None

    @property
    def short(self) -> str:
        from bot.ultra.v2.options import SHORT_NAMES
        return SHORT_NAMES.get(self.cls, self.cls)


#: Verus DoomKnight's long rotation, verbatim from ``CoreLoneWolf``.
VDK_ROTATION = (1, 2, 3, 4, 1, 2, 3, 1, 2, 3, 4, 1, 2, 3, 1, 2, 4, 3, 1, 2, 3)

PRESETS: Dict[str, Preset] = {
    "legion revenant": Preset(
        cls="Legion Revenant",
        skills=(3, 4, 2, 1),
        base="Wizard",
        cape="Vainglory",
        helm="Forge",
        weapon="Arcana's Concerto",
        weapon_fallbacks=("Ravenous", "Valiance", "Health Vamp"),
        tonic="Sage Tonic",
        elixir="Potent Malevolence Elixir",
        combat_potion="Potent Honor Potion",
    ),
    "king's echo": Preset(
        cls="King's Echo",
        skills=(1, 2),
        mode=KINGS_ECHO,
        base="Lucky",
        cape="Vainglory",
        helm="Examen",
        weapon="Ravenous",
        weapon_fallbacks=("Elysium", "Valiance", "Health Vamp"),
        tonic="Fate Tonic",
        elixir="Potent Battle Elixir",
        combat_potion="Felicitous Philtre",
    ),
    "verus doomknight": Preset(
        cls="Verus DoomKnight",
        skills=VDK_ROTATION,
        mode=STRICT,
        base="Lucky",
        cape="Vainglory",
        helm="Forge",
        weapon="Ravenous",
        tonic="Fate Tonic",
        elixir="Potent Battle Elixir",
        combat_potion="Felicitous Philtre",
    ),
    "stonecrusher": Preset(
        cls="StoneCrusher",
        skills=(3, 2, 4, 1),
        base="Fighter",
        cape="Absolution",
        weapon="Valiance",
        tonic="Might Tonic",
        elixir="Potent Battle Elixir",
        combat_potion="Potent Honor Potion",
    ),
    "archpaladin": Preset(
        cls="ArchPaladin",
        skills=(3, 2, 1, 4),
        base="Lucky",
        cape="Vainglory",
        helm="Forge",
        weapon="Valiance",
        tonic="Fate Tonic",
        elixir="Potent Battle Elixir",
        combat_potion="Felicitous Philtre",
    ),
    "lord of order": Preset(
        cls="Lord of Order",
        skills=(2, 3, 1, 4),
        base="Lucky",
        cape="Penitence",
        weapon="Awe Blast",
        tonic="Fate Tonic",
        elixir="Potent Destruction Elixir",
        combat_potion="Potent Honor Potion",
    ),
}


def preset_for_class(class_name: str) -> Preset:
    """The preset for a class name, in any casing the option table uses."""
    preset = PRESETS.get(class_name.strip().lower())
    if preset is None:
        raise KeyError(f"no v2 preset for {class_name!r}; the compositions only "
                       f"use {', '.join(sorted(p.cls for p in PRESETS.values()))}")
    return preset


def preset_for(ultra: str, composition: str, slot: int,
               extras: Optional[dict] = None) -> Preset:
    """The preset one slot wears in one composition, with that ultra's overrides.

    The base preset comes from the shared factory (``LegionRevenant()``); the
    script's own ``GetClassPreset()`` then changes fields on it, and those
    changes are applied here -- Dage's short rotations, Darkon's cape swaps,
    Speaker's Penitence capes.  Skipping this step is how two ultras end up
    looking identical when their reference scripts are not.

    ``extras`` carries the per-ultra toggles: Speaker's Brute Force method keeps
    the presets' own ArchPaladin / Lord of Order rotations instead of the short
    ones the table names.
    """
    from dataclasses import replace

    from bot.ultra.v2.options import slot_plans
    plans = slot_plans(ultra, composition)
    if not 1 <= slot <= len(plans):
        raise KeyError(f"{ultra}: slot {slot} is outside 1-{len(plans)}")
    plan = plans[slot - 1]
    if extras and extras.get("brute_force") and ultra.lower() == "speaker":
        plan = replace(plan, skills=None)
    return plan.apply(preset_for_class(plan.cls))
