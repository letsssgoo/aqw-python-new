"""Every daily in one run -- discovered, so a new one joins by itself.

Each daily is its own module under ``bot/daily`` (``bot/daily/lord_of_order.py``
and friends); this walks the folder for them instead of keeping a list.  A daily
that is already done for the day returns immediately, so re-running this costs
nothing beyond the quest checks.
"""
import importlib
import pathlib

import bot.daily
from bot.script_log import ScriptLog
from core.command import Command

TAG = "All Dailies"

DAILY_ROOT = pathlib.Path(list(bot.daily.__path__)[0])
#: Modules that are not a single daily.
SKIP = {"bot.daily.0_all_daily"}


def daily_modules():
    """Module paths under ``bot.daily`` that expose ``main``, in name order."""
    found = []
    for path in sorted(DAILY_ROOT.glob("*.py")):
        if path.name.startswith("_"):
            continue
        module_path = f"bot.daily.{path.stem}"
        if module_path in SKIP:
            continue
        try:
            module = importlib.import_module(module_path)
        except Exception:  # noqa: BLE001 - a broken module is reported on use
            continue
        if callable(getattr(module, "main", None)):
            found.append(module_path)
    return found


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    modules = daily_modules()
    for module_path in modules:
        name = module_path.rsplit(".", 1)[-1]
        log.info(f"--- {name} ---")
        module = importlib.import_module(module_path)
        try:
            await module.main(cmd)
        except Exception as error:  # noqa: BLE001
            log.error(f"{name} stopped: {type(error).__name__}: {error}")
            return
    log.success(f"{len(modules)} dailies done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
