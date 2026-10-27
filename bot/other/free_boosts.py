"""``FreeBoosts.GetBoostsSelect`` -- the free 10-minute boosts from quest 6208.

Port of ``Other/FreeBoosts/FreeBoostsQuest(10mns)[Rng].cs``.

Deviation, reported: the reference computes ``allQuantitiesMet`` **before** its
``while`` and never recomputes it, so that loop can only end when the bot is
stopped.  Here the three counts are re-read on every pass, which is what the
source means to do.

Its ``Bot.Inventory`` re-clamping of each stack is dropped too -- it only edits
the local copy the C# bot keeps, nothing is sent.

A quantity of ``0`` means that boost is not wanted (the kit calls
``GetBoostsSelect(10, 10, 0)``): asking the inventory for "at least zero" would
still demand the item exists, and the loop would never end.
"""
from bot.core_bots import equip_class, hunt_monster_quest
from core.command import Command
from bot.script_log import ScriptLog
TAG = "Free Boosts"

GOLD_BOOST = "GOLD Boost! (10 min)"
CLASS_BOOST = "CLASS Boost! (10 min)"
REP_BOOST = "REPUTATION Boost! (10 min)"
FREE_BOOST_QUEST = 6208
FREE_BOOST_HUNTS = (("bloodtusk", "Trollola Plant", True),
                    ("cloister", "Acornent", False),
                    ("nibbleon", "Dark Makai", False))


async def get_boosts_select(cmd: Command, gold_quant: int = 9999,
                            class_quant: int = 9999,
                            rep_quant: int = 9999) -> None:
    """``GetBoostsSelect``: farm quest 6208 until all three stacks are filled.

    Args:
        cmd (Command): Facade to act through.
        gold_quant (int): How many GOLD boosts to end up with.
        class_quant (int): How many CLASS boosts to end up with.
        rep_quant (int): How many REPUTATION boosts to end up with.
    """
    cmd.add_drop([GOLD_BOOST, CLASS_BOOST, REP_BOOST])
    ScriptLog(cmd, TAG).info("RNG Quest Rewards: drops are randomly received, and may take a "
                "while... be prepared if quantities are high.")

    # A quantity of 0 means "I do not want this one" -- the caller
    # ``GetBoostsSelect(10, 10, 0)`` -- rather than "at least zero", which the
    # inventory check would read as "must still own one".
    wanted = [(name, quant) for name, quant in
              ((GOLD_BOOST, gold_quant), (CLASS_BOOST, class_quant),
               (REP_BOOST, rep_quant)) if quant > 0]

    for name, quant in wanted:
        if not await cmd.has_item(name, quant):
            cmd.farming_logger(name, quant)

    await equip_class(cmd)

    while cmd.is_still_connected():
        if all([await cmd.has_item(name, quant) for name, quant in wanted]):
            break
        await hunt_monster_quest(cmd, FREE_BOOST_QUEST, *FREE_BOOST_HUNTS)


async def main(cmd: Command):
    await get_boosts_select(cmd)
