"""Lord of Order -- the ten-quest daily chain, then the class.

Port of ``Dailies/LordOfOrder.cs``.  One quest per day: the loop below runs the
first one that is *available and not completed* and then returns, exactly as the
reference does, so a single run makes one day's progress.  ``get_extras=True``
keeps going until all of quest 7165's rewards are owned.

Dependencies it reaches and where they live here:
``CitadelRuins.MurrysQuests``/``PolishsQuestsCitadelRuins`` ->
:mod:`bot.story.nation.citadel_ruins`; ``DragonFableOriginsAll`` ->
:mod:`bot.story.dragonfable_origins`; ``Core.KillKitsune``/``KillXiang`` ->
``bot.core_bots``.

``Bot.Quests.IsAvailable`` has no client to ask, so "available" is the accept
probe: a quest the server refuses is skipped, and because every later quest of
the chain is gated on the previous one, the whole loop then does nothing -- which
is the reference's behaviour on a day when nothing is ready.
"""
from bot.core_advanced import buy_item as adv_buy_item
from bot.core_advanced import gear_store
from bot.core_advanced import rank_up_class as advance_class
from bot.core_bots import (ensure_complete_choose, equip_class, kill_kitsune,
                           kill_xiang, wait_for_item)
from bot.core_farms import farm_experience, fishing_rep
from bot.script_log import ScriptLog
from bot.story.dragonfable_origins import do_all as dragonfable_origins_all
from bot.story.nation.citadel_ruins import (murrys_quests,
                                            polishs_quests_citadel_ruins)
from core.command import Command
from templates.hunt import hunt_item

TAG = "Lord of Order"

LOO_CLASS = "Lord of Order"
#: ``LOO Quest ItemID`` and the collector chest, the two "already owned" marks.
LOO_QUEST_ITEM = 50741
LOO_CHEST_ITEM = 50576
LOO_FINAL_QUEST = 7165
LOO_LEVEL = 50

#: The chain, in order; each one is a separate day.
LOO_QUESTS = (7156, 7157, 7158, 7159, 7160, 7161, 7162, 7163, 7164, 7165)
#: The source's own per-step line, kept word for word.
LOO_DONE_LINES = {
    7156: "[1/10] Heart of Servitude [7156] complete.",
    7157: "[2/10] Spirit of Justice [7157] complete.",
    7158: "[3/10] Purification of Chaos [7158] complete.",
    7159: "[4/10] Steadfast Will [7159] complete.",
    7160: "[5/10] Strike of Order [7160] complete.",
    7161: "[6/10] Harmony [7161] complete.",
    7162: "[7/10] Ordinance [7162] complete.",
    7163: "[8/10] Axiom [7163] complete.",
    7164: "[9/10] Blessing of Order [7164] complete.",
    7165: "[10/10] The Final Challenge [7165] complete.",
}


def _owned_by_id(cmd: Command, item_id: int) -> bool:
    player = cmd.bot.player
    return (player.get_item_inventory_by_id(item_id) is not None
            or player.get_item_bank_by_id(item_id) is not None)


def _owns_all(cmd: Command, names) -> bool:
    return all(cmd.is_in_inventory_or_bank(name) for name in names)


async def _complete_and_bank(cmd: Command, quest_id: int) -> bool:
    if await cmd.ensure_turn_in_quest(quest_id) is False:
        ScriptLog(cmd, TAG).warning(f"quest {quest_id} could not be turned in")
        return False
    rewards = cmd.get_quest_rewards(quest_id)
    if rewards:
        await cmd.inv_to_bank(rewards)
    return True


