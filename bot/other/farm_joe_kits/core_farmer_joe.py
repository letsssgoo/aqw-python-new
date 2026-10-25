"""``CoreFarmerJoe`` -- the Farmer Joe kit's pre-endgame progression.

Port of ``Other/FarmJoeKits/CoreFarmerJoe.cs``.  The kit is what
``0_farmer_joe_do_all`` runs, and it is being ported step by step:

* ``do_all`` -- the reference's own order: the level brackets, then the endgame
  stage, then the outfit and the two pets;
* ``set_class`` -- the configured farm/solo class resolved against the pools the
  reference keeps, then equipped;
* ``beginner_items`` -- step 2: the starter slots at Class Halla, Rogue, Ninja
  and Mage, with the tutorial badges reported;
* ``level_30_to_75`` -- the level ladder (30, 50, 55, 60, 65, 70, 75, 80), the
  one-a-day Elders' Blood, and banking the classes that are not in use;
* the eight bracket handlers -- step 3 -- with their own log lines, each one
  running what this engine can and reporting what it cannot (bracket 80 is
  ``CoreVHL.GetVHL``, which is ported);
* the small extras ``shirt_and_hat``, ``servers_are_down``, ``pets``, ``outfit``.

What the reference reaches but this engine cannot do yet is reported, once per
run and by name, with a ``[joe]`` tag -- never skipped quietly:

* ``Adv.GearStore`` / ``Adv.SmartEnhance`` / ``Adv.RankUpClass`` (gear snapshots,
  enhancement profiles, class ranks: none of them exist here),
* the class and item kits the bracket handlers farm, ``level_75_to_100`` and
  ``end_game``, which are the later steps of this port (4 and 5).

Log lines are the reference's own text, word for word, through ``cmd.bot.log`` --
so a run of this can be read next to a run of the reference bot.
"""
from typing import Optional, Sequence

from bot.core_advanced import buy_item as adv_buy_item
from bot.core_advanced import gear_store, rank_up_class, smart_enhance
from bot.core_bots import buy_item, equip_class, farming_logger
from bot.core_dailies import elders_blood
from bot.core_farms import farm_experience
from bot.enhancements.anima import anima
from bot.enhancements.forge_helm import forge_helm_enhancement
from bot.enhancements.lacerate import lacerate
from bot.enhancements.pneuma import pneuma
from bot.enhancements.smite import smite
from bot.enhancements.examen import examen
from bot.enhancements.vim import vim
from bot.nation.afdl.enough_doom_for_an_archfiend import afdl
from bot.nation.vhl.core_vhl import get_vhl
from bot.other.classes.dragonslayer_general import get_ds_general
from bot.other.classes.rep_based.master_ranger import get_mr
from bot.other.weapons.burning_blade import get_burning_blade
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

#: ``BeginnerItems``' own lists.  Its exclusions are spelled exactly as the
#: reference spells them: ``Except`` compares case-sensitively, so the pool's
#: "Mage (Rare)" is *not* the "Mage (rare)" it excludes and stays in the check.
BEGINNER_SOLO_EXCEPT = ("Assassin", "Ninja Warrior", "Ninja")
BEGINNER_FARM_EXCEPT = ("Mage", "Mage (rare)")
NINJA_NAMES = ("Assassin", "Ninja Warrior", "Ninja")
MAGE_NAMES = ("Mage (Rare)", "Mage")
ROGUE_NAMES = ("Rogue (Rare)", "Rogue")

#: The shops and items ``BeginnerItems`` buys from Class Halla.
CLASSHALLA = "classhalla"
BATTLE_ORACLE_SHOP = 299
ROGUE_SHOP = 172
NINJA_SHOP = 178
NINJA_NAME = "Ninja"
MAGE_SHOP = 174
MAGE_ITEM_ID = 15653
MAGE_SHOP_ITEM_ID = 9845
DEFAULT_WEAPON_PREFIX = "Default"

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

#: ``GetClass``'s cache, cleared by ``set_class`` as the reference clears it.
_class_cache: dict = {}


def _get_class(cmd: Command, class_name: str):
    """``GetClass``: the class item with that name, from the inventory or the bank.

    The reference trims the name and compares case-insensitively, insists the item
    is a class, and caches the answer until the next ``set_class``.
    """
    if class_name in _class_cache:
        return _class_cache[class_name]

    found = None
    for candidate in list(cmd.bot.player.INVENTORY) + list(cmd.bot.player.BANK):
        if (candidate.s_name.strip().lower() == class_name.lower()
                and candidate.s_es == ItemType.CLASS.value):
            found = candidate
            break
    _class_cache[class_name] = found
    return found


