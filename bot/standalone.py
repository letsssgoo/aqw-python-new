"""The ``if __name__ == "__main__"`` block the standalone scripts share.

``bot/enhancements/valiance.py`` runs itself: it asks for the account, builds a
``Bot`` with the drops it cares about and hands ``main`` to ``start_bot``.  Every
ported script can do the same with two lines, so the boilerplate lives here
instead of being copied into each file::

    if __name__ == "__main__":
        from bot.standalone import run_standalone
        run_standalone(main)

``start.py`` / ``gui.py`` keep loading these modules by ``BOT_PATH`` and calling
``main(cmd)``; this only adds the "run me directly" entry.
"""
import asyncio

from core.bot import Bot

DEFAULT_SERVER = "Artix"


def run_standalone(main, server: str = DEFAULT_SERVER) -> None:
    """Prompt for an account and run ``main`` against it, like valiance.py.

    Args:
        main (Callable): The module's ``async def main(cmd)``.
        server (str): Default server name; the prompt still accepts another.
    """
    username = input("Username: ")
    password = input("Password: ")
    entered = input(f"Server [{server}]: ").strip()

    bot = Bot(
        roomNumber=1,
        showLog=True,
        showDebug=False,
        showChat=True,
        isScriptable=True,
        autoRelogin=True,
        muteSpamWarning=True,
    )
    bot.set_login_info(username, password, entered or server)
    asyncio.run(bot.start_bot(main))
