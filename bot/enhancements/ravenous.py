"""Ravenous forge enhancement -- the unlock chain from ``UnlockForgeEnhancements``.

The reference does this (``Enhancement/UnlockForgeEnhancements.cs``)::

    public void Ravenous()
    {
        if (Core.isCompletedBefore(9560))
            return;

        Core.Logger("Unlocking Enhancement: Ravenous");

        Farm.Experience();
        PFS.Storyline();

        Adv.BuyItem(Bot.Map.Name, 2411, "Gluttonous Maw");
        if (Core.CheckInventory("Gluttonous Maw"))
            Core.ChainComplete(9560);
        else
            Core.Logger(
                "Cannot complete Ravenous: Requires Gluttonous Maw, which needs "
                "10 Roentgeniums of Nulgath (daily). Try again tomorrow."
            );
    }

**What this module covers.** The last step exactly as written: buy
``Gluttonous Maw`` from shop **2411** in the current map, then accept and turn
quest **9560** in.  When the Maw cannot be bought it says the same thing the
reference says -- the daily Roentgeniums are short -- and stops.

**What it does not cover yet.** ``Farm.Experience()`` and
``PFS.Storyline()`` (``Nation/Various/PrimeFiendShard.cs``).  That storyline is
quests **9555-9559**, and each one pulls in its own farm: VHL plus
``VHLChallenge(10)``, the Void Chasm / Temple Delve / Dirtlickers / Nulgath
Diamond merge shops, ``VoidPaladin``, ``VoidSpartan``, ``SwirlingTheAbyss``,
``TradingandStuffSingle``, ``VoidRefugeMerge``, ``VoidAvengerScythe``,
``NulgathDemandsWork``, ``ArchfiendDeathLord``, ``WrathofNulgath`` and
``DilligasMerge``, plus the Nulgath material farms (Uni 13, Tainted Gem, Dark
Crystal Shard, Diamond, Totem, Gem, Blood Gem, Essence) and 10 Roentgeniums.
None of that is guessed here: the module stops and says which step is missing
rather than inventing a farm order.
"""
from __future__ import annotations

from typing import Optional

#: ``Ravenous``'s forge quest (``sQuest`` in the forge shop entry, iQSindex 544).
RAVENOUS_QUEST = 9560
#: The shop the reference buys the Maw from (``Adv.BuyItem(Bot.Map.Name, 2411…)``).
GLUTTONOUS_MAW_SHOP = 2411
GLUTTONOUS_MAW = "Gluttonous Maw"
ROENTGENIUM = "Roentgenium of Nulgath"
ROENTGENIUM_REQUIRED = 10


async def unlock(cmd) -> bool:
    """Buy the Maw and complete quest 9560, exactly like the reference."""
    if await cmd.has_item(GLUTTONOUS_MAW):
        return await _complete(cmd)

    from bot.core_bots import buy_item as core_buy
    cmd.bot.log("[forge] unlocking enhancement: Ravenous")
    # The reference buys from the map it is standing in (the storyline leaves it
    # there); no map is joined here for that reason.
    await core_buy(cmd, GLUTTONOUS_MAW_SHOP, GLUTTONOUS_MAW, 1)

    if await cmd.has_item(GLUTTONOUS_MAW):
        return await _complete(cmd)

    held = await _quantity(cmd, ROENTGENIUM)
    cmd.bot.log(
        f"[forge] cannot complete Ravenous: it needs {GLUTTONOUS_MAW}, which "
        f"needs {ROENTGENIUM_REQUIRED} {ROENTGENIUM} (daily); the account "
        f"holds {held}. Try again tomorrow.")
    return False


async def _complete(cmd) -> bool:
    """``ChainComplete(9560)``: accept the quest and turn it in."""
    if not await cmd.ensure_accept_quest(RAVENOUS_QUEST):
        cmd.bot.log(f"[forge] quest {RAVENOUS_QUEST} could not be accepted "
                    f"(already completed, or its requirements are unmet).")
        return False
    if not await cmd.ensure_turn_in_quest(RAVENOUS_QUEST):
        cmd.bot.log(f"[forge] quest {RAVENOUS_QUEST} could not be turned in.")
        return False
    cmd.bot.log("[forge] enhancement unlocked: Ravenous")
    return True


async def _quantity(cmd, name: str) -> int:
    item = cmd.bot.player.get_item_inventory(name)
    return int(getattr(item, "qty", 0) or 0) if item else 0


async def main(cmd, options: Optional[dict] = None) -> None:
    """Run the unlock standalone (``python -m bot.enhancements.ravenous``)."""
    okay = await unlock(cmd)
    if not okay:
        cmd.bot.log("[forge] Ravenous is not unlocked yet.")
