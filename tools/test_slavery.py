"""Slavery slave: every helper reaches the bot through its own ``cmd``.

    python tools/test_slavery.py

``main(cmd)`` owns the only ``bot`` name in the file, and it lives under
``if __name__ == "__main__"``.  The helpers nested in ``main`` used to call a
bare ``bot.log`` anyway, so the first thing they did -- announcing the walk to
the master -- raised ``NameError`` and the hub thread died right after
"Running registered quests...".  The checks here keep ``bot`` out of every
function body and drive ``main`` up to that first log line.
"""
import ast
import asyncio
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bot.slavery import bot_slave  # noqa: E402

MODULE_PATH = REPO_ROOT / "bot" / "slavery" / "bot_slave.py"


class _Bot:
    def __init__(self):
        self.username = "povy"
        self.logs = []
        self.sent = []
        self.checking_locked_zone = False
        self.last_skills = []
        self.taunt_error = False

    def log(self, message):
        self.logs.append(message)

    def write_message(self, message):
        self.sent.append(message)


class _Cmd:
    """One loop turn: the master is missing from the map, the bot walks to him."""

    def __init__(self):
        self.bot = _Bot()
        self.handler = None
        self.goto_calls = []
        self.connected_calls = 0

    async def equip_item(self, item):
        pass

    def get_farm_class(self):
        return "Lord of Order"

    async def sleep(self, ms):
        await asyncio.sleep(0)

    def subscribe(self, handler):
        self.handler = handler

    async def goto_player(self, name):
        self.goto_calls.append(name)

    def get_player_in_map(self, name):
        return None

    def is_player_alive(self):
        return True

    def is_still_connected(self):
        self.connected_calls += 1
        return self.connected_calls == 1


def bare_bot_lines():
    """Line numbers of ``bot`` read by a function body (outside ``__main__``)."""
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if (isinstance(child, ast.Name) and child.id == "bot"
                        and isinstance(child.ctx, ast.Load)):
                    hits.append(child.lineno)
    return sorted(set(hits))


def main():
    hits = bare_bot_lines()
    assert hits == [], f"bare 'bot' inside a function at {hits}"
    print("slave      : no function reads a bare 'bot' (the handle is cmd.bot)")

    cmd = _Cmd()
    asyncio.run(bot_slave.main(cmd))
    assert cmd.goto_calls == [""], cmd.goto_calls
    assert any("goto master" in line for line in cmd.bot.logs), cmd.bot.logs
    print("slave      : main() walks to the master instead of dying at the first log")

    event = json.dumps({"b": {"o": {"cmd": "event", "args": {"zoneSet": "A"}}}})
    cmd.handler(event)
    assert any("Event packet" in line for line in cmd.bot.logs), cmd.bot.logs
    print("slave      : an event packet is logged, not swallowed as a NameError")

    print("\nslavery tests OK")


if __name__ == "__main__":
    main()
