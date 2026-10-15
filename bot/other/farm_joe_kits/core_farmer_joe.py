"""``CoreFarmerJoe`` -- the Farmer Joe kit's pre-endgame progression.

Port of ``Other/FarmJoeKits/CoreFarmerJoe.cs``.  The kit is what
``0_farmer_joe_do_all`` runs, and it is being ported step by step; this is step 1:

* ``do_all`` -- the reference's own order: the level brackets, then the endgame
  stage, then the outfit and the two pets;
* ``set_class`` -- the configured farm/solo class resolved against the pools the
  reference keeps, then equipped;
* ``level_30_to_75`` -- the level ladder (30, 50, 55, 60, 65, 70, 75, 80), the
  one-a-day Elders' Blood, and banking the classes that are not in use;
* the small extras ``shirt_and_hat``, ``servers_are_down``, ``pets``, ``outfit``.

What the reference reaches but this engine cannot do yet is reported, once per
run and by name, with a ``[joe]`` tag -- never skipped quietly:

* ``Adv.GearStore`` / ``Adv.SmartEnhance`` / ``Adv.RankUpClass`` (gear snapshots,
  enhancement profiles, class ranks: none of them exist here),
* ``BeginnerItems``, the eight per-bracket handlers, ``level_75_to_100`` and
  ``end_game``, which are the later steps of this port.

Log lines are the reference's own text, word for word, through ``cmd.bot.log`` --
so a run of this can be read next to a run of the reference bot.
"""
from typing import Optional, Sequence

from bot.core_bots import buy_item, equip_class
from bot.core_dailies import elders_blood
from bot.core_farms import farm_experience
from core.command import Command
from model.inventory import ItemType
from templates.hunt import hunt_item

#: The item quantity a rank 10 class carries (``RANK_10_CLASS_POINTS``).
RANK_10_CLASS_POINTS = 302_500

#: The class pools ``SetClass`` resolves the configured classes against, in the
#: reference's order -- the first one held wins.
SOLO_CLASSES = (
    "King's Echo", "Chaos Avenger", "Void Highlord", "Void Highlord (IoDA)",
    "Legion Revenant", "Dragon of Time", "ArchPaladin", "Lord of Order",
    "Cryomancer", "Dragonslayer General", "Glacial Berserker", "Dragonslayer",
    "DragonSoul Shinobi", "Assassin", "Ninja Warrior", "Classic Ninja", "Ninja",
    "Ninja (Rare)", "Rogue (Rare)", "Rogue", "Healer (Rare)", "Healer",
)
FARM_CLASSES = (
    "Legion Revenant", "ArchMage", "Dragon of Time", "Archfiend", "Blaze Binder",
    "Scarlet Sorceress", "Pyromancer", "Master Ranger", "Mage (Rare)", "Mage",
)
DODGE_CLASSES = (
    "Great Thief", "Yami No Ronin", "Chrono Assassin", "Horc Evader", "Assassin",
    "Ninja Warrior", "Classic Ninja", "Ninja", "Ninja (Rare)", "Rogue (Rare)",
    "Rogue",
)

#: The brackets ``Level30to75`` walks, in the reference's order.
LEVEL_BRACKETS = (30, 50, 55, 60, 65, 70, 75, 80)

#: ``PetChoice`` -- ``DoAll`` asks for the first two explicitly.
PET_NONE = "None"
PET_HOT_MAMA = "HotMama"
PET_AKRILOTH = "Akriloth"
HOT_MAMA = "Hot Mama"
AKRILOTH_PET = "Akriloth Pet"

#: The reference's options, which are module constants here (no option window).
#: Their defaults are the reference's own: the outfit is fetched, but not worn,
#: the boosts stay off, and no pet is chosen except by ``do_all``.
GET_OUTFIT = False
EQUIP_OUTFIT = False
SELL_STARTER_CLASSES = False
GET_BOOSTS = False
PET_CHOICE = PET_NONE

#: ``ShouldSkipSetClass``'s memory: the level and classes it last saw.
_last_checked_level = 0
_last_solo: Optional[str] = None
_last_farm: Optional[str] = None

#: Reports that only make sense once per run.
_reported: set = set()


def report_once(cmd: Command, key: str, message: str) -> None:
    """Log a ``[joe]`` note the first time only, so a run stays readable."""
    if key in _reported:
        return
    _reported.add(key)
    cmd.bot.log(f"[joe] {message}")