# ---------------------------------------------------------------------------
# One body per quest, in the source's order
# ---------------------------------------------------------------------------
async def _q7156(cmd: Command) -> None:
    cmd.add_drop(cmd.get_quest_rewards(7156))
    await equip_class(cmd, solo=True)
    await hunt_item(cmd, "Pristine Blades of Order", 1, "watchtower",
                    monster_name="Chaorrupted Knight", is_temp=False)
    await adv_buy_item(cmd, 1221, "Dreadrock Donation Receipt",
                       map_name="dreadrock")
    await hunt_item(cmd, "Deadmoor Spirits Helped", 1, "deadmoor",
                    monster_name="Banshee Mallora", is_temp=False)
    await murrys_quests(cmd)
    await polishs_quests_citadel_ruins(cmd)
    if not await cmd.has_item("Mage's Gratitude"):
        cmd.add_drop("Mage's Gratitude")
        if await cmd.ensure_accept_quest(6182) is not False:
            await hunt_item(cmd, "Enn'tröpy Defeated", 1, "citadelruins",
                            monster_name="Enn'tröpy")
            await cmd.ensure_turn_in_quest(6182)
    await adv_buy_item(cmd, 614, "Ravenscar's Truth", map_name="ravenscar")


async def _q7157(cmd: Command) -> None:
    cmd.add_drop(cmd.get_quest_rewards(7157))
    await equip_class(cmd, solo=True)
    await hunt_item(cmd, "Warden Elfis Detained", 1, "dwarfprison",
                    monster_name="Warden Elfis", is_temp=False)
    await hunt_item(cmd, "Piggy Drake Punished", 1, "prison",
                    monster_name="Piggy Drake", is_temp=False)
    await hunt_item(cmd, "Mysterious Stranger Foiled", 1, "mysteriousdungeon",
                    monster_name="Mysterious Stranger", is_temp=False)
    await hunt_item(cmd, "Calico Cobby Crushed", 1, "dreammaster",
                    monster_name="Calico Cobby", is_temp=False)


async def _q7158(cmd: Command) -> None:
    cmd.add_drop(cmd.get_quest_rewards(7158))
    await equip_class(cmd, solo=True)
    await adv_buy_item(cmd, 1951, "Chaoroot", 15,
                       map_name="tercessuinotlim")
    await hunt_item(cmd, "Chaotic War Essence", 15, "chaosboss",
                    monster_name="Ultra Chaos Warlord", is_temp=False)
    await hunt_item(cmd, "Chaorrupting Particles", 15, "shadowgates",
                    monster_name="Chaorruption", is_temp=False)
    # ``Bot.Quests.UpdateQuest(2814)`` is a client write with no counterpart;
    # 2814 is Lionfang's last quest, which the port completes in 13LoC.
    if not await cmd.is_completed_before(2814):
        ScriptLog(cmd, TAG).warning(
            "quest 2814 (Chaos Lord Lionfang) is not done; its drop may not be "
            "available yet -- Core13LoC's Lionfang covers it.")
    await hunt_item(cmd, "Purified Raindrop", 45, "stormtemple",
                    monster_name="Chaos Lord Lionfang", is_temp=False)


async def _q7159(cmd: Command) -> None:
    cmd.add_drop(cmd.get_quest_rewards(7159))
    await equip_class(cmd, solo=True)
    await hunt_item(cmd, "Gaiazor's Cornerstone", 1, "gaiazor",
                    monster_name="Gaiazor", is_temp=False)
    # ``Bot.Quests.UpdateQuest(4361)`` -- client write, no counterpart here.
    await cmd.sleep(2000)
    await hunt_item(cmd, "Dakka's Crystal", 1, "treetitanbattle",
                    monster_name="Dakka the Dire Dragon", is_temp=False)
    await hunt_item(cmd, "Andre's Necklace Fragment", 1, "andre",
                    monster_name="Giant Necklace", is_temp=False)
    await cmd.jump_cell(cmd.bot.player.CELL, cmd.bot.player.PAD)
    await hunt_item(cmd, "Desolich's Skull", 1, "desolich",
                    monster_name="Desolich", is_temp=False)


