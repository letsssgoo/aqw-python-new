"""Prime Fiend Shard storyline -- ``Nation/Various/PrimeFiendShard.cs``.

Quests **9555-9559** raise the Prime Fiend Shard.  This port is being filled in
in the reference's own order, and every step that is not ported yet stops the
run by name instead of guessing a farm.

Ported so far:

* the VHL gate -- ``VHL.GetVHL()`` and ``VHLChallenge(10)`` (ten Roentgenium);
* the Shard itself -- ``VoidChasmMerge.BuyAllMerge("Prime Fiend Shard")``;
* quest **9555** up to the two merge-shop items it needs
  (``TempleDelveMerge`` "Void Nation Caster" and ``DirtlickersMerge`` "Iron
  Dreadsaw"), which are the next modules in the queue.

Not ported yet, and named when reached: ``TempleDelveMerge``,
``DirtlickersMerge``, ``NulgathDiamondMerge``, ``VoidPaladin``,
``VoidSpartan``, ``SwirlingTheAbyss``, ``TradingandStuffSingle``,
``VoidRefugeMerge``, ``VoidAvengerScythe``, ``NulgathDemandsWork``,
``ArchfiendDeathLord``, ``WrathofNulgath`` and ``DilligasMerge``.
"""
from bot.core_bots import buy_item
from bot.core_story import quest_progression
from bot.nation.core_nation import (essence_of_nulgath, farm_dark_crystal_shard,
                                    farm_diamond_of_nulgath, farm_tainted_gem,
                                    farm_uni13_quest, supplies, uni)
from bot.nation.merges.dirtlickers_merge import buy_iron_dreadsaw
from bot.nation.merges.void_chasm_merge import buy_prime_fiend_shard
from bot.nation.vhl.core_vhl import get_vhl, vhl_challenge
from core.command import Command
from templates.hunt import hunt_item

#: The chain's last quest; completed means the Shard is done.
GATE_QUEST = 9559
#: The Shard's own quests, in order.
SHARD_QUESTS = (9555, 9556, 9557, 9558, 9559)
PRIME_FIEND_SHARD = "Prime Fiend Shard"
DUAL_DRAGONBONE_AXE = "Dual Dragonbone Axe of Nulgath"
DRAGONBONE_AXE_QUEST = 629

#: Quest 9555's merge-shop items.  Dirtlickers is ported; TempleDelve is not
#: (it needs the Temple Siege storyline first).
TEMPLE_DELVE_ITEM = "Void Nation Caster (TempleDelveMerge)"


async def _unbank_requirements(cmd: Command, quest_id: int) -> None:
    """``foreach (Item in quest.Requirements) Core.Unbank(Item.ID)``."""
    loaded = cmd.get_loaded_quest(quest_id)
    if loaded is None:
        return
    wanted = {int(item_id) for item_id, _qty in loaded.turn_in_items}
    for entry in getattr(loaded, "items", []) or []:
        if int(entry.get("ItemID") or 0) not in wanted:
            continue
        name = str(entry.get("sName") or "").strip()
        if name and cmd.is_in_bank(name):
            await cmd.bank_to_inv(name)


async def _dual_dragonbone_axe(cmd: Command) -> None:
    """``Core.EnsureAccept(629)`` and its materials."""
    if await cmd.has_item(DUAL_DRAGONBONE_AXE):
        return
    cmd.add_drop(DUAL_DRAGONBONE_AXE)
    if not await cmd.ensure_accept_quest(DRAGONBONE_AXE_QUEST):
        cmd.bot.log(f"[pfs] quest {DRAGONBONE_AXE_QUEST} cannot be accepted; "
                    f"{DUAL_DRAGONBONE_AXE} was not made.")
        return
    await farm_uni13_quest(cmd, 1)
    await farm_tainted_gem(cmd, 13)
    await farm_dark_crystal_shard(cmd, 13)
    await farm_diamond_of_nulgath(cmd, 13)
    await supplies(cmd, uni(21))
    await hunt_item(cmd, "Tainted Rune of Evil", 1, "evilmarsh",
                    monster_name="Tainted Elemental", is_temp=False)
    await cmd.ensure_turn_in_quest(DRAGONBONE_AXE_QUEST)


async def storyline(cmd: Command) -> bool:
    """``PrimeFiendShard.Storyline`` -- the part that is ported.

    Returns False with a named reason when the chain reaches a step this port
    does not have yet.
    """
    if await cmd.is_completed_before(GATE_QUEST):
        return True

    await get_vhl(cmd)
    await vhl_challenge(cmd, 10)
    await buy_prime_fiend_shard(cmd)
    if cmd.is_in_bank(PRIME_FIEND_SHARD):
        await cmd.bank_to_inv(PRIME_FIEND_SHARD)

    # Quest 9555, up to the merge-shop items.
    if not await quest_progression(cmd, 9555):
        await cmd.ensure_accept_quest(9555)
        await _dual_dragonbone_axe(cmd)
        await farm_uni13_quest(cmd, 13)
        await essence_of_nulgath(cmd, 20)
        await farm_diamond_of_nulgath(cmd, 20)
        await buy_iron_dreadsaw(cmd)
        await buy_item(cmd, 1206, "Nation Soulstealer", 1,
                       map_name="shadowblast", shop_item_id=3615)
        await _unbank_requirements(cmd, 9555)

        cmd.bot.log(f"[pfs] quest 9555 still needs {TEMPLE_DELVE_ITEM}; the "
                    f"Temple Siege storyline is not ported yet, so the chain "
                    f"stops here.")
        return False

    cmd.bot.log("[pfs] quest 9555 is done; quests 9556-9559 are not ported "
                "yet.")
    return False


async def main(cmd: Command) -> None:
    """Standalone entry (``python -m bot.nation.various.prime_fiend_shard``)."""
    await storyline(cmd)