def _current_class_name(cmd: Command) -> str:
    """``Bot.Player.CurrentClass?.Name``: the worn class, empty when none."""
    equipped = cmd.get_equipped_class()
    return getattr(equipped, "item_name", "") or ""


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

    _class_cache.clear()
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

    farming_logger(cmd, "The Server is Down", 1)
    await set_class(cmd)
    await hunt_item(cmd, "The Server is Down", 1, "undergroundlabb",
                    monster_name="Rabid Server Hamster", is_temp=False)
    await cmd.equip_item("The Server is Down")


async def shirt_and_hat(cmd: Command) -> None:
    """``CoreFarmerJoe.ShirtAndHat``: the NO BOTS Armor and the Scarecrow Hat.

    The armor comes out of ``SynderesMerge``, which needs the merge framework and
    is not ported; the hat is a plain purchase from Yulgar.
    """
    farming_logger(cmd, "NO BOTS Armor", 1)
    report_once(cmd, "shirt",
                "ShirtAndHat's \"NO BOTS Armor\" comes from SynderesMerge "
                "(the merge framework), which is not ported.")
    farming_logger(cmd, "Scarecrow Hat", 1)
    await adv_buy_item(cmd, 16, "Scarecrow Hat", map_name="yulgar")


async def pets(cmd: Command, choice: Optional[str] = None) -> None:
    """``CoreFarmerJoe.Pets``: fetch and wear the chosen pet -- which cannot happen.

    Note:
        The reference *ignores* its own parameter and reads a config key ``"Pets"``,
        which is not one of the options it declares -- those name ``"PetChoice"``.
        So the value it reads is always that option's declared default,
        ``PetChoice.None``, and the method returns without doing anything.  That is
        reproduced here instead of repaired: ``PET_CHOICE`` is that option and it
        is ``PET_NONE``, so ``choice`` is accepted and unused, exactly as in the
        source.  ``DoAll``'s two pet calls are therefore no-ops there as well --
        the source's own dead code, registered as a (iii) defect, not a port
        decision.  Set ``PET_CHOICE`` to a pet to make the branch below run, which
        is what setting the reference's option would have done.
    """
    if PET_CHOICE == PET_NONE:
        return

    if PET_CHOICE == PET_HOT_MAMA and not await cmd.has_item(HOT_MAMA):
        await set_class(cmd)
        await hunt_item(cmd, HOT_MAMA, 1, "battleundere",
                        monster_name="Hot Mama", is_temp=False)
        await cmd.equip_item(HOT_MAMA)

    if PET_CHOICE == PET_AKRILOTH and not await cmd.has_item(AKRILOTH_PET):
        await set_class(cmd)
        await hunt_item(cmd, AKRILOTH_PET, 1, "gravestrike",
                        monster_name="Ultra Akriloth", is_temp=False)
        await cmd.equip_item(AKRILOTH_PET)


async def outfit(cmd: Command) -> None:
    """``CoreFarmerJoe.Outfit``: the extras, and the set itself if asked for."""
    await set_class(cmd)

    await shirt_and_hat(cmd)
    await servers_are_down(cmd)
    await smart_enhance(cmd, _current_class_name(cmd))

    await pets(cmd, PET_CHOICE)

    if EQUIP_OUTFIT:
        for item in ("NO BOTS Armor", "Scarecrow Hat", "The Server is Down",
                     "Hollowborn Reaper's Scythe", PET_CHOICE):
            await cmd.equip_item(item)

    cmd.bot.log("We are farmers, bum ba dum bum bum bum bum")


async def level_1_to_30(cmd: Command) -> None:
    """``CoreFarmerJoe.Level1to30``: the beginner items, then the class-points note."""
    await beginner_items(cmd)
    cmd.bot.log("Class points may be desynced at Rank 9, if you are stuck at "
                "rank 9, please stop the bot & relog if this happens")


