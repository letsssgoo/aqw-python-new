"""ArchPaladin -- the seven-quest class from /darkthronehub.

Port of ``Good/ArchPaladin.GetAP``: Good reputation, the preparation branch
(non-member quests 5463-5466 or the member Silver-Palidin line), then quests
5467-5470 and the purchase.

Three substitutions, all reported in the source's own terms:
* ``Core.EquipClass(ClassType.Dodge)`` -> the **solo** class here: this engine has
  no DodgeClass (see ``bot/core_farms``' class note).
* ``Core.KillDoomKitten`` keeps its DoT class pick but uses the caller's normal
  skill rotation; the reference's per-class rotations are not reproduced.
* ``Bot.Quests.IsUnlocked(5467)`` has no client to ask, so "not done yet" stands
  in for it -- the same substitution ``bot/enhancements/lacerate.py`` documents.
  Each preparation quest guards itself, so a resumed account skips what it has.
"""
from typing import Optional

from bot.core_advanced import buy_item, gear_store
from bot.core_advanced import rank_up_class as advance_class
from bot.core_blod import unlock_mine_crafting
from bot.core_bots import chain_complete, equip_class, kill_doom_kitten
from bot.core_farms import battle_under_b, farm_gold, good_rep, spellcrafting_rep
from bot.core_story import CustomError, quest_progression
from bot.other.classes.paladin import get_paladin
from bot.story.xans_lair import do_all as xans_lair_do_all
from core.command import Command
from templates.hunt import hunt_item
from bot.script_log import ScriptLog
TAG = "ArchPaladin"

ARCH_PALADIN = "ArchPaladin"
#: ``Core.CheckInventory(36920)`` -- the class item, bought at the end.
CLASS_ITEM = 36920
BUY_MAP = "darkthronehub"
BUY_SHOP = 1303
BUY_SHOP_ITEM_ID = 21833

COMMANDMENT_QUEST = 5467
HYMN_QUEST = 5468
RIGHTEOUS_SEAL_QUEST = 5469
EDEN_QUEST = 5470
#: The preparation quests, non-member (5463-5466) / member (5471-5478).
NON_MEMBER_PREP = (5463, 5464, 5465, 5466)
SILVER_OATHS = ((5475, 5471), (5476, 5472), (5477, 5473))
APTITUDE_SILVER, APTITUDE_PLAIN = 5478, 5474


async def _quest(cmd: Command, quest_id: int, body) -> None:
    """``if (!Story.QuestProgression(q)) { accept; body; complete; }``."""
    if await quest_progression(cmd, quest_id):
        return
    if await cmd.ensure_accept_quest(quest_id) is False:
        raise CustomError(f"quest {quest_id} could not be accepted")
    await body()
    if await cmd.ensure_turn_in_quest(quest_id) is False:
        raise CustomError(f"quest {quest_id} could not be turned in")


async def _non_member_prep(cmd: Command) -> None:
    """``A Strong Base`` .. ``For Those Who Have Fallen`` (5463-5466)."""
    async def q5463() -> None:
        # two buys under one quest, as the source calls BuyQuest twice
        await buy_item(cmd, 288, "Stone Paladin Armor", map_name="temple")
        await farm_gold(cmd, 500_000)
        await buy_item(cmd, 1308, "Exalted Paladin Seal",
                       map_name="darkthronehub")

    await _quest(cmd, 5463, q5463)

    async def q5464() -> None:
        await unlock_mine_crafting(cmd)
        await battle_under_b(cmd, "Undead Energy", 1000)
        await equip_class(cmd, solo=True)
        await hunt_item(cmd, "Binky's Uni-horn", 1, "doomvault", cell="r5",
                        pad="Left", monster_name="Binky", is_temp=False)
        await hunt_item(cmd, "Desterrat Moya Tentacle", 1, "banished",
                        monster_name="Desterrat Moya")
        await hunt_item(cmd, "Dreadhaven Helm", 1, "dreadfight", cell="Enter",
                        pad="Spawn", monster_name="*")
        await gear_store(cmd)
        await kill_doom_kitten(cmd, "DoomKitten Claw", is_temp=True)
        await gear_store(cmd, restore=True, enh_after=True)
        await hunt_item(cmd, "Vordred's Skull", 1, "vordredboss",
                        monster_name="Vordred", is_temp=False)

    await _quest(cmd, 5464, q5464)

    async def q5465() -> None:
        await equip_class(cmd, solo=True)
        await hunt_item(cmd, "Pyromancer Artifact", 1, "xantown", cell="r8",
                        pad="Left", monster_name="Xan", is_temp=False)
        await cmd.jump_cell("r12", "Left")   # the map is aggro; r12 is safe
        await hunt_item(cmd, "Zephyrus Manifesto", 1, "dragonheart",
                        monster_name="Proto-Air Dracolich", is_temp=False)
        await hunt_item(cmd, "Karok's Glaceran Gem", 1, "northstar",
                        monster_name="Karok The Fallen", is_temp=False)
        await equip_class(cmd)
        await hunt_item(cmd, "Nightmare Kibble", 200, "thirdspell",
                        monster_name="Mana Phoenix", is_temp=False)
        await hunt_item(cmd, "Condensed Energy", 1, "thunderfang",
                        monster_name="Lightning Ball", is_temp=False)
        await hunt_item(cmd, "Crystallized Mana Catalyst", 1, "downward",
                        cell="r11", pad="Right",
                        monster_name="Crystal Mana Construct", is_temp=False)
        await hunt_item(cmd, "Just the Perfect Stick", 1, "farm",
                        monster_name="Treeant", is_temp=False)

    await _quest(cmd, 5465, q5465)

    async def q5466() -> None:
        await buy_item(cmd, 88, "Holy Hand Grenade", map_name="castle")
        await equip_class(cmd)
        await hunt_item(cmd, "Feather of Paradise", 20, "manor",
                        monster_name="Bird of Paradise", is_temp=False)
        await hunt_item(cmd, "Shoelace of a Fallen Paladin", 77, "doomwood",
                        cell="r6", pad="Right", monster_name="*",
                        is_temp=False)
        await equip_class(cmd, solo=True)
        await hunt_item(cmd, "Eternity Flame", 1, "fotia",
                        monster_name="Amia the Cult Leader", is_temp=False)

    await _quest(cmd, 5466, q5466)


