"""Option schema for Ultra V2, and the army composition of **each** ultra.

The composition is a level-style option in the reference: a dropdown whose
description lists the classes.  Here one table feeds the form, the tooltip and
the log line, so they cannot drift.

The table is **per ultra**.  Every script builds its own ``GetClassPreset()``,
and they are not the same -- Dage overrides the skill rotation of slots 2-4,
Darkon swaps cape enhancements and trims two rotations, Gramiel has no ``Stable``
column at all, Speaker forces Penitence capes and a Divine Elixir.  Those
differences are read off the reference's code, not its option text.

Only ``Default`` / ``Stable`` / ``Reliable`` are ported; the reference's Pay2Win
/ Optimized / Fast / Test tables are absent by decision.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional, Tuple

#: Wipeout retries offered in the form.  ``MaxFightAttempts`` is a constant 3 in
#: every reference script; here it is a dropdown of 1..5 with the same default.
RETRY_CHOICES: Tuple[int, ...] = (1, 2, 3, 4, 5)
DEFAULT_RETRIES = 3

#: Short names the reference's option text uses, for the tooltip.
SHORT_NAMES = {
    "Legion Revenant": "LR",
    "King's Echo": "KE",
    "Verus DoomKnight": "VDK",
    "StoneCrusher": "SC",
    "ArchPaladin": "AP",
    "Lord of Order": "LOO",
    "Dragon of Time": "DOT",
    "Shaman": "SHM",
    "Chaos Slayer Berserker": "CS",
}

LR, SC, AP, LOO, KE, VDK = ("Legion Revenant", "StoneCrusher", "ArchPaladin",
                            "Lord of Order", "King's Echo", "Verus DoomKnight")
SHAMAN = "Shaman"
DOT = "Dragon of Time"
CS = "Chaos Slayer Berserker"


@dataclass(frozen=True)
class SlotPlan:
    """One slot of one composition: a class plus what that script changes on it.

    The reference's ``GetClassPreset()`` starts from a shared ``ClassPreset``
    factory and then overrides fields per boss.  Only the overridden fields are
    named here; everything else comes from the base preset.  ``clear_cape`` /
    ``clear_helm`` exist because the reference also *removes* an enhancement
    (``CapeEnhancement = CapeSpecial.None``), which a ``None`` default cannot
    express.
    """

    cls: str
    skills: Optional[Tuple[int, ...]] = None
    mode: Optional[str] = None
    base: Optional[str] = None
    cape: Optional[str] = None
    helm: Optional[str] = None
    weapon: Optional[str] = None
    tonic: Optional[str] = None
    elixir: Optional[str] = None
    combat_potion: Optional[str] = None
    clear_cape: bool = False
    clear_helm: bool = False

    def apply(self, preset):
        """Return the base preset with this slot's overrides applied."""
        changes = {key: value for key, value in (
            ("skills", self.skills), ("mode", self.mode), ("base", self.base),
            ("cape", self.cape), ("helm", self.helm), ("weapon", self.weapon),
            ("tonic", self.tonic), ("elixir", self.elixir),
            ("combat_potion", self.combat_potion),
        ) if value is not None}
        if self.clear_cape:
            changes["cape"] = None
        if self.clear_helm:
            changes["helm"] = None
        return replace(preset, **changes)


def _standard(slot_one: Optional[SlotPlan] = None,
              stable: Optional[SlotPlan] = None,
              reliable: Optional[SlotPlan] = None) -> Dict[str, Tuple[SlotPlan, ...]]:
    """The row most ultras share: ``s1 / SC / AP / LOO``, KE on Stable."""
    return {
        "Default": (slot_one or SlotPlan(LR), SlotPlan(SC), SlotPlan(AP),
                    SlotPlan(LOO)),
        "Stable": (stable or SlotPlan(KE), SlotPlan(SC), SlotPlan(AP),
                   SlotPlan(LOO)),
        "Reliable": (reliable or SlotPlan(VDK), SlotPlan(SC), SlotPlan(AP),
                     SlotPlan(LOO)),
    }


