"""``CoreAwe`` -- the Blade of Awe relics.

Port of ``Good/GearOfAwe/CoreAwe.cs``; ``GetAweRelic`` is the only function the
Farmer Joe kit reaches, so it is the only one ported.

``intAQ`` (the Awe story counter) decides which pass the account needs, exactly
as the source's ``world.myAvatar.objData.intAQ`` does: with a pass already on the
account the relic quest is ``LegendQuest + 1`` at Blade rank 5 and level 35; a
fresh account buys the member or free pass for ``LegendQuest`` (member) or
``LegendQuest + 2`` (free) at rank 10 and level 55.

``Core.ToBank`` at the end of the cape script takes Awe passes out of the way;
the passes themselves are not consumed here.
"""
from bot.core_bots import buy_item, equip_class, wait_for_item
from bot.core_farms import blade_of_awe_rep, farm_experience
from core.command import Command
from templates.hunt import hunt_item
from bot.script_log import ScriptLog
TAG = "CoreAwe"

#: ``Core.BuyItem("tower", 53, 29403, shopItemID: 18569)`` -- the member pass.
PASS_SHOP = 53
PASS_MAP = "tower"
PASS_ITEM = 29403
PASS_SHOP_ITEM_ID = 18569

#: ``Core.BuyItem("museum", 1130, member ? 29402 : 29404, ...)`` -- the museum's
#: two passes; the free one is 29404 / entry 18579.
MUSEUM_PASS_SHOP = 1130
MUSEUM_PASS_MAP = "museum"
MEMBER_PASS_ITEM = 29402
MEMBER_PASS_SHOP_ITEM_ID = 18580
FREE_PASS_ITEM = 29404
FREE_PASS_SHOP_ITEM_ID = 18579

#: The relic itself is bought from the Awe shop once every fragment is in.
AWE_SHOP = 1129
AWE_SHOP_MAP = "museum"

#: ``Awe.GetAweRelic``'s two bands.
PASS_RANK, PASS_LEVEL = 5, 35
NO_PASS_RANK, NO_PASS_LEVEL = 10, 55


async def get_awe_relic(cmd: Command, item: str, legend_quest: int,
                        fragment_amount: int, shard_amount: int,
                        map_name: str, monster: str) -> None:
    """``CoreAwe.GetAweRelic``: one relic, from its pass to its purchase.

    Args:
        cmd (Command): Facade to act through.
        item (str): Relic's own name -- ``"Cape"`` for the Cape of Awe.
        legend_quest (int): The account's legendary relic quest id.
        fragment_amount (int): Fragments the quest asks for.
        shard_amount (int): Shards one kill has to drop.
        map_name (str): Where the shards come from.
        monster (str): The monster that drops them.
    """
    relic_name = f"{item} Relic"
    if await cmd.has_item(relic_name):
        return

    if (cmd.bot.player.intAQ or 0) > 0:
        await blade_of_awe_rep(cmd, PASS_RANK, False)
        await farm_experience(cmd, PASS_LEVEL)
        await buy_item(cmd, PASS_SHOP, PASS_ITEM, map_name=PASS_MAP,
                       shop_item_id=PASS_SHOP_ITEM_ID)
        quest_id = legend_quest + 1
    else:
        await blade_of_awe_rep(cmd, NO_PASS_RANK, False)
        await farm_experience(cmd, NO_PASS_LEVEL)
        member = cmd.get_player().is_member
        await buy_item(cmd, MUSEUM_PASS_SHOP,
                       MEMBER_PASS_ITEM if member else FREE_PASS_ITEM,
                       map_name=MUSEUM_PASS_MAP,
                       shop_item_id=(MEMBER_PASS_SHOP_ITEM_ID if member
                                     else FREE_PASS_SHOP_ITEM_ID))
        quest_id = legend_quest if member else legend_quest + 2

    await equip_class(cmd, solo=True)
    shard, fragment = f"{item} Shard", f"{item} Fragment"
    cmd.add_drop([shard, fragment])
    cmd.farming_logger(fragment, fragment_amount)

    guard = cmd.pass_guard(f"{fragment} x{fragment_amount} (quest {quest_id})")
    while (cmd.is_still_connected()
           and not await cmd.has_item(fragment, fragment_amount)):
        if await cmd.ensure_accept_quest(quest_id) is False:
            ScriptLog(cmd, TAG).warning(f"[awe] quest {quest_id} could not be accepted; "
                        f'"{fragment}" x{fragment_amount} is not farmable.')
            return

        lower = map_name.lower()
        if lower in ("doomvault", "doomvaultb"):
            # The source's own cell split: r26 in the B variant, r5 otherwise.
            await hunt_item(cmd, shard, shard_amount, map_name,
                            cell=("r26" if lower.endswith("b") else "r5"),
                            pad="Left", monster_name=monster, is_temp=False)
        else:
            await hunt_item(cmd, shard, shard_amount, map_name,
                            monster_name=monster, is_temp=False)

        if await cmd.ensure_turn_in_quest(quest_id) is False:
            return
        await wait_for_item(cmd, fragment)
        if not await guard.tick():
            break

    await buy_item(cmd, AWE_SHOP, relic_name, map_name=AWE_SHOP_MAP)


async def main(cmd: Command):
    await get_awe_relic(cmd, "Cape", 4178, 1, 1, "doomvault", "Binky")


if __name__ == "__main__":
    # Runs this script on its own account, the way
    # ``bot/enhancements/valiance.py`` does.
    from bot.standalone import run_standalone

    run_standalone(main)
