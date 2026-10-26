"""Cryomancer -- the FrozenTower story, then the class daily.

Port of ``Dailies/Cryomancer.DoCrymancer``: ``Glac.DoAll(Cryomancer: true)``
(which is the FrozenTower line), then ``Daily.Cryomancer`` (the Glacera Ice
Token turn-ins, :func:`bot.core_dailies.cryomancer`), then the rank-up.
"""
from bot.core_advanced import rank_up_class as advance_class
from bot.core_dailies import cryomancer as daily_cryomancer
from bot.story.glacera import do_all as glacera_do_all
from core.command import Command

CRYOMANCER = "Cryomancer"


async def get_cryomancer(cmd: Command, rank_up_class: bool = True) -> None:
    """``Cryomancer.DoCrymancer``.

    Args:
        cmd (Command): Facade to act through.
        rank_up_class (bool): Carry the class to rank 10 afterwards.
    """
    if await cmd.has_item(CRYOMANCER):
        if rank_up_class:
            await advance_class(cmd, CRYOMANCER)
        return

    await glacera_do_all(cmd, cryomancer=True)
    await daily_cryomancer(cmd)

    if rank_up_class:
        await advance_class(cmd, CRYOMANCER)


async def main(cmd: Command):
    await get_cryomancer(cmd)
