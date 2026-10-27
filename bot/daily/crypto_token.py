"""Crypto token daily.

Logic lives in ``bot/core_dailies`` (``crypto_token``).  Run it on its own account with
``python -m bot.daily.crypto_token``, or through ``start.py``.
"""
from bot.core_dailies import crypto_token
from bot.script_log import ScriptLog
from core.command import Command

TAG = "Crypto token"


async def main(cmd: Command):
    log = ScriptLog(cmd, TAG)
    log.info("Running the crypto token daily...")
    await crypto_token(cmd)
    log.success("Daily finished.")


if __name__ == "__main__":
    from bot.standalone import run_standalone

    run_standalone(main)