async def _q7160(cmd: Command) -> None:
    cmd.add_drop(cmd.get_quest_rewards(7160))
    await equip_class(cmd, solo=True)
    await kill_kitsune(cmd, "Hanzamune Dragon Koi Blade")
    await hunt_item(cmd, "The Supreme Arcane Staff", 1, "ledgermayne",
                    monster_name="Ledgermayne", is_temp=False)
    await hunt_item(cmd, "Dragonoid of Hours", 1, "mqlesson",
                    monster_name="Dragonoid", is_temp=False)
    if not await cmd.has_item("Safiria's Spirit Orb"):
        cmd.add_drop("Safiria's Spirit Orb")
        await cmd.join_map("maxius")
        await cmd.get_map_item(5470)
        await wait_for_item(cmd, "Safiria's Spirit Orb")
    await dragonfable_origins_all(cmd)
    if not await cmd.has_item("Ice Katana"):
        cmd.add_drop("Ice Katana")
        if await cmd.ensure_accept_quest(6319) is not False:
            await equip_class(cmd)
            await hunt_item(cmd, "Inferno Heart", 1, "drakonnan",
                            monster_name="Living Fire")
            await cmd.ensure_turn_in_quest(6319)


async def _q7161(cmd: Command) -> None:
    cmd.add_drop(cmd.get_quest_rewards(7161))
    await equip_class(cmd, solo=True)
    await hunt_item(cmd, "Unity of Life", 1, "elemental",
                    monster_name="Tree of Destiny", is_temp=False)
    await hunt_item(cmd, "Harmony of Solace", 1, "orchestra",
                    monster_name="Faust", is_temp=False)
    await equip_class(cmd)
    await hunt_item(cmd, "Teamwork Observed", 100, "cathedral",
                    monster_name="Pactagonal Knight", is_temp=False)
    await equip_class(cmd, solo=True)
    await hunt_item(cmd, "Scroll of Enchantment", 1, "goose",
                    monster_name="Queen's ArchSage", is_temp=False)


async def _q7162(cmd: Command) -> None:
    cmd.add_drop(cmd.get_quest_rewards(7162))
    await equip_class(cmd)
    await hunt_item(cmd, "Acolyte's Braille", 1, "newfinale",
                    monster_name="Alliance Healer", is_temp=False)
    await hunt_item(cmd, "Suppressed Drows", 50, "wardwarf",
                    monster_name="Drow Assassin", is_temp=False)
    await hunt_item(cmd, "Suppressed Undead", 50, "warundead",
                    monster_name="Skeletal Fire Mage", is_temp=False)
    await hunt_item(cmd, "Suppressed Horcs", 50, "warhorc",
                    monster_name="Horc Warrior", is_temp=False)
    await hunt_item(cmd, "Suppressed Weavers", 50, "weaverwar",
                    monster_name="Weaver Queen's Hound", is_temp=False)
    await equip_class(cmd, solo=True)
    await hunt_item(cmd, "Strength of Resilience", 1, "extriki",
                    monster_name="Extriki", is_temp=False)


async def _q7163(cmd: Command) -> None:
    cmd.add_drop(cmd.get_quest_rewards(7163))
    await equip_class(cmd, solo=True)
    await hunt_item(cmd, "Law of Nature", 1, "elfhame",
                    monster_name="Guardian Spirit", is_temp=False)
    await hunt_item(cmd, "Law of Time", 1, "deepchaos",
                    monster_name="Kathool", is_temp=False)
    await hunt_item(cmd, "Law of Gravity", 1, "necrocavern",
                    monster_name="ShadowStone Support", is_temp=False)
    await hunt_item(cmd, "Law of Relativity", 1, "blackholesun",
                    monster_name="Reflecteract", is_temp=False)
    await hunt_item(cmd, "Law of Conservation of Energy", 1, "thunderfang",
                    monster_name="Tonitru", is_temp=False)
    await hunt_item(cmd, "Law of Low Drop Rates", 100, "lair",
                    monster_name="Red Dragon", is_temp=False)


