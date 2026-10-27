"""Hero -- port of ``Story/lordsofchaos/14Hero(ChaosFinale).cs``.

The logic is :func:`bot.story.lordsofchaos.core13loc.hero`.
"""
from bot.script_log import ScriptLog
from bot.story.lordsofchaos.core13loc import hero as run_segment
from core.command import Command

TAG = "13 Lords of Chaos: Hero"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running Hero...")
    await run_segment(cmd)
    log.success("Hero done.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