#: ``ultra -> composition -> (slot 1..4)``.  Read off each script's
#: ``GetClassPreset()``; anything not listed keeps the base preset factory.
COMPOSITIONS: Dict[str, Dict[str, Tuple[SlotPlan, ...]]] = {
    # --- daily ultras ---------------------------------------------------
    "warden": _standard(),
    "ezrajal": _standard(
        # Stable's King's Echo goes without a cape in this fight
        # (`preset.CapeEnhancement = CapeSpecial.None`).
        stable=SlotPlan(KE, clear_cape=True),
    ),
    "engineer": _standard(),
    # Tyndarius' Fast column is not ported.  Its Lord of Order wears Valiance
    # instead of the preset's Awe Blast; the other three slots are standard.
    "tyndarius": {
        "Default": (SlotPlan(LR), SlotPlan(SC), SlotPlan(AP),
                    SlotPlan(LOO, weapon="Valiance")),
        "Stable": (SlotPlan(KE), SlotPlan(SC), SlotPlan(AP),
                   SlotPlan(LOO, weapon="Valiance")),
        "Reliable": (SlotPlan(VDK), SlotPlan(SC), SlotPlan(AP),
                     SlotPlan(LOO, weapon="Valiance")),
    },
    # --- weeklies -------------------------------------------------------
    # Drakath's capes are the script's own: the ArchPaladin always wears
    # Penitence, slot 1 wears Penitence on Default/Reliable, and Stable's
    # King's Echo trades Vainglory for Lament.
    "drakath": {
        "Default": (SlotPlan(LR, cape="Penitence"), SlotPlan(SC),
                    SlotPlan(AP, cape="Penitence"), SlotPlan(LOO)),
        "Stable": (SlotPlan(KE, cape="Lament"), SlotPlan(SC),
                   SlotPlan(AP, cape="Penitence"), SlotPlan(LOO)),
        "Reliable": (SlotPlan(VDK, cape="Penitence"), SlotPlan(SC),
                     SlotPlan(AP, cape="Penitence"), SlotPlan(LOO)),
        # Optimized swaps slot 1 for Chaos Slayer; the cape rule still applies.
        "Optimized": (SlotPlan(CS, cape="Lament"), SlotPlan(SC),
                      SlotPlan(AP, cape="Penitence"), SlotPlan(LOO)),
    },
    "drago": _standard(),
    "nulgath": {
        "Default": (SlotPlan(LR), SlotPlan(SC), SlotPlan(AP), SlotPlan(LOO)),
        "Stable": (SlotPlan(KE), SlotPlan(SC), SlotPlan(AP), SlotPlan(LOO)),
        "Reliable": (SlotPlan(VDK), SlotPlan(SC), SlotPlan(AP),
                     SlotPlan(LOO)),
        # Optimized runs two Dragons of Time and moves the Legion Revenant to
        # slot 3.  Fast is not ported: its Arcana Invoker needs the reference's
        # own skill engine, which this port does not have.
        "Optimized": (SlotPlan(DOT), SlotPlan(DOT), SlotPlan(LR),
                      SlotPlan(LOO)),
    },
    # Dage overrides the rotations of slots 2-4 (and slot 1 restates LR's own).
    "dage": {
        # Every pane wears Health Vamp with Vainglory: the script overrides the
        # class presets, and Dage is won on that weapon's healing.
        "Default": (SlotPlan(LR, skills=(3, 4, 2, 1), weapon="Health Vamp",
                             cape="Vainglory"),
                    SlotPlan(SC, skills=(2, 4, 1), weapon="Health Vamp",
                             cape="Vainglory"),
                    SlotPlan(AP, skills=(3, 1, 4), weapon="Health Vamp",
                             cape="Vainglory"),
                    SlotPlan(LOO, skills=(3, 1, 4), weapon="Health Vamp",
                             cape="Vainglory")),
        "Stable": (SlotPlan(KE, weapon="Health Vamp", cape="Vainglory"),
                   SlotPlan(SC, skills=(2, 4, 1), weapon="Health Vamp",
                            cape="Vainglory"),
                   SlotPlan(AP, skills=(3, 1, 4), weapon="Health Vamp",
                            cape="Vainglory"),
                   SlotPlan(LOO, skills=(3, 1, 4), weapon="Health Vamp",
                            cape="Vainglory")),
        "Reliable": (SlotPlan(VDK, weapon="Health Vamp", cape="Vainglory"),
                     SlotPlan(SC, skills=(2, 4, 1), weapon="Health Vamp",
                              cape="Vainglory"),
                     SlotPlan(AP, skills=(3, 1, 4), weapon="Health Vamp",
                              cape="Vainglory"),
                     SlotPlan(LOO, skills=(3, 1, 4), weapon="Health Vamp",
                              cape="Vainglory")),
    },
    # Darkon: Lament is substituted by Penitence, Absolution on the two
    # support slots, and slots 3-4 fight on short rotations.
    "darkon": {
        "Default": (SlotPlan(LR, cape="Penitence"),
                    SlotPlan(SC, cape="Absolution"),
                    SlotPlan(AP, skills=(3, 1, 4), cape="Penitence"),
                    SlotPlan(LOO, skills=(3, 1), cape="Absolution")),
        "Stable": (SlotPlan(KE, cape="Penitence", helm="Forge"),
                   SlotPlan(SC, cape="Absolution"),
                   SlotPlan(AP, skills=(3, 1, 4), cape="Penitence"),
                   SlotPlan(LOO, skills=(3, 1), cape="Absolution")),
        "Reliable": (SlotPlan(VDK, cape="Penitence"),
                     SlotPlan(SC, cape="Absolution"),
                     SlotPlan(AP, skills=(3, 1, 4), cape="Penitence"),
                     SlotPlan(LOO, skills=(3, 1), cape="Absolution")),
    },
    # Gramiel has no Stable column: slot 1 is LR in both of its compositions.
    "gramiel": {
        "Default": (SlotPlan(LR, skills=(3, 4, 2), cape="Penitence"),
                    SlotPlan(SC),
                    SlotPlan(AP, cape="Penitence"),
                    SlotPlan(LOO)),
        # Optimized runs a Shaman on slot 1: Wizard base, Elysium, Absolution,
        # and its own Sage/Malevolence potions.
        "Optimized": (SlotPlan(SHAMAN, base="Wizard", cape="Absolution",
                               weapon="Elysium", tonic="Sage Tonic",
                               elixir="Potent Malevolence Elixir"),
                      SlotPlan(SC),
                      SlotPlan(AP, cape="Penitence"),
                      SlotPlan(LOO)),
        "Reliable": (SlotPlan(VDK),
                     SlotPlan(SC),
                     SlotPlan(AP, cape="Penitence"),
                     SlotPlan(LOO)),
    },
    # Speaker: Penitence everywhere, LR without a helm, StoneCrusher on the
    # Divine Elixir, and two short rotations (2,1 / 2,3,1) for the non-brute
    # force method -- Brute Force restores the presets' own rotations, which the
    # Speaker module applies when the option is on.
    "speaker": {
        "Default": (SlotPlan(LR, cape="Penitence", clear_helm=True),
                    SlotPlan(SC, cape="Penitence", elixir="Divine Elixir"),
                    SlotPlan(AP, skills=(2, 1), cape="Penitence"),
                    SlotPlan(LOO, skills=(2, 3, 1))),
        "Reliable": (SlotPlan(VDK, cape="Penitence"),
                     SlotPlan(SC, cape="Penitence", elixir="Divine Elixir"),
                     SlotPlan(AP, skills=(2, 1), cape="Penitence"),
                     SlotPlan(LOO, skills=(2, 3, 1))),
    },
}