def any_rank10(cmd: Command, names: Sequence[str]) -> bool:
    """``AnyRank10``: is one of ``names`` a class with rank 10's class points?

    The reference reads the quantity off the inventory item itself, and insists
    the item is a class: a class that has been ranked up carries
    ``RANK_10_CLASS_POINTS`` class points.
    """
    for name in names:
        item = cmd.bot.player.get_item_inventory(name)
        if (item is not None
                and item.s_es == ItemType.CLASS.value
                and item.qty >= RANK_10_CLASS_POINTS):
            return True
    return False


def _resolve_class(cmd: Command, current: Optional[str],
                   pool: Sequence[str]) -> Optional[str]:
    """``ResolveClass``: keep ``current`` if it is held and in ``pool``, else swap.

    The reference treats an empty name, the literal ``"Generic"``, a name outside
    the pool, and a name that is not held as all equally invalid, and replaces it
    with the first pool entry the account does have.
    """
    invalid = (not current
               or current.lower() == "generic"
               or not any(x.lower() == current.lower() for x in pool)
               or not cmd.is_in_inventory(current))
    if not invalid:
        return current
    for candidate in pool:
        if cmd.is_in_inventory(candidate):
            return candidate
    return current


async def set_class(cmd: Command) -> None:
    """``CoreFarmerJoe.SetClass``: resolve the classes, then equip the solo one.

    The reference reads its class settings (``Core.ReadCBO``) and ranks each up
    before equipping.  Here the settings are the bot's own ``farmClass`` /
    ``soloClass``, and a class rank cannot be read at all -- so the resolved names
    are reported once and the equip goes ahead, rather than a rank-up being
    guessed at.  ``DodgeClass`` has no counterpart in this engine either.
    """
    global _last_checked_level, _last_solo, _last_farm

    level = cmd.get_player().LEVEL or 0
    solo, farm = cmd.get_solo_class(), cmd.get_farm_class()
    if level <= _last_checked_level and solo == _last_solo and farm == _last_farm:
        return

    resolved_solo = _resolve_class(cmd, solo, SOLO_CLASSES)
    resolved_farm = _resolve_class(cmd, farm, FARM_CLASSES)
    if resolved_solo:
        cmd.bot.soloClass = resolved_solo
    if resolved_farm:
        cmd.bot.farmClass = resolved_farm

    report_once(
        cmd, "ranks",
        f"classes resolved to SoloClass={resolved_solo!r}, "
        f"FarmClass={resolved_farm!r}; ranking them up needs the class rank, "
        f"which this engine cannot read, and this engine has no DodgeClass "
        f"(the reference resolves one from {len(DODGE_CLASSES)} pools).")

    if resolved_solo and cmd.is_in_inventory(resolved_solo) \
            and not any_rank10(cmd, [resolved_solo]):
        cmd.bot.log(f"SoloClass resolved -> {resolved_solo}")

    await cmd.sleep(500)
    await equip_class(cmd, solo=True)

    _last_checked_level = level
    _last_solo = resolved_solo
    _last_farm = resolved_farm


async def bank_all_unused_classes(cmd: Command) -> None:
    """``CoreFarmerJoe.BankAllUnusedClasses``: bank every class that is not in use.

    What it keeps is the two classes ``set_class`` resolved, plus the dodge class
    the reference has and this engine does not.
    """
    keep = {name.lower() for name in (cmd.get_solo_class(), cmd.get_farm_class())
            if name}
    to_bank = [item.s_name for item in cmd.bot.player.INVENTORY
               if item.s_es == ItemType.CLASS.value
               and item.s_name.lower() not in keep]
    if to_bank:
        cmd.bot.log(f"Banking unused classes: {', '.join(to_bank)}")
        await cmd.inv_to_bank(to_bank)
    else:
        cmd.bot.log("No unused classes to bank")


async def servers_are_down(cmd: Command) -> None:
    """``CoreFarmerJoe.ServersAreDown``: the "The Server is Down" helm."""
    if await cmd.has_item("The Server is Down"):
        return

    cmd.farming_logger("The Server is Down", 1)
    await set_class(cmd)
    await hunt_item(cmd, "The Server is Down", 1, "undergroundlabb",
                    monster_name="Rabid Server Hamster", is_temp=False)
    await cmd.equip_item("The Server is Down")


