"""Slavery API: starting is additive, stop and pause act on one account.

    python tools/test_slavery_api.py

The global STOP is the only thing that ends every pane.  ``start_slaves`` used to
call ``stop_slaves()`` first, so starting a second account killed the first one;
these checks pin the per-account behaviour.  Threads are stubbed, so no socket is
opened and no account is touched.
"""
import json
import pathlib
import tempfile
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app import build_hub_app as hub  # noqa: E402

PASS = 0
FAIL = 0


def check(label, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok   {label}   [{got}]")
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, want {want!r}")


class StubBot:
    def __init__(self):
        self.is_paused = False
        self.is_script_paused = False
        self.is_client_connected = True


class StubThread:
    """A ``SlaveBotThread`` that never logs in."""

    made = []

    def __init__(self, *args, **kwargs):
        self.username = kwargs.get("username")
        self.bot_instance = StubBot()
        self.started = False
        self.alive = True
        StubThread.made.append(self)

    def start(self):
        self.started = True

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        return None


def make_api(tmpdir):
    api = hub.SlaveryApi()
    api.config_path = str(pathlib.Path(tmpdir) / "slavery_config.json")
    return api


CONFIG = {"slaves": [{"username": "alpha", "password": "x"},
                     {"username": "beta", "password": "y"},
                     {"username": "gamma", "password": "z"}]}


def main():
    print("=" * 74)
    print("slavery api: one account at a time, global stop still stops all")
    print("=" * 74)

    real_thread = hub.SlaveBotThread
    real_stop_panes = hub._stop_panes

    def stop_panes(threads, timeout_s=20.0, tag=""):
        for thread in threads.values():
            thread.alive = False
        return {}

    hub.SlaveBotThread = StubThread
    hub._stop_panes = stop_panes
    try:
        with tempfile.TemporaryDirectory() as tmp:
            api = make_api(tmp)

            # --- start is additive ------------------------------------
            check("start alpha", api.start_slaves(CONFIG, ["alpha"])["success"],
                  True)
            check("alpha is up", list(api.active_threads), ["alpha"])

            first_beta = None
            check("start beta on top of alpha",
                  api.start_slaves(CONFIG, ["beta"])["success"], True)
            check("both are up, alpha was not killed",
                  sorted(api.active_threads), ["alpha", "beta"])

            # --- starting a running account does not spawn a second one
            alpha_thread = api.active_threads["alpha"]
            api.start_slaves(CONFIG, ["alpha"])
            check("alpha keeps its thread", api.active_threads["alpha"] is
                  alpha_thread, True)
            check("and it is started only once", alpha_thread.started, True)
            first_beta = api.active_threads["beta"]
            api.start_slaves(CONFIG, ["beta"])
            check("beta is left alone too",
                  api.active_threads["beta"] is first_beta, True)

            # --- stop one ---------------------------------------------
            api.start_slaves(CONFIG, ["gamma"])
            check("gamma joined", sorted(api.active_threads),
                  ["alpha", "beta", "gamma"])
            check("stop gamma succeeds", api.stop_slave("gamma")["success"],
                  True)
            check("only gamma ended", sorted(api.active_threads),
                  ["alpha", "beta"])
            check("stopping an account that is not up is a no-op",
                  api.stop_slave("nobody")["success"], True)
            check("and it changes nothing", sorted(api.active_threads),
                  ["alpha", "beta"])

            # --- pause one --------------------------------------------
            check("pause beta", api.pause_slave("beta", True)["success"], True)
            beta_bot = api.active_threads["beta"].bot_instance
            alpha_bot = api.active_threads["alpha"].bot_instance
            check("beta is paused", (beta_bot.is_paused,
                                     beta_bot.is_script_paused), (True, True))
            check("alpha is untouched", alpha_bot.is_paused, False)
            check("resume beta", api.pause_slave("beta", False)["success"], True)
            check("beta is running again", beta_bot.is_paused, False)
            check("pausing an account that is not up fails",
                  api.pause_slave("nobody", True)["success"], False)

            # --- a pane that ended stops counting as running -----------
            api.active_threads["alpha"].alive = False
            statuses = api.get_status()
            check("a dead pane is pruned", "alpha" in api.active_threads, False)
            check("and it is not reported", "alpha" in statuses, False)
            check("the live one still is", "beta" in statuses, True)

            # --- the global stop still stops all ----------------------
            check("global stop", api.stop_slaves()["success"], True)
            check("nothing is left", api.active_threads, {})
    finally:
        hub.SlaveBotThread = real_thread
        hub._stop_panes = real_stop_panes
        StubThread.made.clear()

    print()
    print("=" * 74)
    print(f"passed {PASS}   failed {FAIL}")
    print("=" * 74)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