def slot_plans(ultra: str, composition: str) -> Tuple[SlotPlan, ...]:
    """The four slot plans for one ultra's composition."""
    table = COMPOSITIONS.get(ultra.lower())
    if table is None:
        raise KeyError(f"{ultra!r} is not a ported ultra")
    if composition not in table:
        raise KeyError(f"{ultra}: composition {composition!r} is not ported; "
                       f"pick one of {', '.join(table)}")
    return table[composition]


def compositions(ultra: str) -> Dict[str, Tuple[str, ...]]:
    """``{composition: (class per slot 1..4)}`` for one ultra, in display order."""
    return {name: tuple(plan.cls for plan in plans)
            for name, plans in COMPOSITIONS[ultra.lower()].items()}


def composition_tooltip(ultra: str) -> str:
    """The text under the composition dropdown, e.g. ``Default: LR / SC / AP / LOO``."""
    lines = []
    for name, slots in compositions(ultra).items():
        short = " / ".join(SHORT_NAMES.get(cls, cls) for cls in slots)
        lines.append(f"{name}: {short}")
    return "\n".join(lines)


@dataclass(frozen=True)
class UltraSpec:
    """What one ultra is: where, which quest, and how the fight is shaped.

    Attributes:
        id: Short key used for the config file, the menu and the sync session
            (``"warden"``).
        title: Display name (``"Ultra Warden"``).
        quest: The ultra's daily quest.
        prereq_quest: Quest that must be completed first; the reference refuses
            the run (and says so) rather than fighting behind a locked door.
        prereq_name: That quest's name, quoted in the message.
        min_level: Character level gate.
        map: Map the boss lives in.
        safe_cell, safe_pad: Where the party regroups between attempts.
        boss_cell, boss_pad: Where the boss is pulled from.
        monster_id: The boss's ``MonMapID`` (targets are ``id.N``).
        taunt_hp: HP at which the taunter is asked for skill 5; ``0`` = no taunt.
        extra_options: Per-ultra toggles on top of the shared form, each a dict
            with ``key``, ``label``, ``help`` and ``default``.
    """

    id: str
    title: str
    quest: int
    prereq_quest: int
    prereq_name: str
    min_level: int
    map: str
    safe_cell: str = "Enter"
    safe_pad: str = "Spawn"
    boss_cell: str = "r2"
    boss_pad: str = "Left"
    monster_id: int = 1
    taunt_hp: int = 0
    extra_options: Tuple[Dict[str, Any], ...] = ()

    @property
    def key(self) -> str:
        """Config / sync / menu key, e.g. ``ultra_v2_warden``."""
        return f"ultra_v2_{self.id}"

    def describe(self) -> str:
        return f"{self.title} (quest {self.quest}, /{self.map})"