async def shirt_and_hat(cmd: Command) -> None:
    """``CoreFarmerJoe.ShirtAndHat``: the NO BOTS Armor and the Scarecrow Hat.

    The armor comes out of ``SynderesMerge``, which needs the merge framework and
    is not ported; the hat is a plain purchase from Yulgar.
    """
    cmd.farming_logger("NO BOTS Armor", 1)
    report_once(cmd, "shirt",
                "ShirtAndHat's \"NO BOTS Armor\" comes from SynderesMerge "
                "(the merge framework), which is not ported.")
    cmd.farming_logger("Scarecrow Hat", 1)
    await buy_item(cmd, 16, "Scarecrow Hat", map_name="yulgar")


async def pets(cmd: Command, choice: Optional[str] = None) -> None:
    """``CoreFarmerJoe.Pets``: fetch and wear the chosen pet, if any.

    Note:
        The reference ignores its own parameter and reads a ``"Pets"`` config key,
        which is not one of the options it declares (``"PetChoice"`` is), so its
        two calls from ``DoAll`` do nothing whichever pet was picked.  The
        parameter is honoured here -- that is the fix for it -- and the slip is in
        the deviation register (``knowledge_script.md`` §16).
    """
    if choice == PET_HOT_MAMA and not await cmd.has_item(HOT_MAMA):
        await set_class(cmd)
        await hunt_item(cmd, HOT_MAMA, 1, "battleundere",
                        monster_name="Hot Mama", is_temp=False)
        await cmd.equip_item(HOT_MAMA)

    if choice == PET_AKRILOTH and not await cmd.has_item(AKRILOTH_PET):
        await set_class(cmd)
        await hunt_item(cmd, AKRILOTH_PET, 1, "gravestrike",
                        monster_name="Ultra Akriloth", is_temp=False)
        await cmd.equip_item(AKRILOTH_PET)


async def outfit(cmd: Command) -> None:
    """``CoreFarmerJoe.Outfit``: the extras, and the set itself if asked for."""
    await set_class(cmd)

    await shirt_and_hat(cmd)
    await servers_are_down(cmd)
    report_once(cmd, "smart_enhance",
                "Adv.SmartEnhance has no counterpart here; enhance the class by "
                "hand (or through a loadout) after the run.")

    await pets(cmd, PET_CHOICE)

    if EQUIP_OUTFIT:
        for item in ("NO BOTS Armor", "Scarecrow Hat", "The Server is Down",
                     "Hollowborn Reaper's Scythe", PET_CHOICE):
            await cmd.equip_item(item)

    cmd.bot.log("We are farmers, bum ba dum bum bum bum bum")


async def level_1_to_30(cmd: Command) -> None:
    """``CoreFarmerJoe.Level1to30``: the beginner items, then the class-points note.

    ``BeginnerItems`` is step 2 of this port: it needs ``Story/Tutorial``,
    ``Mazumi`` and ``Adv.RankUpClass``.
    """
    report_once(cmd, "beginner_items",
                "BeginnerItems is not ported yet (step 2): it needs "
                "Story/Tutorial, Mazumi and Adv.RankUpClass.")
    cmd.bot.log("Class points may be desynced at Rank 9, if you are stuck at "
                "rank 9, please stop the bot & relog if this happens")


async def level_30_to_75(cmd: Command) -> None:
    """``CoreFarmerJoe.Level30to75``: the level ladder, brackets 30 through 80.

    Each bracket: enhance (reported), level to the bracket, run that bracket's
    handler (reported until step 3), then bank the unused classes.
    """
    await set_class(cmd)

    if (cmd.get_player().LEVEL or 0) >= 30:
        await elders_blood(cmd)

    cmd.bot.log(
        "Joe will handle each level bracket (0-30, 30-50, 50-55, 55-60, 60-65, "
        "65-75, 75-100)\n doing the leveling first, then acquiring classes and "
        "items after\n so its prepared... and hopefully strong enough to handle "
        "the next level bracket.")

    if GET_BOOSTS:
        report_once(cmd, "boosts",
                    "GetBoosts is on, but CoreFarms.GetBoost and "
                    "FreeBoosts.GetBoostsSelect are not ported.")

    for level in LEVEL_BRACKETS:
        report_once(cmd, "smart_enhance",
                    "Adv.SmartEnhance has no counterpart here; enhance the class "
                    "by hand (or through a loadout) after the run.")

        await farm_experience(cmd, level)

        handler = LEVEL_HANDLERS.get(level)
        if handler is not None:
            cmd.bot.log(f"Level Handler: {level} bracket")
            await handler(cmd)
            await bank_all_unused_classes(cmd)