async def _starter_slots(cmd: Command) -> None:
    """``BeginnerItems``' slot pass: Battle Oracle hood, wings and battlestaff.

    The reference walks every item category.  Only three cases do anything: an
    empty helm slot, an empty cape slot, and a ``Default`` weapon still in hand,
    which it replaces with the battlestaff and sells on the spot.
    """
    inventory = cmd.bot.player.INVENTORY

    if not any(i.is_equipped and i.s_es == ItemType.HELM.value for i in inventory):
        await buy_item(cmd, BATTLE_ORACLE_SHOP, "Battle Oracle Hood",
                       map_name=CLASSHALLA)
        await cmd.equip_item("Battle Oracle Hood")

    if not any(i.is_equipped and i.s_es == ItemType.CAPE.value for i in inventory):
        await buy_item(cmd, BATTLE_ORACLE_SHOP, "Battle Oracle Wings",
                       map_name=CLASSHALLA)
        await cmd.equip_item("Battle Oracle Wings")

    default_weapon = next((i for i in inventory
                           if i.s_name.startswith(DEFAULT_WEAPON_PREFIX)), None)
    if default_weapon is None:
        return
    await buy_item(cmd, BATTLE_ORACLE_SHOP, "Battle Oracle Battlestaff",
                   map_name=CLASSHALLA)
    await cmd.equip_item("Battle Oracle Battlestaff")
    await cmd.sell_item(default_weapon.s_name)
    # the reference waits (up to 20 tries) for the sale to clear the inventory
    for _ in range(20):
        if not await cmd.has_item(default_weapon.s_name):
            return
        await cmd.sleep(100)


async def beginner_items(cmd: Command) -> None:
    """``CoreFarmerJoe.BeginnerItems``: the tutorial badges and the starter kit.

    The guard is the reference's: an account that already has a high-tier class in
    both pools, or both beginner classes at rank 10, is left alone with its own
    line in the log.  Skipped here, because this engine cannot reach the pieces
    they need, are ``Tutorial.Badges``, ``Mazumi.MazumiQuests`` and
    ``Adv.RankUpClass`` -- and with Mazumi missing the Ninja purchase is skipped
    too, since its shop would refuse it.
    """
    solo_others = [name for name in SOLO_CLASSES
                   if name not in BEGINNER_SOLO_EXCEPT]
    farm_others = [name for name in FARM_CLASSES
                   if name not in BEGINNER_FARM_EXCEPT]
    has_high_tier = (await cmd.has_any_item(solo_others)
                     and await cmd.has_any_item(farm_others))

    ninja = _get_class(cmd, NINJA_NAME)
    mage = _get_class(cmd, "Mage")
    ninja_points = ninja.qty if ninja else 0
    mage_points = mage.qty if mage else 0
    has_both_rank10 = (
        await cmd.has_any_item(list(NINJA_NAMES))
        and ninja_points >= RANK_10_CLASS_POINTS
        and await cmd.has_any_item(list(MAGE_NAMES))
        and mage_points >= RANK_10_CLASS_POINTS
        and (cmd.get_player().LEVEL or 0) >= 30)

    if has_high_tier or has_both_rank10:
        cmd.bot.log("Acc is lvl 30+, skipping beginner items.")
        return

    cmd.bot.log('As the Acc is still "new", we\'re going todo the tutorial badges')

    report_once(cmd, "tutorial_badges",
                "Tutorial.Badges (Story/Tutorial) is not ported; the starter "
                "badges are skipped.")

    await _starter_slots(cmd)

    cmd.bot.log("Starting out acc:\n\tGoals: Ninja class & Mage Class")

    await farm_experience(cmd, 10)

    cmd.bot.log("Getting Started: Beginner Levels/Equipment")

    if not await cmd.has_any_item(list(ROGUE_NAMES)):
        cmd.bot.log("Getting rogue.. so we can get ninja (there's a 10k hp "
                    "\"boss\" to kill during the \"Hit Job\" quest.)")
        await adv_buy_item(cmd, ROGUE_SHOP, "Rogue", map_name=CLASSHALLA)

    if not await cmd.has_any_item(list(NINJA_NAMES)):
        cmd.bot.log("Getting starter Dodge class (Ninja)")
        await rank_up_class(cmd, "Rogue")
        await farm_experience(cmd, 25)
        await set_class(cmd)
        report_once(cmd, "mazumi",
                    f"Mazumi.MazumiQuests is not ported, so the {NINJA_NAME} shop "
                    f"({CLASSHALLA} {NINJA_SHOP}) would refuse the purchase; it is "
                    f"skipped.")

    await set_class(cmd)

    if not await cmd.has_any_item(list(MAGE_NAMES)):
        cmd.bot.log("Getting Starter Farm class (Mage)")
        await adv_buy_item(cmd, MAGE_SHOP, MAGE_ITEM_ID, map_name=CLASSHALLA,
                           shop_item_id=MAGE_SHOP_ITEM_ID)

    await set_class(cmd)


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

    # ``bool HasEnhancedThisBracket`` -- the source's own field, reset at the end
    # of every bracket.
    has_enhanced_this_bracket = False

    for level in LEVEL_BRACKETS:
        if (cmd.get_player().LEVEL or 0) > 75:
            has_enhanced_this_bracket = True

        # ``Adv.SmartEnhance(Bot.Player.CurrentClass?.Name)`` at the start of a
        # bracket, when this bracket has not enhanced yet or any worn item is
        # behind the player's level.
        if (not has_enhanced_this_bracket
                or any(item.enh_level < (cmd.get_player().LEVEL or 0)
                       for item in cmd.bot.player.INVENTORY)):
            await smart_enhance(cmd, _current_class_name(cmd))
            has_enhanced_this_bracket = True

        await farm_experience(cmd, level)

        handler = LEVEL_HANDLERS.get(level)
        if handler is not None:
            cmd.bot.log(f"Level Handler: {level} bracket")
            await handler(cmd)
            await bank_all_unused_classes(cmd)

        has_enhanced_this_bracket = False


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
    await gear_store(cmd)

    await level_1_to_30(cmd)
    await level_30_to_75(cmd)
    await level_75_to_100(cmd)
    await end_game(cmd)
    await outfit(cmd)
    await pets(cmd, PET_HOT_MAMA)
    await pets(cmd, PET_AKRILOTH)

    await gear_store(cmd, restore=True, enh_after=True)


