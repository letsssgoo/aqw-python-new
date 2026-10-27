"""Every ported story in one run -- discovered, so new ones join by themselves.

A module under ``bot/story`` that exposes ``main(cmd)`` is a story entry point,
and this walks the package for exactly that instead of keeping a list to update.
``SKIP`` holds the non-story modules (their ``main`` is a helper for something
else) and this file.
"""
import importlib
import pathlib

import bot.story
from bot.script_log import ScriptLog
from core.command import Command

TAG = "All Stories"

#: Modules that expose ``main`` but are not a story to run here.
SKIP = {
    "bot.story.0_all_story",
}

#: The package directory, for the file walk below.  ``pkgutil`` is not used
#: because the sub-folders are namespace packages (no ``__init__.py``), which it
#: does not descend into -- and a namespace package has no ``__file__`` either,
#: so the first ``__path__`` entry is the directory.
STORY_ROOT = pathlib.Path(list(bot.story.__path__)[0])


def story_modules():
    """Module paths under ``bot.story`` that expose ``main``, in name order."""
    found = []
    for path in sorted(STORY_ROOT.rglob("*.py")):
        if path.name.startswith("_"):
            continue
        parts = path.relative_to(STORY_ROOT).with_suffix("").parts
        module_path = "bot.story." + ".".join(parts)
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
    modules = story_modules()
    for module_path in modules:
        name = module_path.rsplit(".", 1)[-1]
        log.info(f"--- {name} ---")
        module = importlib.import_module(module_path)
        try:
            await module.main(cmd)
        except Exception as error:  # noqa: BLE001
            log.error(f"{name} stopped: {type(error).__name__}: {error}")
            return
    log.success(f"{len(modules)} stories done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
