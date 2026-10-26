"""``YokaiQuests`` -- ShogunWar, ShinrinGrove and Shadowfortress.

Port of ``Story/Yokai.cs``, all three regions in the source's order.  The
map-id hunts (``Core.HuntMonsterMapID``) resolve the item id from the accepted
quest's own payload, the same way :mod:`bot.story.throne_of_darkness.core_tod`
does.

One source quirk is kept: quest 6494 ends with ``Core.EnsureAccept(6494)`` again
instead of a turn-in, so it stays in progress -- the port does the same.
"""
from bot.core_bots import buy_item, equip_class
from bot.core_story import (CustomError, buy_quest, item_id_by_name, kill_quest,
                            map_item_quest, quest_progression)
from core.command import Command
from templates.hunt import hunt_item, hunt_item_by_id

SHOGUN_WAR = "shogunwar"
SHINRIN_GROVE = "shinringrove"
GREEN_SHELL = "greenshell"
HEIWA_VALLEY = "heiwavalley"
SHADOW_FORTRESS = "shadowfortress"


async def _quest(cmd: Command, quest_id: int, body) -> None:
    """``if (!Story.QuestProgression(q)) { accept; body; complete; }``."""
    if await quest_progression(cmd, quest_id):
        return
    if await cmd.ensure_accept_quest(quest_id) is False:
        raise CustomError(f"quest {quest_id} could not be accepted")
    await body()
    if await cmd.ensure_turn_in_quest(quest_id) is False:
        raise CustomError(f"quest {quest_id} could not be turned in")


async def _hunt_map_id(cmd: Command, quest_id: int, map_name: str,
                       monster_map_id: int, item_name: str) -> None:
    """``Core.HuntMonsterMapID``: kill that monster until the named item drops."""
    item_id = item_id_by_name(cmd, quest_id, item_name)
    if item_id is None:
        cmd.bot.log(f"[yokai] quest {quest_id} names no item {item_name!r}; "
                    f"monster {monster_map_id} is not hunted.")
        return
    await hunt_item_by_id(cmd, item_id, 1, map_name,
                          monster_map_id=monster_map_id, hunt=True)


async def shogun_war(cmd: Command) -> None:
    """``YokaiQuests.ShogunWar``: quests 6450-6461."""
    if await cmd.is_completed_before(6459):
        return

    cmd.bot.log("ShogunWar Quest line")

    async def q6450() -> None:
        await hunt_item(cmd, "Shadow Medallions", 5, SHOGUN_WAR,
                        monster_name="Shadow Samurai")

    await _quest(cmd, 6450, q6450)

    async def q6451() -> None:
        await _hunt_map_id(cmd, 6451, SHOGUN_WAR, 8, "Kijimuna Pollen")
        await _hunt_map_id(cmd, 6451, SHOGUN_WAR, 7, "Reishi Spores")

    await _quest(cmd, 6451, q6451)
    await map_item_quest(cmd, 6452, SHOGUN_WAR, 5956, 5)
    await kill_quest(cmd, 6453, SHOGUN_WAR, "Shadow Samurai")
    await kill_quest(cmd, 6454, SHOGUN_WAR, "Bamboo Treeant")
    await kill_quest(cmd, 6455, SHOGUN_WAR, "Shadow Samurai")
    await map_item_quest(cmd, 6456, SHOGUN_WAR, (5957, 5958, 5959, 5960))
    await kill_quest(cmd, 6457, SHOGUN_WAR, "Reishi")
    await kill_quest(cmd, 6458, SHOGUN_WAR, "Bamboo Treeant")

    async def q6459() -> None:
        await equip_class(cmd, solo=True)
        await _hunt_map_id(cmd, 6459, SHOGUN_WAR, 25, "Orochi Defeated")

    await _quest(cmd, 6459, q6459)
    await equip_class(cmd)
    await kill_quest(cmd, 6460, SHOGUN_WAR, "Shadow Samurai")

    async def q6461() -> None:
        await hunt_item(cmd, "Kijimuna Pollen", 3, SHOGUN_WAR,
                        monster_name="Kijimuna")
        await hunt_item(cmd, "Glowing Mushroom Cap", 3, SHOGUN_WAR,
                        monster_name="Reishi")
        await hunt_item(cmd, "Bamboo Leaf", 3, SHOGUN_WAR,
                        monster_name="Bamboo Treeant")

    await _quest(cmd, 6461, q6461)