async def _q7164(cmd: Command) -> None:
    cmd.add_drop(cmd.get_quest_rewards(7164))
    await equip_class(cmd, solo=True)
    await hunt_item(cmd, "Weapon Imprint", 15, "doomvaultb", cell="r26",
                    pad="Left", monster_name="Undead Raxgore", is_temp=False)
    await fishing_rep(cmd, 7)
    await adv_buy_item(cmd, 363, "Lure of Order", map_name="greenguardwest")
    await gear_store(cmd)
    await kill_xiang(cmd, "Quixotic Mana Essence", 10, True)
    await gear_store(cmd, restore=True, enh_after=True)
    await equip_class(cmd, solo=True)
    await hunt_item(cmd, "Inversion Infusion", 5, "yasaris",
                    monster_name="Serepthys", is_temp=False)


async def _q7165(cmd: Command) -> bool:
    """``The Final Challenge``: the class is the chosen reward."""
    cmd.add_drop(cmd.get_quest_rewards(LOO_FINAL_QUEST))
    await equip_class(cmd, solo=True)
    await hunt_item(cmd, "Champion of Chaos Confronted", 1, "ultradrakath",
                    monster_name="Champion of Chaos", is_temp=False)
    cmd.add_drop([LOO_QUEST_ITEM])
    if not await cmd.is_completed_before(LOO_FINAL_QUEST):
        if await cmd.ensure_turn_in_quest(LOO_FINAL_QUEST,
                                          LOO_QUEST_ITEM) is False:
            return False
        await wait_for_item(cmd, LOO_CLASS)
        await ensure_complete_choose(cmd, LOO_FINAL_QUEST, LOO_CLASS)
        rewards = [name for name in cmd.get_quest_rewards(LOO_FINAL_QUEST)
                   if name != LOO_CLASS]
        if rewards:
            await cmd.inv_to_bank(rewards)
    return True


BODIES = {7156: _q7156, 7157: _q7157, 7158: _q7158, 7159: _q7159,
          7160: _q7160, 7161: _q7161, 7162: _q7162, 7163: _q7163,
          7164: _q7164}


async def get_loo(cmd: Command, rank_up_class: bool = True,
                  get_extras: bool = False) -> None:
    """``LordOfOrder.GetLoO``: the next daily in the chain, then the class.

    Args:
        cmd (Command): Facade to act through.
        rank_up_class (bool): Carry the class to rank 10 once it is owned.
        get_extras (bool): Keep going until quest 7165's rewards are all owned.
    """
    log = ScriptLog(cmd, TAG)

    owns_mark = (_owned_by_id(cmd, LOO_QUEST_ITEM)
                 or _owned_by_id(cmd, LOO_CHEST_ITEM))
    if not get_extras and owns_mark \
            and await cmd.is_completed_before(LOO_FINAL_QUEST):
        if rank_up_class:
            await advance_class(cmd, LOO_CLASS)
        return
    if get_extras and await cmd.is_completed_before(LOO_FINAL_QUEST) \
            and _owns_all(cmd, cmd.get_quest_rewards(LOO_FINAL_QUEST)):
        if rank_up_class:
            await advance_class(cmd, LOO_CLASS)
        log.info("All desired rewards owned for LOO.")
        return

    log.info("Daily: Lord of Order Class")
    log.info("It's a DAILY quest chain, 10 quests total, up to 7165: one "
             "completes per run, per day.")

    await farm_experience(cmd, LOO_LEVEL)

    for quest_id in LOO_QUESTS:
        if await cmd.is_completed_before(quest_id):
            continue
        if await cmd.ensure_accept_quest(quest_id) is False:
            continue

        log.info(f"Quest {quest_id} accepted.")
        if quest_id == LOO_FINAL_QUEST:
            ok = await _q7165(cmd)
            if not ok:
                return
            await _complete_and_bank(cmd, quest_id)
            log.success(LOO_DONE_LINES[quest_id])
            if rank_up_class:
                await advance_class(cmd, LOO_CLASS)
            return

        await BODIES[quest_id](cmd)
        if await _complete_and_bank(cmd, quest_id):
            log.success(LOO_DONE_LINES[quest_id])
        return


async def main(cmd: Command):
    await get_loo(cmd)


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
