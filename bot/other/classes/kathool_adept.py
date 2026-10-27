"""Kathool Adept -- the class from /callofkathool, quest 10920.

Port of ``Other/Classes/KathoolAdept.cs``.  The class quest is gated by the
*other* Kathool quest, 10918 (``BottomFeeder``), which is what the seven set
armors and rank 10 Somnia/Fishing are for; an account that already owns
``Adeptus Kathooli`` takes the shortcut through 10919 instead.

Two substitutions, both reported here:

* ``Bot.Quests.IsUnlocked(10920)`` -- a client slot check with no counterpart in
  this engine.  "Not completed yet" stands in for it, the same substitution
  ``bot/enhancements/lacerate.py`` documents; the unlock itself is then proven by
  ``ensure_accept_quest(10920)``, which reports a refusal in its own words, so the
  source's ``Wait.ForTrue`` on the client flag has nothing left to add.
* ``Core.AddDrop(104429, 104532, 104533)`` -- the whitelist here is by name, so
  the three ids are given as the names they belong to.

The source's ``RequiredArmors`` order is kept: DeepWater Drow is bought before
Ashray Elf Warden, because the Drow merge consumes one.
"""
from bot.core_bots import buy_item, equip_class, wait_for_item
from bot.core_farms import fishing_rep, somnia_rep
from bot.core_story import CustomError
from bot.other.merge_shops.abyssal_zone_merge import abyssal_zone_merge
from bot.other.merge_shops.midnight_zone_merge import midnight_zone_merge
from bot.other.merge_shops.sea_voice_merge import sea_voice_merge
from bot.other.merge_shops.seaview_souvenirs_merge import seaview_souvenirs_merge
from bot.other.merge_shops.trench_observe_merge import trench_observe_merge
from bot.other.merge_shops.twilight_zone_merge import twilight_zone_merge
from bot.other.merge_shops.undine_commissary_merge import undine_commissary_merge
from bot.story.age_of_ruin.core_aor import sea_voice
from core.command import Command
from templates.hunt import hunt_item
from bot.script_log import ScriptLog
TAG = "Kathool Adept"

CLASS = "Kathool Adept"
#: ``Core.CheckInventory(104429, toInv: false)`` -- the class item itself.
CLASS_ITEM = 104429
CLASS_LEVEL = 80
CLASS_MAP = "callofkathool"

#: ``isCompletedBefore(9348)`` -- the Voice in the Sea saga's last quest.
SAGA_LAST_QUEST = 9348
#: ``Bot.Quests.IsUnlocked(10920)``: the class quest, and the two ways to it.
CLASS_QUEST = 10920
BOTTOM_FEEDER_QUEST = 10918
SHORTCUT_QUEST = 10919
#: ``Core.CheckInventory(78153)`` -- the owned Adeptus Kathooli shortcut.
SHORTCUT_ITEM = "Adeptus Kathooli"

#: 10918's turn-in: 75 morsels from the Kultist, and Johnnyfish from a shop.
MORSEL = "Kultist's Morsel"
MORSEL_ITEM = 104532
MORSEL_QUANT = 75
MORSEL_MONSTER = "Kathool Kultist"
JOHNNYFISH = "Johnnyfish"
JOHNNYFISH_ITEM = 104533
JOHNNYFISH_MAP = "greenguardwest"
JOHNNYFISH_SHOP = 363
JOHNNYFISH_SHOP_ITEM_ID = 15252

#: 10920's drop, in the temporary bag (``Bot.TempInv``).
CONSUMED = "Kathool's Morsel Consumed"
CONSUMED_ITEM = 104534
CONSUMED_MONSTER = "Mad Morsel"

#: ``RequiredArmors``, in the reference's order.
REQUIRED_ARMORS = ("Kathool Acolyte", "Ashray Elf Warden",
                   "Midnight Glaucus Sage", "DeepWater Drow", "Ashray Villager",
                   "Evacuation Protocol Suit", "Undine Defence Director",
                   "Elven Heritage Guardian")
