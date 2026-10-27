"""Every ported story, in one run.

The list lives here and is kept current: a new story module that exposes
``main(cmd)`` gets appended to ``STORIES``.  Order is alphabetical and each
story guards its own last quest, so re-running this only does what is missing.
"""
from bot.script_log import ScriptLog
from core.command import Command
import importlib

TAG = "All Stories"

#: Module paths, in the order they run.
STORIES = (
    "bot.story.age_of_ruin.core_aor",
    "bot.story.battle_under",
    "bot.story.glacera",
    "bot.story.lair",
    "bot.story.lordsofchaos.core13loc",
    "bot.story.mazumi",
    "bot.story.nation.citadel_ruins",
    "bot.story.nation.deleuze_tundra",
    "bot.story.nation.fiendshard",
    "bot.story.nation.oblivion_tundra",
    "bot.story.nation.originul",
    "bot.story.nation.shadow_blast_arena",
    "bot.story.nation.terces_archive",
    "bot.story.nation.terces_invasion",
    "bot.story.nation.tercessuinotlim",
    "bot.story.nation.void_chasm",
    "bot.story.nation.void_refuge",
    "bot.story.queen_of_monsters.celestial_arena",
    "bot.story.shadows_of_war.core_sow",
    "bot.story.throne_of_darkness.core_tod",
    "bot.story.tutorial",
    "bot.story.xans_lair",
    "bot.story.yokai",
)


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    for module_path in STORIES:
        name = module_path.rsplit(".", 1)[-1]
        log.info(f"--- {name} ---")
        module = importlib.import_module(module_path)
        try:
            await module.main(cmd)
        except Exception as error:  # noqa: BLE001
            log.error(f"{name} stopped: {type(error).__name__}: {error}")
            return
    log.success(f"{len(STORIES)} stories done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