async def _member_prep(cmd: Command) -> None:
    """The Silver Paladin line the reference runs instead for members."""
    if not await cmd.has_item("Silver Paladin"):
        await get_paladin(cmd, rank_up_class=False)

    silver = await cmd.has_item("Silver Paladin")
    for silver_quest, plain_quest in SILVER_OATHS:
        await chain_complete(cmd, silver_quest if silver else plain_quest)

    aptitude = APTITUDE_SILVER if silver else APTITUDE_PLAIN

    async def q_aptitude() -> None:
        await equip_class(cmd, solo=True)
        await hunt_item(cmd, "Primarch's Hilt", 1, "bosschallenge",
                        monster_name="Colossal Primarch", is_temp=False)
        await farm_gold(cmd, 500_000)
        await buy_item(cmd, 1308, "Exalted Paladin Seal",
                       map_name="darkthronehub")
        await hunt_item(cmd, "Condensed Mana", 1, "timevoid",
                        monster_name="Unending Avatar", is_temp=False)

    await _quest(cmd, aptitude, q_aptitude)


async def _commandment(cmd: Command) -> None:
    async def body() -> None:
        await equip_class(cmd, solo=True)
        await hunt_item(cmd, "Skill Observed", 1, "brightfall",
                        monster_name="Painadin Overlord", is_temp=False)
        await hunt_item(cmd, "Spirit of Vindication", 1, "citadel",
                        monster_name="Grand Inquisitor", is_temp=False)
        await hunt_item(cmd, "Radiant Blade Enhancement", 1, "alliance",
                        monster_name="Good Lieutenant", is_temp=False)

    await _quest(cmd, COMMANDMENT_QUEST, body)


async def _hymn_of_light(cmd: Command) -> None:
    async def body() -> None:
        await equip_class(cmd, solo=True)
        await hunt_item(cmd, "Divine Elixir", 1, "poisonforest",
                        monster_name="Xavier Lionfang", is_temp=False)
        await hunt_item(cmd, "Prayer of Salvation", 1, "ultraalteon",
                        monster_name="Ultra Chaos Alteon", is_temp=False)
        await equip_class(cmd)
        await hunt_item(cmd, "Acolyte's Braille", 1, "newfinale",
                        monster_name="Alliance Healer", is_temp=False)
        await hunt_item(cmd, "Innocence", 25, "skytower",
                        monster_name="Dove", is_temp=False)

    await _quest(cmd, HYMN_QUEST, body)