ACOLYTE = "Kathool Acolyte"
ACOLYTE_MAP = "deepchaos"
ACOLYTE_MONSTER = "Kathool"
GLAUCUS = "Midnight Glaucus Sage"
GLAUCUS_MYSTIC = "Midnight Glaucus Mystic"


def owns_class(cmd: Command) -> bool:
    """``Core.CheckInventory(104429, toInv: false)`` -- banked counts, no pull."""
    player = cmd.bot.player
    return (player.get_item_inventory_by_id(CLASS_ITEM) is not None
            or player.get_item_bank_by_id(CLASS_ITEM) is not None)


async def accept_quest(cmd: Command, quest_id: int) -> bool:
    """``KathoolAdept.AcceptQuest``: accept, then confirm it is in progress."""
    await cmd.ensure_accept_quest(quest_id)
    if cmd.quest_in_progress(quest_id):
        return True
    ScriptLog(cmd, TAG).warning(f"Quest {quest_id} was not accepted. Check its requirements.")
    return False


async def farm_required_armors(cmd: Command) -> bool:
    """``KathoolAdept.FarmRequiredArmors``: the seven set items and the Acolyte.

    Returns:
        bool: False when the bot was told to stop part way through.
    """
    for item, merge in (("Ashray Villager", seaview_souvenirs_merge),
                        ("Undine Defence Director", undine_commissary_merge),
                        ("Evacuation Protocol Suit", twilight_zone_merge),
                        ("Elven Heritage Guardian", midnight_zone_merge),
                        # the Drow merge consumes one Warden, so it goes first
                        ("DeepWater Drow", trench_observe_merge),
                        ("Ashray Elf Warden", abyssal_zone_merge)):
        if not cmd.is_still_connected():
            return False
        if not await cmd.has_item(item):
            await merge(cmd, buy_only_this=item)

    if cmd.is_still_connected() and not await cmd.has_item(GLAUCUS):
        # The prerequisites are merged first so their own recipes do not eat the
        # materials the Sage needs.
        if not await cmd.has_item(GLAUCUS_MYSTIC):
            await sea_voice_merge(cmd, buy_only_this="Glaucus Sage")
            await sea_voice_merge(cmd, buy_only_this=GLAUCUS_MYSTIC)
        await sea_voice_merge(cmd, buy_only_this=GLAUCUS)

    if cmd.is_still_connected() and not await cmd.has_item(ACOLYTE):
        await equip_class(cmd, solo=True)
        await hunt_item(cmd, ACOLYTE, 1, ACOLYTE_MAP,
                        monster_name=ACOLYTE_MONSTER, is_temp=False)

    return cmd.is_still_connected()


async def bottom_feeder(cmd: Command) -> bool:
    """``KathoolAdept.BottomFeeder``: quest 10918, the 10920 unlock.

    Returns:
        bool: True only when the quest was accepted and turned in.
    """
    if not await farm_required_armors(cmd):
        return False

    for armor in REQUIRED_ARMORS:
        if not await cmd.has_item(armor):
            ScriptLog(cmd, TAG).warning(f"Required armor is missing from inventory: {armor}.")
            return False

    await somnia_rep(cmd)
    if not cmd.is_still_connected():
        return False
    if cmd.get_faction_rank("Somnia") < 10:
        ScriptLog(cmd, TAG).warning("Bottom Feeder requires rank 10 Somnia.")
        return False

    await fishing_rep(cmd)
    if not cmd.is_still_connected():
        return False
    # A shop gates on the server's rank, which is what the faction list holds:
    # the catch frames' own rep is *not* added on top of it.
    fishing = cmd.get_faction_rank("Fishing")
    if fishing < 10:
        ScriptLog(cmd, TAG).warning("Johnnyfish requires rank 10 Fishing.")
        ScriptLog(cmd, TAG).info(f"[kathool] the server reports Fishing rank {fishing}; the "
                    f"shop will refuse the purchase until it reaches 10.")
        return False

    await buy_item(cmd, JOHNNYFISH_SHOP, JOHNNYFISH_ITEM,
                   map_name=JOHNNYFISH_MAP,
                   shop_item_id=JOHNNYFISH_SHOP_ITEM_ID)
    if not cmd.is_still_connected():
        return False
    # The purchase packet is answered a moment later; waiting is what tells a
    # real buy apart from a refused one.
    await wait_for_item(cmd, JOHNNYFISH)
    if not await cmd.has_item(JOHNNYFISH):
        ScriptLog(cmd, TAG).warning("Johnnyfish is missing from inventory.")
        return False

    await cmd.join_map(CLASS_MAP)
    if not await accept_quest(cmd, BOTTOM_FEEDER_QUEST):
        return False

    await equip_class(cmd)
    await hunt_item(cmd, MORSEL, MORSEL_QUANT, CLASS_MAP,
                    monster_name=MORSEL_MONSTER, is_temp=False)
    if not cmd.is_still_connected():
        return False
    if not await cmd.has_item(MORSEL, MORSEL_QUANT):
        ScriptLog(cmd, TAG).warning(f"Bottom Feeder requires {MORSEL_QUANT} Kultist morsels in "
                    f"inventory.")
        return False

    if await cmd.ensure_turn_in_quest(BOTTOM_FEEDER_QUEST) is False:
        return False
    return cmd.is_still_connected()