#: The two purchases inside the bracket handlers that need no other kit.
MUSEUM_SHOP = 631
AWETHUR_ITEM = "Awethur's Accoutrements"
BLOODTUSK_SHOP = 308
HORC_EVADER = "Horc Evader"

#: ``Handlelevel80`` checks for either spelling, and stops if it finds one.
VOID_HIGHLORD_NAMES = ("Void Highlord", "Void Highlord (IoDA)")


async def _handle_level_30(cmd: Command) -> None:
    """``HandleLevel30``: Master Ranger, Dragonslayer and the Blade of Awe rep."""
    if not (await cmd.has_item("Master Ranger")
            and any_rank10(cmd, ["Master Ranger"])):
        if await cmd.has_item("Venom Head"):
            await cmd.sell_item("Venom Head")
        cmd.bot.log("Level 30: Acquiring Master Ranger")
        await set_class(cmd)
        await get_mr(cmd)

    if not (await cmd.has_item("Dragonslayer")
            and any_rank10(cmd, ["Dragonslayer"])):
        cmd.bot.log("Level 30: Acquiring Dragonslayer")
        await set_class(cmd)
        report_once(cmd, "dragonslayer",
                    "Dragonslayer.GetDragonslayer is not ported; Dragonslayer is "
                    "not farmed.")

    cmd.bot.log("Level 30: Farming Blade of Awe Rep for enhancements & sword")
    await set_class(cmd)
    report_once(cmd, "blade_of_awe_rep",
                "CoreFarms.BladeofAweREP is not ported; the Blade of Awe rep is "
                "not farmed.")
    await adv_buy_item(cmd, MUSEUM_SHOP, AWETHUR_ITEM, map_name="museum")
    await forge_helm_enhancement(cmd)


async def _handle_level_50(cmd: Command) -> None:
    """``HandleLevel50``: Scarlet Sorceress, Dragonslayer General, Burning Blade."""
    if not (await cmd.has_item("Scarlet Sorceress")
            and any_rank10(cmd, ["Scarlet Sorceress"])):
        cmd.bot.log("Level 50: Acquiring Scarlet Sorceress")
        await set_class(cmd)
        report_once(cmd, "scarlet_sorceress",
                    "ScarletSorceress.GetSSorc needs CoreToD.TowerofMirrors and "
                    "BloodSorceress.GetBSorc; neither is ported.")

    if not (await cmd.has_item("Dragonslayer General")
            and any_rank10(cmd, ["Dragonslayer General"])):
        cmd.bot.log("Level 50: Acquiring Dragonslayer General")
        await set_class(cmd)
        await get_ds_general(cmd)

    cmd.bot.log("Level 50: Acquiring Burning Blade")
    await set_class(cmd)
    await get_burning_blade(cmd)