@dataclass
class UltraOptions:
    """The values the form holds.  Defaults match the reference script."""

    composition: str = "Default"
    players: Tuple[str, str, str, str] = ("", "", "", "")
    private_room: int = 0
    use_potions: bool = True
    use_enhancements: bool = True
    retries: int = DEFAULT_RETRIES
    #: Per-ultra toggles (Ezrajal's ``SkipManaLock``, Speaker's brute force).
    extras: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "UltraOptions":
        data = dict(data or {})
        players = data.get("players") or []
        padded = [str(name or "") for name in players][:4]
        while len(padded) < 4:
            padded.append("")
        return cls(
            composition=str(data.get("composition") or "Default"),
            players=tuple(padded),                     # type: ignore[arg-type]
            private_room=int(data.get("private_room") or 0),
            use_potions=bool(data.get("use_potions", True)),
            use_enhancements=bool(data.get("use_enhancements", True)),
            retries=int(data.get("retries") or DEFAULT_RETRIES),
            extras=dict(data.get("extras") or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "composition": self.composition,
            "players": list(self.players),
            "private_room": self.private_room,
            "use_potions": self.use_potions,
            "use_enhancements": self.use_enhancements,
            "retries": self.retries,
            "extras": dict(self.extras),
        }


def validate(spec: UltraSpec, options: UltraOptions) -> List[str]:
    """Everything wrong with the form, as sentences the GUI can show as-is."""
    problems: List[str] = []
    if options.composition not in compositions(spec.id):
        allowed = ", ".join(compositions(spec.id))
        problems.append(f"{spec.title}: composition {options.composition!r} is "
                        f"not ported; pick one of {allowed}.")
    if options.retries not in RETRY_CHOICES:
        problems.append(f"{spec.title}: wipeout retries must be one of "
                        f"{', '.join(str(n) for n in RETRY_CHOICES)}.")
    if options.private_room and not (1001 <= options.private_room <= 99999):
        problems.append(f"{spec.title}: a private room number is 1001-99999 "
                        f"(or 0 for the public map).")
    missing = [str(i + 1) for i, name in enumerate(options.players) if not name.strip()]
    if missing:
        problems.append(f"{spec.title}: fill the account for slot "
                        f"{', '.join(missing)}.")
    return problems


def schema(spec: UltraSpec) -> List[Dict[str, Any]]:
    """The form for one ultra, as plain dicts the hub can render and post back."""
    fields: List[Dict[str, Any]] = [
        {
            "key": "players",
            "label": "Army players",
            "type": "players",
            "help": "One account per slot.  Slot 1 is the leader and follows "
                    "the party's sync order.",
            "count": 4,
        },
        {
            "key": "composition",
            "label": "Army Composition",
            "type": "select",
            "help": composition_tooltip(spec.id),
            "choices": [
                {"value": name, "label": name, "help": " / ".join(slots)}
                for name, slots in compositions(spec.id).items()
            ],
            "default": "Default",
        },
        {
            "key": "private_room",
            "label": "Private Room Number",
            "type": "int",
            "help": "Private room from 1001 through 99999; 0 uses the public map.",
            "default": 0,
            "min": 0,
            "max": 99999,
        },
        {
            "key": "use_potions",
            "label": "Use Potions",
            "type": "bool",
            "help": "Prepare and use the composition's tonic / elixir / combat "
                    "potion (shop 2036).",
            "default": True,
        },
        {
            "key": "use_enhancements",
            "label": "Use Enhancements",
            "type": "bool",
            "help": "Wear the composition's base / cape / helm / weapon "
                    "enhancements.  A missing one stops the run by name.",
            "default": True,
        },
        {
            "key": "retries",
            "label": "Wipeout retries",
            "type": "select",
            "help": "How many fight attempts the party makes before giving up "
                    "and stopping (the reference hardcodes 3).",
            "choices": [{"value": n, "label": str(n)} for n in RETRY_CHOICES],
            "default": DEFAULT_RETRIES,
        },
    ]
    for extra in spec.extra_options:
        fields.append(dict(extra, type=extra.get("type", "bool")))
    return fields
