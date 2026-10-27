"""Vainglory -- quest 8744, the cape enhancement on the Awe relic chain.

Port of ``Enhancement/UnlockForgeEnhancements.Vainglory``.  Absolution comes
first (the reference calls it), then Blacksmithing rank 9, then the five Awe
relics: a member buys the Armor of Awe Pass and farms the Pauldron fragments on
quest 4162, everybody else walks the relic quests themselves.

The other cape enhancements are not ported yet, and their blockers are named in
the log rather than skipped quietly: Avarice needs the Legion circles and the
Head of the Legion Beast, Lament needs Penitence (which needs Avarice) plus the
Third Spell story and the 7 Deadly Dragons.
"""
from bot.core_advanced import buy_item
from bot.core_bots import equip_class, wait_for_item
from bot.core_farms import (blade_of_awe_rep, blacksmithing_rep,
                            farm_experience)
from bot.enhancements.absolution import absolution
from bot.other.gear_of_awe.core_awe import get_awe_relic
from bot.script_log import ScriptLog
from core.command import Command
from templates.hunt import hunt_item

TAG = "Vainglory"
VAINGLORY_QUEST = 8744
BLACKSMITHING_RANK = 9

#: The five relics the quest wants: ``(item, legend quest, fragments, shards,
#: map, monster)`` -- the reference's own ``Awe.GetAweRelic`` arguments.
RELICS = (("Breastplate", 4163, 10, 10, "aqlesson", "Carnax"),
          ("Vambrace", 4166, 15, 15, "bloodtitan", "Ultra Blood Titan"),
          ("Gauntlet", 4169, 25, 5, "alteonbattle", "ULTRA Alteon"),
          ("Greaves", 4172, 10, 15, "bosschallenge", "Mutated Void Dragon"))

#: The member path's Pauldron: the pass, then quest 4162's fragments.
PAULDRON = "Pauldron"
PAULDRON_RELIC = "Pauldron Relic"
PAULDRON_QUEST = 4162
PAULDRON_FRAGMENT = "Pauldron Fragment"
PAULDRON_QTY = 15
PAULDRON_MAP = "gravestrike"
PAULDRON_MONSTER = "Ultra Akriloth"
PASS_MAP = "museum"
PASS_SHOP = 1130
PASS_NAME = "Armor of Awe Pass"
AWE_SHOP_MAP = "museum"
AWE_SHOP = 1129
#: ``Awe.GetAweRelic("Pauldron", 4160, 15, 15, "gravestrike", "Ultra Akriloth")``
PAULDRON_RELIC_ARGS = (PAULDRON, 4160, 15, 15, PAULDRON_MAP, PAULDRON_MONSTER)


async def _member_pauldron(cmd: Command, log: ScriptLog) -> None:
    """The member branch: the pass bought, then 15 fragments under quest 4162."""
    if await cmd.has_item(PAULDRON_RELIC):
        return
    await blade_of_awe_rep(cmd, 10, False)
    await farm_experience(cmd, 55)
    await buy_item(cmd, PASS_SHOP, PASS_NAME, map_name=PASS_MAP)

    cmd.add_drop(PAULDRON_FRAGMENT)
    await cmd.register_quest(PAULDRON_QUEST)
    await hunt_item(cmd, PAULDRON_FRAGMENT, PAULDRON_QTY, PAULDRON_MAP,
                    monster_name=PAULDRON_MONSTER, is_temp=False)
    await wait_for_item(cmd, PAULDRON_FRAGMENT)
    cmd.cancel_registered_quests()

    log.info(f"Buying {PAULDRON_RELIC} from the Awe shop...")
    await buy_item(cmd, AWE_SHOP, PAULDRON_RELIC, map_name=AWE_SHOP_MAP)


async def vainglory(cmd: Command, use_gold: bool = False) -> None:
    """``UnlockForgeEnhancements.Vainglory``.

    Args:
        cmd (Command): Facade to act through.
        use_gold (bool): The reference's ``UseGold`` option for the reputation
            step.
    """
    log = ScriptLog(cmd, TAG)
    if await cmd.is_completed_before(VAINGLORY_QUEST):
        log.success("Already unlocked (quest 8744 is done).")
        return

    await absolution(cmd)

    log.info("Unlocking Enhancement: Vainglory")
    if await cmd.ensure_accept_quest(VAINGLORY_QUEST) is False:
        log.warning(f"quest {VAINGLORY_QUEST} could not be accepted; stopping.")
        return

    await blacksmithing_rep(cmd, BLACKSMITHING_RANK, use_gold)
    await equip_class(cmd, solo=True)

    if cmd.get_player().is_member:
        await _member_pauldron(cmd, log)
    else:
        log.info("Non-member: farming the Pauldron relic through its own quests.")
        await get_awe_relic(cmd, *PAULDRON_RELIC_ARGS)

    for relic in RELICS:
        log.info(f"Farming the {relic[0]} relic...")
        await get_awe_relic(cmd, *relic)

    if await cmd.ensure_turn_in_quest(VAINGLORY_QUEST) is False:
        log.warning(f"quest {VAINGLORY_QUEST} could not be turned in.")
        return
    log.success("Enhancement Unlocked: Vainglory")


async def main(cmd: Command):
    await vainglory(cmd)


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