async def get_class(cmd: Command) -> None:
    """``KathoolAdept.GetClass``: the sage, the unlock, then quest 10920."""
    if owns_class(cmd):
        ScriptLog(cmd, TAG).success("Kathool Adept is already owned.")
        return

    if (cmd.get_player().LEVEL or 0) < CLASS_LEVEL:
        ScriptLog(cmd, TAG).warning(f"Kathool Adept requires level {CLASS_LEVEL}.")
        return

    await sea_voice(cmd)
    if not cmd.is_still_connected():
        return

    if not await cmd.is_completed_before(SAGA_LAST_QUEST):
        ScriptLog(cmd, TAG).info("Voice in the Sea saga completion was not confirmed. Class "
                    "quests will not start.")
        return

    cmd.add_drop([CLASS, MORSEL, JOHNNYFISH])
    await cmd.join_map(CLASS_MAP)

    # ``if (!Bot.Quests.IsUnlocked(10920))``: "not done yet" is this engine's
    # stand-in; both unlock paths advance the same slot.
    if not await cmd.is_completed_before(CLASS_QUEST):
        if await cmd.has_item(SHORTCUT_ITEM):
            ScriptLog(cmd, TAG).info("Using the owned Adeptus Kathooli shortcut.")
            if not await accept_quest(cmd, SHORTCUT_QUEST):
                return
            if await cmd.ensure_turn_in_quest(SHORTCUT_QUEST) is False:
                return
        else:
            if not await bottom_feeder(cmd):
                return

    await cmd.join_map(CLASS_MAP)
    if not await accept_quest(cmd, CLASS_QUEST):
        return

    await equip_class(cmd, solo=True)
    await hunt_item(cmd, CONSUMED, 1, CLASS_MAP, monster_name=CONSUMED_MONSTER)
    if not cmd.is_still_connected():
        return
    if cmd.bot.player.get_item_temp_inventory_by_id(CONSUMED_ITEM) is None:
        ScriptLog(cmd, TAG).success("The Mad Morsel quest drop was not obtained.")
        return

    if await cmd.ensure_turn_in_quest(CLASS_QUEST, CLASS_ITEM) is False:
        raise CustomError(f"quest {CLASS_QUEST} could not be turned in")

    await wait_for_item(cmd, CLASS)
    if not cmd.is_still_connected():
        return
    if await cmd.has_item(CLASS):
        ScriptLog(cmd, TAG).success("Kathool Adept obtained.")
    else:
        ScriptLog(cmd, TAG).info("The Kathool Adept reward was not received. Check the quest "
                    "and inventory space.")


async def main(cmd: Command):
    await get_class(cmd)


if __name__ == "__main__":
    # Runs this script on its own account, the way
    # ``bot/enhancements/valiance.py`` does.
    from bot.standalone import run_standalone

    run_standalone(main)
