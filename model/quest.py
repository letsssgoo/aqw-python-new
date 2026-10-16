"""One quest, as sent by ``getQuests``.

Wire format (``{"t":"xt","b":{"r":-1,"o":{"cmd":"getQuests","quests":{...}}}}``):
the server sends one object per quest, carrying the quest's chain position, its
turn-in requirements, and its rewards-on-turn-in metadata::

    QuestID  iSlot  iValue  sName  sDesc  sEndText  bOnce  sField  iIndex
    bUpg  iLvl  iClass  iReqCP  FactionID  iReqRep  iGold  iExp
    reqd  oItems  turnin  reward  oRewards

``turnin``
    What the bot actually reads: ``[{"ItemID": ..., "iQty": ...}, ...]``.  It is
    ``oItems`` with the quantities inlined, which is why ``Bot.can_turn_in_quest``
    walks it to decide whether the quest can be completed right now.

``reqd``
    Items consumed when the quest is *accepted* (e.g. the pet a merge quest
    requires).  The live payload calls this ``reqd``; the reference bot's reconstructed
    shape calls it ``oReqd``, so both are read.

``reward`` / ``oRewards``
    The turn-in rewards.  ``reward`` is a light array of
    ``{ItemID, iQty, iType, iRate}``; ``oRewards.itemsC`` holds the same
    rewards as full item objects, **with names**.  ``iType == 2`` marks a
    choice entry -- a quest that makes you pick one reward instead of paying
    all of them.

``bOnce`` / ``sField``
    A quest that is one-time only, or that carries a ``field`` marker, can be
    turned in exactly once no matter how many requirements are banked.  That
    rule lives in :attr:`needs_single_turn_in` (the reference bot's
    ``EnsureCompleteMulti`` open-codes the same test).

``iSlot`` / ``iValue``
    Chain position: a quest is unlocked once the *completed* quest sharing its
    ``iSlot`` has a lower ``iValue``.  the reference bot additionally reads the live slot
    value through ``world.getQuestValue`` -- a client-side call this engine does
    not have.  The static pair is still enough to order a chain.

**Why this is a dict:** ``bot.loaded_quest_datas`` is walked as a mapping in
``core/``, ``commands/`` and ``handlers/`` -- ``loaded_quest["QuestID"]``,
``loaded_quest["turnin"]``.  Subclassing ``dict`` gives typed accessors to new
code while leaving every one of those call sites untouched, which is the same
reason ``model.skill.Skill`` subclasses ``dict``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _int(value: Any, default: int = 0) -> int:
    """``int()`` that tolerates the empty string and ``None`` the payload uses."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _flag(value: Any) -> bool:
    """Read a ``bOnce``/``bUpg``-style flag.

    The payload sends ``"1"``/``"0"``; a real ``bool`` and a JSON ``true`` are
    both accepted so a future change of shape cannot flip the meaning.
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() not in ("", "0", "false")


def _as_list(value: Any) -> List[Dict[str, Any]]:
    """Normalise ``oItems``/``oReqd``/``turnin`` into a list of dicts.

    ``oItems`` and ``oReqd`` arrive keyed by item id; ``turnin`` arrives as a
    plain array.  Both shapes appear here, so both are accepted.
    """
    if isinstance(value, dict):
        return [item for item in value.values() if isinstance(item, dict)]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _collect_items(value: Any, depth: int = 0) -> List[Dict[str, Any]]:
    """Every item-shaped mapping under ``value``, however it is nested.

    ``oRewards`` is not shaped the same way on every quest: quest 870 sends
    ``{"itemsC": {"0": {...}}}``, while others put the items straight in the
    container or send an array.  Walking the value instead of guessing the
    wrapper means all of those read the same -- and an item is recognised by
    carrying ``ItemID`` or ``sName``, so a wrapper key is never mistaken for
    one.
    """
    if depth > 4:
        return []
    if isinstance(value, dict):
        if "ItemID" in value or "sName" in value:
            return [value]
        found: List[Dict[str, Any]] = []
        for item in value.values():
            found.extend(_collect_items(item, depth + 1))
        return found
    if isinstance(value, list):
        found = []
        for item in value:
            found.extend(_collect_items(item, depth + 1))
        return found
    return []


def normalize_quest_id(value: Any) -> int:
    """A quest id as an ``int``, or ``0`` when it cannot be read as one.

    Ids arrive as **strings** off the wire (``{"QuestID": "870"}``) and as
    **ints** from scripts, config and command classes.  Comparing the two
    directly never matches, which is why callers used to fall back on
    ``str(quest_id) in str(loaded_quest_ids)`` -- a substring test that happily
    equates ``443`` with ``4432``.  Normalising once, at the boundary, lets
    every comparison be ``int == int``.

    ``0`` is safe as the "not a quest" value: no real quest has that id, and
    ``get_loaded_quest`` refuses it.
    """
    return _int(value)


class Quest(dict):
    """A quest: dict-compatible, with named accessors over it."""

    # --- identity -----------------------------------------------------
    @property
    def quest_id(self) -> int:
        """``QuestID`` -- the id every packet and command keys on."""
        return _int(self.get("QuestID"))

    @property
    def name(self) -> str:
        return str(self.get("sName") or "")

    @property
    def description(self) -> str:
        return str(self.get("sDesc") or "")

    @property
    def end_text(self) -> str:
        return str(self.get("sEndText") or "")

    # --- chain position ------------------------------------------------
    @property
    def slot(self) -> int:
        """``iSlot`` -- the chain this quest belongs to."""
        return _int(self.get("iSlot"))

    @property
    def value(self) -> int:
        """``iValue`` -- the slot value this quest waits for."""
        return _int(self.get("iValue"))

    @property
    def index(self) -> int:
        return _int(self.get("iIndex"))

    @property
    def field(self) -> str:
        """``sField`` -- one-time-ish marker; non-empty blocks repeat turn-ins."""
        return str(self.get("sField") or "")

    # --- flags ---------------------------------------------------------
    @property
    def is_once(self) -> bool:
        """``bOnce`` -- the quest can be completed only one time per character."""
        return _flag(self.get("bOnce"))

    @property
    def is_upgrade(self) -> bool:
        """``bUpg`` -- members-only quest."""
        return _flag(self.get("bUpg"))

    @property
    def needs_single_turn_in(self) -> bool:
        """True when the quest may be turned in exactly once per accept.

        the reference bot's ``EnsureCompleteMulti`` uses this to skip asking the client how
        many turn-ins are possible: a ``once`` quest, or one carrying a
        ``field``, always completes in a single turn-in.
        """
        return self.is_once or bool(self.field)

    # --- requirements --------------------------------------------------
    @property
    def turn_in_requirements(self) -> List[Dict[str, Any]]:
        """Raw ``turnin`` entries, as sent.  Safe to iterate; never ``None``."""
        return _as_list(self.get("turnin"))

    @property
    def accept_requirements(self) -> List[Dict[str, Any]]:
        """``reqd`` -- items consumed when the quest is *accepted*.

        The live payload calls this ``reqd``; the shape the reference bot's
        ``QuestPacketCollector`` reconstructs calls it ``oReqd``.  Both are
        read, so the model works against either.
        """
        return _as_list(self.get("reqd") or self.get("oReqd"))

    @property
    def items(self) -> List[Dict[str, Any]]:
        """``oItems`` -- the requirement item objects, with quantities."""
        return _as_list(self.get("oItems"))

    @property
    def turn_in_items(self) -> List[Tuple[int, int]]:
        """``turnin`` as ``[(item_id, qty), ...]``, skipping unusable rows.

        The normalised form every caller wants: the raw entries carry
        ``ItemID``/``iQty`` as strings, and an entry missing either is dropped
        rather than raising.
        """
        pairs: List[Tuple[int, int]] = []
        for entry in self.turn_in_requirements:
            item_id = _int(entry.get("ItemID"), -1)
            if item_id < 0:
                continue
            pairs.append((item_id, _int(entry.get("iQty"), 1) or 1))
        return pairs

    def requirements_met(self, player) -> bool:
        """True when ``player`` holds every ``turnin`` requirement right now.

        The inventory *and* the temp inventory are checked, because quest
        progress items land in the temp one.  A malformed requirement counts as
        unmet rather than raising -- a quest whose data cannot be read must not
        look completable.
        """
        for item_id, qty in self.turn_in_items:
            item = (player.get_item_inventory_by_id(item_id)
                    or player.get_item_temp_inventory_by_id(item_id))
            if not item or _int(item.qty) < qty:
                return False
        return True

    # --- rewards-on-turn-in metadata -----------------------------------
    @property
    def gold(self) -> int:
        """``iGold`` -- gold granted on turn-in."""
        return _int(self.get("iGold"))

    @property
    def exp(self) -> int:
        """``iExp`` -- experience granted on turn-in."""
        return _int(self.get("iExp"))

    @property
    def reward_items(self) -> List[Dict[str, Any]]:
        """Full reward item objects, from ``oRewards``.

        These carry ``sName``, which is what :attr:`reward_names` reads.  The
        lighter :attr:`rewards` array beside them has the quantities and the
        choice flag but no names.  ``oRewards`` is nested differently from
        quest to quest, so it is walked rather than indexed.
        """
        return _collect_items(self.get("oRewards"))

    @property
    def rewards(self) -> List[Dict[str, Any]]:
        """Raw ``reward`` array: ``{ItemID, iQty, iType, iRate}`` rows."""
        return _as_list(self.get("reward"))

    @property
    def reward_names(self) -> List[str]:
        """Reward item names, in payload order; ``[]`` when none are sent.

        The port of the reference bot's ``Core.QuestRewards``, with one
        difference that matters: that one reads a client-side quest cache,
        while this reads the live ``getQuests`` payload -- which carries the
        names under ``oRewards``.  Not every quest sends that block, so an
        empty list can mean "no rewards" *or* "this payload named none"; see
        :attr:`reward_ids` to tell the two apart.
        """
        return [str(item["sName"]) for item in self.reward_items if item.get("sName")]

    @property
    def reward_ids(self) -> List[int]:
        """Reward item ids from the light ``reward`` array.

        Present on quests that ship no ``oRewards`` block, which is how a
        caller can say "there are rewards, they just have no names here".
        """
        ids = (_int(row.get("ItemID"), -1) for row in self.rewards)
        return [item_id for item_id in ids if item_id >= 0]

    @property
    def reward_entries(self) -> List[Tuple[int, str, int]]:
        """Rewards as ``(item_id, name, max_stack)``.

        Both halves of the payload are needed: ``oRewards.itemsC`` carries the
        name and ``iStk`` -- the max stack -- which is what a "farm until full"
        loop compares against.  A row missing its id or its name is skipped
        rather than yielding a half-usable entry.
        """
        entries: List[Tuple[int, str, int]] = []
        for item in self.reward_items:
            item_id = _int(item.get("ItemID"), -1)
            name = str(item.get("sName") or "")
            if item_id < 0 or not name:
                continue
            entries.append((item_id, name, _int(item.get("iStk"), 1) or 1))
        return entries

    @property
    def is_choice_reward(self) -> bool:
        """True when the quest makes you pick one reward instead of paying all.

        ``iType == 2`` marks a choice entry -- the same flag the reference bot's
        ``SimpleRewards`` uses to populate ``ChoiceRewardQuestIDs``.
        """
        return any(_int(row.get("iType")) == 2 for row in self.rewards)

    @property
    def faction_name(self) -> str:
        """``sFaction`` -- the faction this quest pays reputation into."""
        return str(self.get("sFaction") or "")

    @property
    def rep(self) -> int:
        """``iRep`` -- reputation granted on turn-in."""
        return _int(self.get("iRep"))

    # --- requirements to accept ----------------------------------------
    @property
    def level(self) -> int:
        return _int(self.get("iLvl"))

    @property
    def required_class_id(self) -> int:
        return _int(self.get("iClass"))

    @property
    def required_class_points(self) -> int:
        return _int(self.get("iReqCP"))

    @property
    def faction_id(self) -> int:
        return _int(self.get("FactionID"))

    @property
    def required_faction_rep(self) -> int:
        return _int(self.get("iReqRep"))

    # --- construction / display ----------------------------------------
    @classmethod
    def from_payload(cls, data: Optional[Dict[str, Any]]) -> "Quest":
        """Copy one ``getQuests`` entry into a Quest, dropping nothing.

        The raw keys stay in the mapping, so ``quest["QuestID"]`` and
        ``quest["turnin"]`` keep working for existing callers.
        """
        return cls(data or {})

    def describe(self) -> str:
        bits = [f"[{self.quest_id}]"]
        if self.name:
            bits.append(f'"{self.name}"')
        if self.slot:
            bits.append(f"slot {self.slot}/{self.value}")
        if self.needs_single_turn_in:
            bits.append("once" if self.is_once else f"field {self.field!r}")
        reqs = ", ".join(f"{item_id}x{qty}" for item_id, qty in self.turn_in_items)
        if reqs:
            bits.append(f"needs {reqs}")
        names = self.reward_names
        if names:
            shown = ", ".join(names[:3]) + ("..." if len(names) > 3 else "")
            bits.append(("choice: " if self.is_choice_reward else "reward: ") + shown)
        return " ".join(bits)

    def __str__(self) -> str:  # pragma: no cover - display helper
        return f"<Quest {self.describe()}>"
