"""Blaze Binder -- Pyromancer's own class points, then two sigils.

Port of ``Other/Classes/Daily-Classes/BlazeBinder.GetClass``: ``Dailies.Pyromancer``
first (that method is not a daily in the reference either -- its own comment says
so), one class point in /noobshire if Pyromancer has none, both sigils from
/fireforge, then the class itself and its rank-up.
"""
from bot.core_advanced import buy_item, gear_store
from bot.core_advanced import rank_up_class as advance_class
from bot.core_bots import kill_once
from bot.core_dailies import pyromancer
from core.command import Command

BLAZE_BINDER = "Blaze Binder"
PYROMANCER = "Pyromancer"

#: ``Adv.BuyItem("fireforge", 1142, ...)`` for both sigils, 1140 for the class.
SIGIL_SHOP = 1142
CLASS_SHOP = 1140
DARKNESS_SIGIL, FLAME_SIGIL = "Darkness Sigil", "Flame Sigil"

#: The reference's own "getting 1 point" run.
POINT_MAP = "Noobshire"


async def _kill_one(cmd: Command) -> None:
    """``Bot.Kill.Monster("*")``: attack the cell until nothing in it is alive."""
    for _ in range(POINT_ATTACK_TRIES):
        cell = str(getattr(cmd.bot.player, "CELL", "") or "").lower()
        alive = [mon for mon in cmd.bot.monsters
                 if str(mon.frame or "").lower() == cell and mon.is_alive
                 and mon.current_hp > 0]
        if not alive:
            return
        await cmd.use_next_skill(DEFAULT_SKILL_LIST, "*")
    cmd.bot.log(f"[blazebinder] nothing died in /{POINT_MAP}; carrying on.")


async def get_class(cmd: Command, rank_up_class: bool = True) -> None:
    """``BlazeBinder.GetClass``.

    Args:
        cmd (Command): Facade to act through.
        rank_up_class (bool): Carry the class to rank 10 afterwards.
    """
    if await cmd.has_item(BLAZE_BINDER):
        if rank_up_class:
            await advance_class(cmd, BLAZE_BINDER)
        return

    await pyromancer(cmd)

    pyromancer_item = cmd.bot.player.get_item_inventory(PYROMANCER)
    if pyromancer_item is None or int(pyromancer_item.qty) < 1:
        await gear_store(cmd)
        await cmd.equip_item(PYROMANCER)
        cmd.bot.log("Getting *1* point in Pyro for Blaze Binder")
        await cmd.join_map(POINT_MAP)
        await kill_once(cmd, POINT_MAP)
        await gear_store(cmd, restore=True, enh_after=True)

    await buy_item(cmd, SIGIL_SHOP, DARKNESS_SIGIL, map_name="fireforge")
    await buy_item(cmd, SIGIL_SHOP, FLAME_SIGIL, map_name="fireforge")
    await buy_item(cmd, CLASS_SHOP, BLAZE_BINDER, map_name="fireforge")
    await cmd.sleep(500)

    await advance_class(cmd, BLAZE_BINDER)


async def main(cmd: Command):
    await get_class(cmd)