async def shinrin_grove(cmd: Command) -> None:
    """``YokaiQuests.ShinrinGrove``: quests 6462-6473."""
    if await cmd.is_completed_before(6472):
        return

    cmd.bot.log("ShinrinGrove Quest line")
    await equip_class(cmd)

    async def q6462() -> None:
        await hunt_item(cmd, "Kame Defeated", 1, SHINRIN_GROVE,
                        monster_name="Kame")

    await _quest(cmd, 6462, q6462)

    async def q6463() -> None:
        await hunt_item(cmd, "Reishi Caps", 6, SHINRIN_GROVE,
                        monster_name="Reishi")
        await hunt_item(cmd, "Tsurubebi Flame", 3, SHINRIN_GROVE,
                        monster_name="Tsurubebi")

    await _quest(cmd, 6463, q6463)

    async def q6464() -> None:
        await equip_class(cmd, solo=True)
        await cmd.get_map_item(5962, 1)
        await cmd.sleep(500)
        await hunt_item(cmd, "Otoroshi Defeated", 1, SHINRIN_GROVE, cell="r4a",
                        pad="Left", monster_name="Otoroshi")

    await _quest(cmd, 6464, q6464)

    await equip_class(cmd)

    async def q6465() -> None:
        await cmd.get_map_item(5964, 5)
        await hunt_item(cmd, "Tsurubebi Extinguished", 5, GREEN_SHELL,
                        monster_name="Tsurubebi")

    await _quest(cmd, 6465, q6465)
    await kill_quest(cmd, 6466, GREEN_SHELL, "Tsukumogami")
    await kill_quest(cmd, 6467, SHINRIN_GROVE, "Kodama")
    await kill_quest(cmd, 6468, SHINRIN_GROVE, "Moglinberry Bush")

    async def q6469() -> None:
        await cmd.get_map_item(5965, 8)
        await hunt_item(cmd, "Luminous Spores", 6, SHINRIN_GROVE,
                        monster_name="Reishi")

    await _quest(cmd, 6469, q6469)

    async def q6470() -> None:
        await cmd.get_map_item(5966, 1)
        await hunt_item(cmd, "Merdraconians Slain", 3, GREEN_SHELL,
                        monster_name="Merdraconian")

    await _quest(cmd, 6470, q6470)
    await map_item_quest(cmd, 6471, GREEN_SHELL, 5967)

    async def q6472() -> None:
        await equip_class(cmd, solo=True)
        await hunt_item(cmd, "Nagami Defeated", 1, GREEN_SHELL,
                        monster_name="Nagami")

    await _quest(cmd, 6472, q6472)

    async def q6473() -> None:
        await equip_class(cmd)
        await hunt_item(cmd, "Moglinberry Bushels ", 8, SHINRIN_GROVE,
                        monster_name="Moglinberry Bush")
        await hunt_item(cmd, "Reishi Caps", 6, SHINRIN_GROVE,
                        monster_name="Reishi")

    await _quest(cmd, 6473, q6473)


