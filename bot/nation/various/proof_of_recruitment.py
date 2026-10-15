"""Proof of Recruitment -- quest 4785's five rewards, behind the ArchToken chain.

Port of ``Nation/Various/ProofOfRecruitmentQuest.cs``.

Eleven quests (4751-4761) hand over the ArchTokens in turn, each one the next
one's requirement, and then quest 4785 is turned in until every reward is at its
max stack.  The file's own ``LegacyQuestManager`` sorts that chain by which
quest's reward the next one needs; they are written in that order here, which is
the order both of the reference's copies of the chain list them in.

Note:
    Quest 4752 needs five ``Doomwood Token`` -- a temp item out of the DoomWood
    PvP arena, which nothing here can farm.  The reference stops the bot at that
    point, and so does this, with the same reason.
"""
from typing import Sequence, Tuple

from core.command import Command
from bot.core_farms import bludrut_brawl_boss
from bot.nation.core_nation import emblem_of_nulgath
from templates.hunt import hunt_item

#: What quest 4785 pays out, one at a time up to each one's max stack.
REWARDS: Tuple[str, ...] = (
    "Tainted Gem",
    "Dark Crystal Shard",
    "Diamond of Nulgath",
    "Gem of Nulgath",
    "Unidentified 13",
)

#: The drops the chain and the reward quest hand over.
REQUIRED_ITEMS: Tuple[str, ...] = (
    "ArchToken I", "ArchToken II", "Portal Key", "ArchToken III", "ArchToken IV",
    "ArchToken V", "ArchToken VI", "ArchToken VII", "ArchToken VIII",
    "ArchToken IX", "ArchToken X", "ArchToken XI",
)

#: Quest 4785 itself and what one turn-in needs.
PROOF_QUEST = 4785
PROOF_SEALS = ("Fiend Seal", 15)
PROOF_HUNTS = (("Defeat the TR8T0R", 15, "ArchPortal", "Skull Warrior"),)

#: Quest 4752's unfarmable requirement.
DOOMWOOD_QUEST = 4752
DOOMWOOD_TOKEN = "Doomwood Token"
DOOMWOOD_QTY = 5

#: The chain: ``(quest, token, brawl trophies, hunts, map items)`` where a hunt is
#: ``(item, qty, map, monster)`` and a map item ``(item id, qty, map)``.
CHAIN: Tuple[Tuple[int, str, int, Sequence, Sequence], ...] = (
    (4751, "ArchToken I", 0,
     (("Monsters Slain", 8, "ArchPortal", "Skull Warrior"),), ()),
    (4752, "ArchToken II", 0, (), ()),
    (4753, "ArchToken III", 30, (), ()),
    (4754, "ArchToken IV", 0,
     (("Defeated Legion Spies", 8, "ArchPortal", "Legion Spy"),), ()),
    (4755, "ArchToken V", 0,
     (("Death's Head Head", 1, "citadel", "Death's Head"),
      ("Infernal Fiend Head", 1, "EvilWarDage", "Infernalfiend"),
      ("Nulgath's Redemption Head", 1, "EvilWarNul", "Nulgath's Redemption")),
     ()),
    (4756, "ArchToken VI", 0,
     (("Blade Master's Blood", 1, "EvilWarNul", "Blade Master"),
      ("Legion's Crown", 1, "EvilWarNul", "Undead Legend"),
      ("Saber of the Traveler", 1, "EvilWarNul", "Laken")), ()),
    (4757, "ArchToken VII", 0,
     (("Void Energy", 8, "Void", "Void Elemental"),),
     ((4178, 8, "ArchPortal"),)),
    (4758, "ArchToken VIII", 0,
     (("Dusty Bone Marrow", 5, "ArchPortal", "Skull Warrior"),
      ("Mummified Gray Matter", 5, "ArchPortal", "Legion Guard")), ()),
    (4759, "ArchToken IX", 0,
     (("Legion Skull", 1, "ArchPortal", "Skull Warrior"),),
     ((4179, 12, "ArchPortal"),)),
    (4760, "ArchToken X", 0,
     (("Undead Guards Souls", 8, "ArchPortal", "Legion Guard"),
      ("Skull Warriors Souls", 10, "ArchPortal", "Skull Warrior"),
      ("Hidden Legion Spy Souls", 6, "ArchPortal", "Legion Spy"),
      ("Soul of the Death's Head", 1, "citadel", "Death's Head")), ()),
    (4761, "ArchToken XI", 0,
     (("High Legion Inquisitor Defeated", 1, "ArchPortal",
       "High Legion Inquisitor"),), ()),
)


async def main(cmd: Command):
    cmd.add_drop(list(REQUIRED_ITEMS) + list(REWARDS))
    if not await arch_tokens(cmd):
        return

    await cmd.ensure_accept_quest(PROOF_QUEST)      # accepts, so rewards load
    entries = cmd.get_quest_reward_entries(PROOF_QUEST)
    if not entries:
        print(f"[nation] quest {PROOF_QUEST} did not load; nothing farmed.")
        return
    cmd.add_drop([name for _, name, _ in entries])

    for item_id, name, stack in entries:
        if name not in REWARDS:
            continue
        if await cmd.has_item(name, stack):
            print(f"[nation] {name} is at max stack; next reward.")
            continue

        print(f"[nation] farming {name} to its max stack from quest "
              f"{PROOF_QUEST}")
        cmd.farming_logger(name, stack)
        while cmd.is_still_connected() and not await cmd.has_item(name, stack):
            await cmd.ensure_accept_quest(PROOF_QUEST)
            await hunt_item(cmd, PROOF_SEALS[0], PROOF_SEALS[1], "shadowblast",
                            cell="r13", pad="Left", monster_name="*",
                            is_temp=False)
            await emblem_of_nulgath(cmd, 1)
            for item, qty, map_name, monster in PROOF_HUNTS:
                await hunt_item(cmd, item, qty, map_name, monster_name=monster,
                                is_temp=False)
            await cmd.ensure_turn_in_quest(PROOF_QUEST)


async def arch_tokens(cmd: Command) -> bool:
    """The eleven token quests, in order, skipping the ones already done.

    Returns:
        bool: False when quest 4752's Doomwood Token is missing -- the reference
        stops the bot there, and there is nothing here that can farm it.
    """
    for quest_id, token, brawl, hunts, map_items in CHAIN:
        if not cmd.is_still_connected():
            return False
        if await cmd.is_completed_before(quest_id):
            continue

        if quest_id == DOOMWOOD_QUEST and not await cmd.has_item(
                DOOMWOOD_TOKEN, DOOMWOOD_QTY):
            print(f"[nation] quest {quest_id} ({token}) needs "
                  f"'{DOOMWOOD_TOKEN} x{DOOMWOOD_QTY}', a temp item from the "
                  f"DoomWood PvP arena that nothing here can farm. Stopping.")
            return False

        print(f"[nation] {token}: quest {quest_id}")
        await cmd.ensure_accept_quest(quest_id)

        if brawl:
            if not await bludrut_brawl_boss(cmd, quant=brawl):
                return False

        for item_id, qty, map_name in map_items:
            while cmd.is_still_connected() and cmd.is_not_in_map(map_name):
                await cmd.join_map(map_name)
            for _ in range(qty):
                await cmd.get_map_item(item_id)

        for item, qty, map_name, monster in hunts:
            await hunt_item(cmd, item, qty, map_name, monster_name=monster,
                            is_temp=False)

        await cmd.ensure_turn_in_quest(quest_id)

    return True