async def level_75_to_100(cmd: Command) -> None:
    """``CoreFarmerJoe.Level75to100``: the endgame classes and weapons (step 4)."""
    report_once(cmd, "lvl75",
                "Level75to100 is not ported yet (step 4): it needs CapeOfAwe, "
                "Core13LoC.Complete13LOC, LordOfOrder, UnlockForgeEnhancements, "
                "CelestialArenaQuests, BurningBladeOfAbezeth, CoreYnR, "
                "DragonOfTime, KingsEcho and ShadowrealmMerge.")


async def end_game(cmd: Command) -> None:
    """``CoreFarmerJoe.EndGame``: the remaining enhancements (step 5)."""
    if GET_OUTFIT:
        await outfit(cmd)
    await set_class(cmd)
    report_once(cmd, "endgame",
                "EndGame is not ported yet (step 5): it needs "
                "UnlockForgeEnhancements, ExaltedApotheosisPreReqs and "
                "CoreNation.Supplies.")


async def do_all(cmd: Command) -> None:
    """``CoreFarmerJoe.DoAll``: the whole kit, in the reference's order."""
    report_once(cmd, "gear_store",
                "Adv.GearStore (the gear snapshot around the run) has no "
                "counterpart here.")

    await level_1_to_30(cmd)
    await level_30_to_75(cmd)
    await level_75_to_100(cmd)
    await end_game(cmd)
    await outfit(cmd)
    await pets(cmd, PET_HOT_MAMA)
    await pets(cmd, PET_AKRILOTH)

    report_once(cmd, "gear_store_after",
                "Adv.GearStore(true, EnhAfter: true) at the end of the run is "
                "skipped for the same reason.")


async def _handle_level_30(cmd: Command) -> None:
    report_once(cmd, "lvl30",
                "bracket 30 needs MasterRanger, Dragonslayer, "
                "CoreFarms.BladeofAweREP and UnlockForgeEnhancements (step 3).")


async def _handle_level_50(cmd: Command) -> None:
    report_once(cmd, "lvl50",
                "bracket 50 needs ScarletSorceress, DragonslayerGeneral and "
                "BurningBlade (step 3).")


async def _handle_level_55(cmd: Command) -> None:
    report_once(cmd, "lvl55",
                "bracket 55 needs BlazeBinder and Cryomancer (step 3).")


async def _handle_level_60(cmd: Command) -> None:
    report_once(cmd, "lvl60",
                "bracket 60 needs DragonShinobi and "
                "UnlockForgeEnhancements.Lacerate (step 3).")


async def _handle_level_65(cmd: Command) -> None:
    report_once(cmd, "lvl65",
                "bracket 65 needs GlacialBerserker (step 3).")


async def _handle_level_70(cmd: Command) -> None:
    report_once(cmd, "lvl70",
                "bracket 70 needs UnlockForgeEnhancements (Smite, Vim, Pneuma, "
                "Examen, Anima), Horc Evader and ArchPaladin (step 3).")


async def _handle_level_75(cmd: Command) -> None:
    report_once(cmd, "lvl75_bracket",
                "bracket 75 needs EnoughDOOMforanArchfiend and Archfiend, plus "
                "Adv.HasMinimalBoost (step 3).")


async def _handle_level_80(cmd: Command) -> None:
    report_once(cmd, "lvl80",
                "bracket 80 acquires Void Highlord through CoreVHL.GetVHL, which "
                "is ported; wiring it here is step 3.")


#: Bracket -> the handler the reference runs after leveling to it.
LEVEL_HANDLERS = {
    30: _handle_level_30,
    50: _handle_level_50,
    55: _handle_level_55,
    60: _handle_level_60,
    65: _handle_level_65,
    70: _handle_level_70,
    75: _handle_level_75,
    80: _handle_level_80,
}