async def shadowfortress(cmd: Command) -> None:
    """``YokaiQuests.Shadowfortress``: quests 6474-6494."""
    if await cmd.is_completed_before(6494):
        return

    cmd.bot.log("Shadowfortress Quest line")
    await equip_class(cmd)

    await kill_quest(cmd, 6474, HEIWA_VALLEY, "Abumi Guchi")

    async def q6475() -> None:
        await hunt_item(cmd, "Pilfered Armor", 5, HEIWA_VALLEY,
                        monster_name="Shadow Samurai")
        await hunt_item(cmd, "Stolen Sword", 5, HEIWA_VALLEY,
                        monster_name="Shadow Samurai")

    await _quest(cmd, 6475, q6475)

    async def q6476() -> None:
        await cmd.get_map_item(5968, 6)
        await hunt_item(cmd, "Kosenjobi Flame", 6, HEIWA_VALLEY,
                        monster_name="Kosenjobi")

    await _quest(cmd, 6476, q6476)
    await kill_quest(cmd, 6477, HEIWA_VALLEY, "Goryo")

    async def q6478() -> None:
        await hunt_item(cmd, "Spectral Heat", 5, HEIWA_VALLEY,
                        monster_name="Kosenjobi")
        await buy_quest(cmd, 6478, HEIWA_VALLEY, 1608, "Wasabi")

    await _quest(cmd, 6478, q6478)
    await kill_quest(cmd, 6479, HEIWA_VALLEY, "Abumi Guchi")
    await kill_quest(cmd, 6480, HEIWA_VALLEY, "Inugami")

    async def q6481() -> None:
        await hunt_item(cmd, "Spirit Eyes", 4, HEIWA_VALLEY,
                        monster_name="Inugami")
        await cmd.get_map_item(5970, 8)

    await _quest(cmd, 6481, q6481)

    await map_item_quest(cmd, 6482, HEIWA_VALLEY, 5971)
    await map_item_quest(cmd, 6482, HEIWA_VALLEY, 5972, 8)

    async def q6483() -> None:
        await _hunt_map_id(cmd, 6483, HEIWA_VALLEY, 15, "Onryo Slain")

    await _quest(cmd, 6483, q6483)
    await kill_quest(cmd, 6485, SHADOW_FORTRESS, "Restless Spirit")
    await kill_quest(cmd, 6486, SHADOW_FORTRESS, "Shadow Samurai")
    await map_item_quest(cmd, 6487, SHADOW_FORTRESS, 5973)

    async def q6488() -> None:
        await cmd.get_map_item(5974, 1)
        await hunt_item(cmd, "Shadow Essence", 7, SHADOW_FORTRESS,
                        monster_name="Living Shadow")

    await _quest(cmd, 6488, q6488)
    await kill_quest(cmd, 6489, SHADOW_FORTRESS, "Shadow Samurai")

    async def q6490() -> None:
        await cmd.get_map_item(5975, 7)
        await hunt_item(cmd, "Shadows Slain", 7, SHADOW_FORTRESS,
                        monster_name="Creeping Shadow")

    await _quest(cmd, 6490, q6490)
    await kill_quest(cmd, 6491, SHADOW_FORTRESS, "7th Head of Orochi")
    await map_item_quest(cmd, 6492, SHADOW_FORTRESS, (5976, 5979))

    async def q6493() -> None:
        await equip_class(cmd, solo=True)
        for head, item in (("6th Head of Orochi", "6th Head Defeated"),
                           ("5th Head of Orochi", "5th Head Defeated"),
                           ("4th Head of Orochi", "4th Head Defeated"),
                           ("3rd Head of Orochi", "3rd Head Defeated"),
                           ("2nd Head of Orochi", "2nd Head Defeated"),
                           ("1st Head of Orochi", "1st Head Defeated")):
            await hunt_item(cmd, item, 1, SHADOW_FORTRESS, monster_name=head)
        await cmd.get_map_item(5977, 1)

    await _quest(cmd, 6493, q6493)

    # ``Defeat Jaaku!`` accepts again after the hunt instead of turning in, so the
    # quest stays in progress -- reproduced, not repaired.
    if await quest_progression(cmd, 6494):
        return
    await equip_class(cmd, solo=True)
    if await cmd.ensure_accept_quest(6494) is False:
        raise CustomError("quest 6494 could not be accepted")
    await _hunt_map_id(cmd, 6494, SHADOW_FORTRESS, 31, "Jaaku Defeated")
    await cmd.ensure_accept_quest(6494)


async def do_quests(cmd: Command, no_pirate: bool = True) -> None:
    """``YokaiQuests.Quests``: the three regions in order.

    ``no_pirate`` is the reference's own parameter and is unused there too.
    """
    await shogun_war(cmd)
    await shinrin_grove(cmd)
    await shadowfortress(cmd)


async def main(cmd: Command):
    await do_quests(cmd)
