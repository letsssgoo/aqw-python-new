"""Ultra V2 -- the four-player army ultras, ported from the UltraLW scripts.

Nothing here is shared with ``bot/ultra`` (v1): v1 keeps its own hand-ported
daily/speaker fights, this package is the army engine the reference scripts use.

Layout mirrors the reference folder, minus ``Extras``::

    options.py        the form the hub renders + the composition table
    presets.py        the six class presets the allowed compositions use
    potions.py        tonics / elixirs / combat potions (shop 2036)
    scrolls.py        Enrage / Decay / Mystify stock and equipping
    enhancements.py   base / cape / helm / weapon, with the weapon fallbacks
    sync.py           step and signal helpers over ``bot.ultra.party``
    core.py           ``V2Core``: skill engine, taunt, wipeout, quest gates
    dailies/          Ezrajal, Warden, Engineer, Tyndarius
    weeklies/         Drakath, Drago, Nulgath, Dage, Darkon, Gramiel, Speaker

Only the ``Default`` / ``Stable`` / ``Reliable`` compositions are ported; the
reference's Pay2Win / Optimized / Fast / Test tables are deliberately absent.
"""
from bot.ultra.v2.core import V2Core
from bot.ultra.v2.options import UltraOptions, UltraSpec

__all__ = ["V2Core", "UltraOptions", "UltraSpec"]
