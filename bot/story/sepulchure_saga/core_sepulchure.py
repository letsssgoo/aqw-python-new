"""``CoreSepulchure`` -- the Sepulchure Saga, only Shadowfall Rise so far.

Port of ``Story/SepulchureSaga/CoreSepulchure.cs``.  The Smite forge enhancement
unlock needs ``ShadowfallRise()``, so that is the method ported; ``Alden()``,
``Lynaria()``, ``SepulchuresRise()`` and ``CompleteSS()`` wait for a caller.

``Story.PreLoad`` has no counterpart here; the guards do its work.
"""
from typing import Sequence, Tuple, Union

from bot.core_bots import equip_class
from bot.core_story import kill_quest, map_item_quest
from core.command import Command
from templates.hunt import hunt_item

SHADOWFALL_RISE_LAST = 6592
CORRUPTED_LUMA_QUEST = 6591

#: ``(quest, map, map item id or ids, how many, monster or monsters)``, in the
#: source's order.  An entry with both halves is one quest the source hands to
#: ``MapItemQuest`` first and then to ``KillQuest``.
SHADOWFALL_RISE_STEPS: Tuple[Tuple[int, str, Union[int, Sequence[int], None], int,
                                   Union[str, Sequence[str], None]], ...] = (
    (6539, "noxustower", None, 0, "Slimeskull"),
    (6540, "noxustower", None, 0, "Doomwood Treeant"),
    (6541, "noxustower", None, 0, "Sanguine Souleater"),
    (6542, "noxustower", None, 0, "Lightguard Caster"),
    (6543, "noxustower", None, 0, "Lightguard Caster"),
    (6544, "noxustower", 6018, 4, None),
    (6544, "noxustower", None, 0, "Lightguard Caster"),
    (6545, "noxustower", None, 0, "Lightguard Wolf"),
    (6546, "noxustower", None, 0, "Lightguard Paladin"),
    (6547, "noxustower", None, 0,
     ("Slimeskull", "Lightguard Caster", "Doomwood Treeant")),
    (6548, "noxustower", 6019, 1, None),
    (6549, "noxustower", 6020, 1, None),
    (6550, "noxustower", None, 0, "General Goldhammer"),
    (6560, "lightguardwar", None, 0, "Citadel Crusader"),
    (6561, "lightguardwar", None, 0, "Citadel Crusader"),
    (6562, "lightguardwar", None, 0, "Citadel Crusader"),
    (6563, "lightguardwar", None, 0, "Slimeskull"),
    (6564, "lightguardwar", None, 0, "Lightguard Engine"),
    (6565, "lightguardwar", None, 0, "Scorching Flame"),
    (6566, "lightguardwar", None, 0, "Citadel Crusader"),
    (6567, "lightguardwar", None, 0, "Sigrid Sunshield"),
    (6581, "lumafortress", 6098, 8, None),
    (6581, "lumafortress", None, 0, "Invasive Shadow"),
    (6582, "lumafortress", 6099, 7, None),
    (6582, "lumafortress", None, 0, "Light Treeant"),
    (6583, "lumafortress", None, 0, "Light Elemental"),
    (6584, "lumafortress", None, 0, "Hapless Skeleton"),
    (6585, "lumafortress", None, 0, "Light Treeant"),
    (6586, "lumafortress", 6100, 1, None),
    (6586, "lumafortress", None, 0, "Lightwing"),
    (6587, "lumafortress", 6101, 1, None),
    (6588, "lumafortress", None, 0, "Light Elemental"),
    (6589, "lumafortress", None, 0, "Living Shadow"),
    (6590, "lumafortress", None, 0, "Skeleton Minion"),
    (6592, "lumafortress", None, 0, "Light Elemental"),
)


async def shadowfall_rise(cmd: Command) -> None:
    """``CoreSepulchure.ShadowfallRise``: quests 6539-6592 across three maps.

    Quest 6591 is written out by hand because the source guards it with
    ``QuestProgression`` and fights ``Corrupted Luma`` in cell ``r4`` itself.
    """
    if await cmd.is_completed_before(SHADOWFALL_RISE_LAST):
        return

    await equip_class(cmd, solo=False)

    for quest_id, map_name, map_items, qty, monster in SHADOWFALL_RISE_STEPS:
        if map_items is not None:
            await map_item_quest(cmd, quest_id, map_name, map_items, qty)
        if monster is not None:
            await kill_quest(cmd, quest_id, map_name, monster)

    if not await cmd.is_completed_before(CORRUPTED_LUMA_QUEST):
        await cmd.ensure_accept_quest(CORRUPTED_LUMA_QUEST)
        await equip_class(cmd, solo=True)
        await hunt_item(cmd, "Luma Defeated", 1, "lumafortress", cell="r4",
                        pad="Left", monster_name="Corrupted Luma")
        await cmd.ensure_turn_in_quest(CORRUPTED_LUMA_QUEST)