async def _righteous_seal(cmd: Command) -> None:
    async def body() -> None:
        cmd.add_drop(["Scroll of Ethereal Slumber", "Fists of Fire",
                      "Holy Magic Attunement", "Ring of Mana Transposition"])
        await xans_lair_do_all(cmd)
        await equip_class(cmd, solo=True)
        await hunt_item(cmd, "Fists of Fire", 1, "xancave",
                        monster_name="Shurpu Ring Guardian", is_temp=False)

        if not await cmd.has_item("Scroll of Ethereal Slumber"):
            if not await cmd.has_item("Archmage Ink"):
                await spellcrafting_rep(cmd, 8)
                if await cmd.has_item("Mystic Shards", 2):
                    await buy_item(cmd, 549, "Archmage Ink",
                                   map_name="spellcraft")
                else:
                    if not await cmd.has_item("Arcane Quill"):
                        await farm_gold(cmd, 100_000)
                        await buy_item(cmd, 693, "Gold Voucher 100k",
                                       map_name="spellcraft")
                        await buy_item(cmd, 693, 17391, map_name="spellcraft",
                                       shop_item_id=7685)
                    await buy_item(cmd, 622, "Archmage Ink",
                                   map_name="spellcraft")
            if not await cmd.has_item("Archmage Ink"):
                await hunt_item(cmd, "Mystic Shards", 2, "underworld",
                                monster_name="Skull Warrior", is_temp=False)
                await buy_item(cmd, 549, "Archmage Ink",
                               map_name="dragonrune")
            await chain_complete(cmd, 2347)
            for name in ("Archmage Ink", "Mystic Shards"):
                held = cmd.get_quant_item(name)
                if held:
                    await cmd.sell_item(name, held)

        await equip_class(cmd)
        await hunt_item(cmd, "Holy Magic Attunement", 1, "onslaughttower",
                        monster_name="Golden Caster", is_temp=False)
        await equip_class(cmd, solo=True)
        await hunt_item(cmd, "Ring of Mana Transposition", 1, "palace",
                        monster_name="Pettivox", is_temp=False)

    await _quest(cmd, RIGHTEOUS_SEAL_QUEST, body)
    if await cmd.has_item("Scroll of Ethereal Slumber"):
        await cmd.sell_item("Scroll of Ethereal Slumber", 1)


async def _sacred_magic_eden(cmd: Command) -> None:
    async def body() -> None:
        await equip_class(cmd, solo=True)
        await hunt_item(cmd, "Sacred Tome", 1, "seraph",
                        monster_name="Adventus", is_temp=False)
        await equip_class(cmd)
        await hunt_item(cmd, "Paladaffodil", 25, "marsh",
                        monster_name="Marsh Tree", is_temp=False)
        await hunt_item(cmd, "Spirit Lotus", 25, "wanders", cell="r5",
                        pad="Left", monster_name="Lotus Spider", is_temp=False)
        await hunt_item(cmd, "Radiant Magnolia", 25, "bloodtusk",
                        monster_name="Trollola Plant", is_temp=False)
        await hunt_item(cmd, "Cyanoblossom", 25, "gaiazor",
                        monster_name="Wisterrora", is_temp=False)
        await equip_class(cmd, solo=True)
        await hunt_item(cmd, "BrightOak Forest Sapling", 1, "gaiazor",
                        monster_name="Nevanna", is_temp=False)
        await hunt_item(cmd, "Forbidden Demon Seal", 1, "infernalspire",
                        monster_name="Malxas", is_temp=False)

    await _quest(cmd, EDEN_QUEST, body)


async def get_ap(cmd: Command, rank_up_class: bool = True,
                 armor_only: bool = False) -> None:
    """``ArchPaladin.GetAP``.

    Args:
        cmd (Command): Facade to act through.
        rank_up_class (bool): Carry the class to rank 10 afterwards.
        armor_only (bool): The reference's ``ArmorOnly`` -- stop before the buy.
    """
    if await cmd.has_item_id(CLASS_ITEM):
        if rank_up_class:
            await advance_class(cmd, ARCH_PALADIN)
        return

    await good_rep(cmd)

    # ``!Bot.Quests.IsUnlocked(5467)``: "not done yet" is this engine's stand-in.
    if not await cmd.is_completed_before(COMMANDMENT_QUEST):
        if cmd.get_player().is_member:
            await _member_prep(cmd)
        else:
            await _non_member_prep(cmd)

    await _commandment(cmd)
    await _hymn_of_light(cmd)
    await _righteous_seal(cmd)
    await _sacred_magic_eden(cmd)

    if armor_only:
        return

    await buy_item(cmd, BUY_SHOP, CLASS_ITEM, map_name=BUY_MAP,
                   shop_item_id=BUY_SHOP_ITEM_ID)
    if rank_up_class:
        await gear_store(cmd)
        await cmd.equip_item(ARCH_PALADIN)
        await advance_class(cmd, ARCH_PALADIN)
        await gear_store(cmd, restore=True, enh_after=True)


async def main(cmd: Command):
    await get_ap(cmd)
