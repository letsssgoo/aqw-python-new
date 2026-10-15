"""``CoreAdvanced`` -- the core that re-implements several of ``CoreBots``' names.

Port of ``CoreAdvanced.cs``, and it matters *which* of the two a kit meant: the
reference's cores do not inherit from one another (there is no
``class CoreAdvanced : CoreBots``), so ``Adv.BuyItem`` and ``Core.BuyItem`` are two
separate methods that happen to share a name.  Only the ``CoreAdvanced`` one runs
``GetItemReq``, which farms what a shop entry asks for before the purchase.

Mapping a kit's ``Adv.X`` onto our ``CoreBots`` equivalent is therefore unsound --
that is exactly how Master Ranger's Sandsea requirement went missing -- so
everything a kit calls as ``Adv.`` lives here.

Ported so far:

========================  ==============================================
``buy_item``              ``CoreAdvanced.BuyItem``: the CoreBots purchase
                          plus ``GetItemReq``
``meet_shop_requirements`` ``CoreAdvanced.GetItemReq``: reputation, level, gold
========================  ==============================================

Still reported rather than faked, because the engine has no counterpart:
``SmartEnhance``, ``GearStore``, ``RankUpClass``, ``HasMinimalBoost`` and
``StartBuyAllMerge`` (the merge framework, which also owns ``GetItemReq``'s Gold
Voucher and merge-item steps).
"""
from typing import Optional, Union

from bot.core_bots import load_shop_entry, points_to_level
from bot.core_farms import farm_experience, farm_faction, farm_gold
from core.command import Command

#: ``GetItemReq`` caps its gold farm here (``Math.Min(cost * quant, 100000000)``).
GOLD_FARM_CAP = 100_000_000


async def meet_shop_requirements(cmd: Command, entry, qty: int = 1) -> None:
    """``CoreAdvanced.GetItemReq``: farm what a shop entry needs before buying.

    The reference runs this inside ``_BuyItem``, and it is what makes
    ``Adv.BuyItem`` work at all for an entry behind a faction: reputation first,
    then player level, then gold.  Its Gold Voucher and merge-item steps belong to
    ``StartBuyAllMerge``'s dependency walk, which is not ported.

    A faction this engine has no farm for is reported by ``farm_faction`` rather
    than quietly skipped -- the purchase would fail at the server either way.
    """
    faction = str(getattr(entry, "required_faction", "None") or "None").strip()
    required_rep = int(getattr(entry, "required_rep", 0) or 0)
    if faction and faction.lower() != "none" and required_rep > 0:
        rank = points_to_level(required_rep)
        if rank > cmd.get_faction_rank(faction):
            cmd.bot.log(f"Farming reputation for {faction} "
                        f"(Required: {required_rep})")
            await farm_faction(cmd, faction, rank)

    required_level = int(getattr(entry, "level", 0) or 0)
    if required_level > (cmd.get_player().LEVEL or 0):
        cmd.bot.log(f"Farming experience to reach level {required_level}")
        await farm_experience(cmd, min(required_level, 100))

    cost = int(getattr(entry, "cost", 0) or 0)
    if cost > 0 and not getattr(entry, "is_acs", False):
        await farm_gold(cmd, min(cost * qty, GOLD_FARM_CAP))


async def buy_item(cmd: Command, shop_id: int, item: Union[int, str],
                   qty: int = 1, map_name: Optional[str] = None,
                   shop_item_id: int = 0) -> bool:
    """``CoreAdvanced.BuyItem``: ``CoreBots.BuyItem`` plus ``GetItemReq``.

    Same arguments and the same reporting as :func:`bot.core_bots.buy_item`; the
    difference is that the entry's own requirements are farmed first.  A kit that
    the reference calls ``Adv.BuyItem`` from has to come through here.
    """
    if isinstance(item, int) and await cmd.has_item_id(item):
        return True

    entry = await load_shop_entry(cmd, shop_id, item, map_name, shop_item_id)
    if entry is None:
        return False

    await meet_shop_requirements(cmd, entry, qty)
    await cmd.buy_item(shop_id, entry.item_name, qty,
                       shop_item_id=entry.shop_item_id)
    return True
