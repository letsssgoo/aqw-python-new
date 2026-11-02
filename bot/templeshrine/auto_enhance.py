"""Wear the V2 class preset's enhancements on a Temple/Eclipse pane.

The class comes from the menu as free text, so it may be any class the account
owns.  When it matches a V2 preset the preset's class/weapon/cape/helm
enhancements are applied through the same code the ultra menus use; a class
with no preset is left exactly as it is -- the pane still wears it, it just
gets no automatic enhancement.
"""
from __future__ import annotations

from bot.ultra.v2 import enhancements, presets


async def apply(cmd, class_name: str) -> bool:
    """Apply the class preset's enhancements; never stops the pane."""
    name = (class_name or "").strip()
    if not name:
        return True
    try:
        preset = presets.preset_for_class(name)
    except KeyError:
        cmd.bot.log(f"[temple] no enhancement preset for {name!r}; the gear is "
                    f"left as it is.")
        return True

    cmd.bot.log(f"[temple] {preset.cls} enhancements: "
                f"{enhancements.describe(preset)}.")
    try:
        applied = await enhancements.prepare(cmd, preset)
    except Exception as error:
        cmd.bot.log(f"[temple] the {preset.cls} enhancement pass failed "
                    f"({error}); the gear is left as it is.")
        return False
    if not applied:
        cmd.bot.log(f"[temple] a {preset.cls} enhancement is missing; the pane "
                    f"keeps what it has.")
    return bool(applied)
