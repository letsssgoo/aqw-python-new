"""Which Ultra V2 fights exist, and how the hub builds one.

One entry per ported ultra: its :class:`~bot.ultra.v2.options.UltraSpec` and the
runner class.  Adding the next ultra means adding a module and one line here --
the menu, the config file and the "run all" page all read this registry.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple, Type

from bot.ultra.v2.dailies import engineer, ezrajal, warden
from bot.ultra.v2.options import UltraOptions, UltraSpec

#: ``ultra id -> (spec, runner class)``.
REGISTRY: Dict[str, Tuple[UltraSpec, Type[Any]]] = {
    "warden": (warden.SPEC, warden.UltraWarden),
    "ezrajal": (ezrajal.SPEC, ezrajal.UltraEzrajal),
    "engineer": (engineer.SPEC, engineer.UltraEngineer),
}

#: Menu order: dailies first, weeklies after (as they land).
ORDER: Tuple[str, ...] = ("warden", "ezrajal", "engineer")


def spec(ultra: str) -> UltraSpec:
    """The spec for one ultra id, or ``KeyError`` with the ported list."""
    try:
        return REGISTRY[ultra][0]
    except KeyError:
        raise KeyError(f"{ultra!r} is not a ported ultra; ported: "
                       f"{', '.join(ORDER)}") from None


def build_runner(ultra: str, cmd, slot: int,
                 options: UltraOptions):
    """Construct one pane's runner for the hub or a standalone launch."""
    try:
        runner = REGISTRY[ultra][1]
    except KeyError:
        raise KeyError(f"{ultra!r} is not a ported ultra; ported: "
                       f"{', '.join(ORDER)}") from None
    return runner(cmd, options, slot)
