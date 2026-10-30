"""The daily-rotating ultras: Ezrajal, Warden, Engineer, Tyndarius.

Only Warden is ported so far; the rest join this folder as they land, and
``__all__`` is what the "run all" page and the tests walk.
"""
from bot.ultra.v2.dailies import warden

__all__ = ["warden"]
