"""Option schema for Ultra V2: one table feeding the form, the tooltip and the log.

The army composition is a *level-style* option in the reference (a dropdown with
a description that lists the four classes).  Here the same data drives three
places so they cannot drift apart:

* the GUI form the hub renders (:func:`schema`),
* the tooltip text under the composition dropdown (:func:`composition_tooltip`),
* the line a run prints when it starts (:meth:`V2Core.describe`).

Only ``Default`` / ``Stable`` / ``Reliable`` exist -- the reference's other
compositions are out of scope by decision, not by accident.
"""
from __future__ import annotations

from dataclasses import dataclass, field
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
}

#: The three class columns, in slot order (1..4).
DEFAULT_SLOTS = ("Legion Revenant", "StoneCrusher", "ArchPaladin", "Lord of Order")
STABLE_SLOTS = ("King's Echo", "StoneCrusher", "ArchPaladin", "Lord of Order")
RELIABLE_SLOTS = ("Verus DoomKnight", "StoneCrusher", "ArchPaladin", "Lord of Order")

#: Ultras whose reference script never had a ``Stable`` column.
NO_STABLE = {"speaker"}


def compositions(ultra: str) -> Dict[str, Tuple[str, ...]]:
    """``{composition: (class per slot 1..4)}`` for one ultra, in display order."""
    table: Dict[str, Tuple[str, ...]] = {"Default": DEFAULT_SLOTS}
    if ultra.lower() not in NO_STABLE:
        table["Stable"] = STABLE_SLOTS
    table["Reliable"] = RELIABLE_SLOTS
    return table


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