async def _handle_level_55(cmd: Command) -> None:
    """``HandleLevel55``: Blaze Binder and Cryomancer."""
    if not (await cmd.has_item("Blaze Binder")
            and any_rank10(cmd, ["Blaze Binder"])):
        cmd.bot.log("Level 55: Acquiring Blaze Binder")
        await set_class(cmd)
        report_once(cmd, "blaze_binder",
                    "BlazeBinder.GetClass is not ported.")

    if not (await cmd.has_item("Cryomancer")
            and any_rank10(cmd, ["Cryomancer"])):
        cmd.bot.log("Level 55: Acquiring Cryomancer")
        await set_class(cmd)
        report_once(
            cmd, "cryomancer",
            "Cryomancer.DoCrymancer needs Glac.DoAll (the Glacera story) before "
            "the Cryomancer daily; that story is not ported.")


async def _handle_level_60(cmd: Command) -> None:
    """``HandleLevel60``: DragonSoul Shinobi, then the Lacerate enhancement."""
    if not (await cmd.has_item("DragonSoul Shinobi")
            and any_rank10(cmd, ["DragonSoul Shinobi"])):
        cmd.bot.log("Level 60: Acquiring DragonSoul Shinobi")
        await set_class(cmd)
        report_once(cmd, "dragonsoul_shinobi",
                    "DragonShinobi.GetDSS is not ported.")

    await lacerate(cmd)


async def _handle_level_65(cmd: Command) -> None:
    """``HandleLevel65``: Glacial Berserker."""
    if not (await cmd.has_item("Glacial Berserker")
            and any_rank10(cmd, ["Glacial Berserker"])):
        cmd.bot.log("Level 65: Acquiring Glacial Berserker")
        await set_class(cmd)
        report_once(cmd, "glacial_berserker",
                    "GlacialBerserker.GetGB is not ported.")


async def _handle_level_70(cmd: Command) -> None:
    """``HandleLevel70``: Horc Evader, the easy forge enhancements, ArchPaladin."""
    if not (await cmd.has_item(HORC_EVADER)
            and any_rank10(cmd, [HORC_EVADER])):
        cmd.bot.log("Geting Horc Evader so we can attemp to kill Ultra Chaos "
                    "Alteon during the story to get AP")
        await adv_buy_item(cmd, BLOODTUSK_SHOP, HORC_EVADER, map_name="bloodtusk")
        await set_class(cmd)

    cmd.bot.log("unlocking the easy lvl 70 forge enhs")
    await smite(cmd)
    await vim(cmd)
    await pneuma(cmd)
    await examen(cmd)
    await anima(cmd)

    if not (await cmd.has_item("ArchPaladin")
            and any_rank10(cmd, ["ArchPaladin"])):
        cmd.bot.log("Level 70: Acquiring ArchPaladin")
        await set_class(cmd)
        report_once(cmd, "archpaladin", "ArchPaladin.GetAP is not ported.")


async def _handle_level_75(cmd: Command) -> None:
    """``HandleLevel75``: Archfiend DoomLord and Archfiend itself."""
    if not (await cmd.has_item("Archfiend DoomLord")
            and any_rank10(cmd, ["Archfiend"])):
        cmd.bot.log("Level 75: Acquiring Archfiend DoomLord for 35% more damage "
                    "to any monster, and gives 25% more class points, XP, gold, "
                    "and rep when equipped")
        await set_class(cmd)
        await afdl(cmd)

    if not (await cmd.has_item("Archfiend")
            and any_rank10(cmd, ["Archfiend"])):
        cmd.bot.log("Level 75: Acquiring Archfiend")
        await set_class(cmd)
        report_once(cmd, "archfiend", "Archfiend.GetArchfiend is not ported.")


async def _handle_level_80(cmd: Command) -> None:
    """``Handlelevel80``: Void Highlord, through the ported ``CoreVHL``.

    The reference's log line here says "Dragon of Time found but not rank 10" --
    in a branch that is about Void Highlord.  It is copied as it stands, the way
    every other source line is.
    """
    if await cmd.has_any_item(list(VOID_HIGHLORD_NAMES)):
        cmd.bot.log("Dragon of Time found but not rank 10 - ranking up")
        await set_class(cmd)
        return

    cmd.bot.log("Bracket level [80]; Attemping to aquire VHL (Elders' bloods are "
                "a daily, this will take a total of 17 days ( minus your current "
                "roents/elders' quantity))")
    await get_vhl(cmd)


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
