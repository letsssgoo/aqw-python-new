"""``Lair`` -- the three /lair story lines.

Port of ``Story/Lair.cs``: Galanoth's line is what the Dragonslayer class needs
(quests 165-168); Duncan (1492-1495) and Ferzana (1502-1507) are members-only and
are kept exactly as the source has them, including its ``isCompletedBefore(169)``
guard even though 169 itself is no longer done there.
"""
from bot.core_bots import chain_complete
from bot.core_story import kill_quest, map_item_quest
from core.command import Command

LAIR = "lair"


def _is_member(cmd: Command) -> bool:
    return bool(getattr(cmd.bot.player, "is_member", False))


async def galanoth(cmd: Command) -> None:
    """``Lair.Galanoth``: Dragonslayer Veteran/Sergeant/Captain/Marshal 165-168."""
    if await cmd.is_completed_before(169):
        return
    await kill_quest(cmd, 165, LAIR, "Wyvern")
    await kill_quest(cmd, 166, LAIR, "Bronze Draconian")
    await kill_quest(cmd, 167, LAIR, "Dark Draconian")
    await kill_quest(cmd, 168, LAIR, "Red Dragon")


async def duncan(cmd: Command) -> None:
    """``Lair.Duncan``: quests 1492-1495, members only."""
    if not _is_member(cmd):
        cmd.bot.log("You must be a Member to complete the quests.")
        return
    if await cmd.is_completed_before(1495):
        return
    await kill_quest(cmd, 1492, LAIR, "Bronze Draconian")
    await map_item_quest(cmd, 1493, LAIR, 755, 10)
    await kill_quest(cmd, 1494, LAIR, "Red Dragon")
    await map_item_quest(cmd, 1495, LAIR, 753)


async def ferzana(cmd: Command) -> None:
    """``Lair.Ferzana``: quests 1502-1507, members only."""
    if not _is_member(cmd):
        cmd.bot.log("You must be a Member to complete the quests.")
        return
    if await cmd.is_completed_before(1507):
        return
    await chain_complete(cmd, 1502)
    await map_item_quest(cmd, 1503, LAIR, 754, 12)
    await kill_quest(cmd, 1504, LAIR, "Wyvern")
    await kill_quest(cmd, 1505, LAIR, "Bronze Draconian")
    await kill_quest(cmd, 1506, LAIR, "Dark Draconian")
    await kill_quest(cmd, 1507, LAIR, "Onyx Lava Dragon")


async def do_all(cmd: Command) -> None:
    """``Lair.DoAll``: Galanoth, then Duncan, then Ferzana."""
    await galanoth(cmd)
    await duncan(cmd)
    await ferzana(cmd)


async def main(cmd: Command):
    await do_all(cmd)
