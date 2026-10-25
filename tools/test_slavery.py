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
import os
import pathlib
import shutil
import sys
import tempfile

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


def override_checks():
    """Every global setting can be pinned per account; empty means inherit."""
    from app.build_hub_app import (OVERRIDABLE_SETTINGS, SlaveBotThread,
                                   SlaveryApi, resolve_setting,
                                   slave_config_for)

    global_cfg = {
        "server": "Artix",
        "room_number": 9099,
        "follow_player": "GLOBAL",
        "copy_walk": True,
        "auto_zone": "none",
        "targets_priority": "Global Target",
        "whitelist": ["Treasure Chest"],
        "locked_zones": ["doomvault"],
    }

    # an override wins, an emptied field falls back to the global value
    own = {"overrides": {"follow_player": "OWN", "copy_walk": False,
                         "room_number": 1234, "whitelist": []}}
    assert resolve_setting(own, global_cfg, "follow_player") == "OWN"
    assert resolve_setting(own, global_cfg, "room_number") == 1234
    assert resolve_setting(own, global_cfg, "copy_walk") is False   # off is a choice
    assert resolve_setting(own, global_cfg, "whitelist") == ["Treasure Chest"]
    assert resolve_setting(own, global_cfg, "auto_zone") == "none"
    assert resolve_setting({"overrides": {"follow_player": ""}}, global_cfg,
                           "follow_player") == "GLOBAL"
    assert resolve_setting({"overrides": {"room_number": None}}, global_cfg,
                           "room_number") == 9099
    assert resolve_setting(None, global_cfg, "server") == "Artix"
    print("override   : an account's own value wins, an empty one inherits")

    effective = slave_config_for(own, global_cfg)
    assert effective["follow_player"] == "OWN"
    assert effective["copy_walk"] is False
    assert effective["server"] == "Artix"
    assert effective["targets_priority"] == "Global Target"
    assert global_cfg["follow_player"] == "GLOBAL"      # the globals are untouched
    assert set(effective) >= set(OVERRIDABLE_SETTINGS)
    print("override   : the thread config is the globals with the account's on top")

    thread = SlaveBotThread(username="a", password="b", char_class="c",
                            config=slave_config_for(own, global_cfg),
                            callback=None)
    assert thread.config["follow_player"] == "OWN"
    assert thread.config["room_number"] == 1234
    print("override   : the slave thread carries the resolved settings")

    temp_dir = tempfile.mkdtemp(prefix="slavery_test_")
    try:
        api = SlaveryApi()
        api.config_path = os.path.join(temp_dir, "slavery_config.json")

        class _Bot:
            pass

        class _Thread:
            def __init__(self):
                self.bot_instance = _Bot()

        api.active_threads = {"own": _Thread(), "global": _Thread()}
        saved = api.save_config({
            "room_number": 9099,
            "follow_player": "NEWGLOBAL",
            "whitelist": ["Void Aura"],
            "copy_walk": True,
            "slaves": [
                {"username": "own", "taunter": True,
                 "overrides": {"follow_player": "OWN", "room_number": 1234,
                               "copy_walk": False, "whitelist": ["Keep Me"]}},
                {"username": "global", "overrides": {}},
            ],
        })
        assert saved["success"], saved
        mine = api.active_threads["own"].bot_instance
        theirs = api.active_threads["global"].bot_instance
        # saving the globals must not flatten an account's own settings
        assert mine.follow_player == "OWN", mine.follow_player
        assert mine.default_room_number == 1234, mine.default_room_number
        assert mine.copy_walk is False, mine.copy_walk
        assert mine.itemsDropWhiteList == ["Keep Me"], mine.itemsDropWhiteList
        assert mine.taunter is True
        # and an account without overrides moves with the globals
        assert theirs.follow_player == "NEWGLOBAL", theirs.follow_player
        assert theirs.default_room_number == 9099, theirs.default_room_number
        assert theirs.itemsDropWhiteList == ["Void Aura"], theirs.itemsDropWhiteList

        # the master used to be a field of its own: an old config is migrated
        with open(api.config_path, "w") as f:
            json.dump({"server": "Twilly",
                       "slaves": [{"username": "old", "follow_player": "OWN"}]}, f)
        migrated = api.load_config()
        old = migrated["slaves"][0]
        assert "follow_player" not in old, old
        assert old["overrides"]["follow_player"] == "OWN", old
        assert migrated["server"] == "Twilly"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    print("override   : saving the globals leaves every account's own settings alone")


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

    override_checks()

    print("\nslavery tests OK")


if __name__ == "__main__":
    main()
