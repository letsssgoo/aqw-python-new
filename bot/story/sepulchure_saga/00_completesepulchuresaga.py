"""Sepulchure Saga -- every ported chapter of Sepulchure Saga, in order.

Mirrors ``Story/sepulchure_saga/00CompleteSepulchureSaga.cs``.  Chapters the port has not reached
yet are named in ``NOT_PORTED`` instead of being skipped silently.
"""
import importlib

from bot.script_log import ScriptLog
from core.command import Command

TAG = "Sepulchure Saga"

#: Chapter modules, in the source's order.
CHAPTERS = (
    "bot.story.sepulchure_saga.04_shadowfall_rise",
)

#: Source chapters with no port yet.
NOT_PORTED = (
    "01Alden",
    "02Lynaria",
    "03SepulchuresRise",
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
