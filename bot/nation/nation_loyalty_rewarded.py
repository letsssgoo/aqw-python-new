"""Farm the Nation Loyalty Rewarded quest (4749).

Port of ``Nation/NationLoyaltyRewarded.cs``.

``FARM_ITEMS``:
  * ``None`` -- max every reward quest 4749 offers
  * a list of names -- e.g. ``["Diamond of Nulgath", "Dark Crystal Shard"]``

The names must be quest 4749 rewards; the exact list only exists once the quest
is accepted, which is why ``None`` is the safe choice.
"""
from core.command import Command
from bot.nation.core_nation import nation_loyalty_rewarded

#: ``None`` for all of them, or a list of quest 4749 reward names.
FARM_ITEMS = None
QUANTITY = 0        # 0 = pakai max stack masing-masing reward


async def main(cmd: Command):
    await nation_loyalty_rewarded(cmd, FARM_ITEMS, QUANTITY)
