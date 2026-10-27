"""13 Lords of Chaos -- every ported chapter of 13 Lords of Chaos, in order.

Mirrors ``Story/lordsofchaos/00Complete13LOC.cs``.  Chapters the port has not reached
yet are named in ``NOT_PORTED`` instead of being skipped silently.
"""
import importlib

from bot.script_log import ScriptLog
from core.command import Command

TAG = "13 Lords of Chaos"

#: Chapter modules, in the source's order.
CHAPTERS = (
    "bot.story.lordsofchaos.01_prologue",
    "bot.story.lordsofchaos.02_escherion",
    "bot.story.lordsofchaos.03_vath",
    "bot.story.lordsofchaos.04_kitsune",
    "bot.story.lordsofchaos.05_wolfwing",
    "bot.story.lordsofchaos.06_kimberly",
    "bot.story.lordsofchaos.07_ledgermayne",
    "bot.story.lordsofchaos.08_tibicenas",
    "bot.story.lordsofchaos.09_khasaanda_horc",
    "bot.story.lordsofchaos.10_iadoa",
    "bot.story.lordsofchaos.11_lionfang",
    "bot.story.lordsofchaos.12_xiang",
    "bot.story.lordsofchaos.13_alteon",
    "bot.story.lordsofchaos.14_hero",
)

#: Source chapters with no port yet.
NOT_PORTED = (
    "09Khasaanda(Troll)",
    "15Extra",
)


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    for module_path in CHAPTERS:
        name = module_path.rsplit(".", 1)[-1]
        log.info(f"--- {name} ---")
        module = importlib.import_module(module_path)
        try:
            await module.main(cmd)
        except Exception as error:  # noqa: BLE001
            log.error(f"{name} stopped: {type(error).__name__}: {error}")
            return
    if NOT_PORTED:
        log.warning(f"not ported yet: {', '.join(NOT_PORTED)}")
    log.success(f"{len(CHAPTERS)} chapters done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
