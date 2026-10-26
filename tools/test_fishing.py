"""FishingREP: cast -> castWait -> getFish -> CatchResult.

    python tools/test_fishing.py

Paketnya dari capture nyata (``core/new_things.txt``, fishing): yang penting di
sini adalah timer cast **tidak tetap** (2800-7000 ms), jadi port harus memakai
nilai ``wait`` dari balasan ``castWait``, bukan angka 3500 milik sumber.

Drive loop-nya dengan cmd tiruan: satu cast = satu rank naik, jadi rank 9 -> 10
selesai dalam satu putaran.
"""
import asyncio
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from bot import core_farms                               # noqa: E402
from bot.core_farms import fishing_rep                       # noqa: E402

PASS = 0
FAIL = 0


def check(label: str, got, want) -> None:
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ok   {label}   [{got}]")
    else:
        FAIL += 1
        print(f"  FAIL {label}: got {got!r}, want {want!r}")


class StubBot:
    """A client that answers the fishing packets the way the server does."""

    def __init__(self, wait_ms: int):
        self.sent = []
        self.slept = []
        self.logs = []
        self.fishing_cast_wait = False
        self.fishing_caught = False
        self.fishing_wait_ms = 0
        self.fishing_derp = False
        self.fishing_catch_result = {}
        self._wait_ms = wait_ms

    def log(self, *args):
        self.logs.append(" ".join(map(str, args)))

    def write_message(self, msg):
        self.sent.append(msg)
        if "FishCast" in msg:
            self.fishing_cast_wait = True
            self.fishing_wait_ms = self._wait_ms
        if "getFish" in msg:
            self.fishing_caught = True
            self.fishing_catch_result = {"act": "CatchDynamite", "tool": "Dynamite"}


class Stub:
    #: The dynamite a real client would name in its cast packet.
    DYNAMITE_HELD = 23

    def __init__(self, bot):
        self.bot = bot
        self.rank = 9
        self.calls = []

    # --- what fishing_rep touches -------------------------------------
    def get_faction_rank(self, faction):
        return self.rank

    def get_quant_item(self, name):
        return self.DYNAMITE_HELD if name == "Fishing Dynamite" else 0

    def get_faction_rep(self, faction):
        return 0

    async def has_item(self, name, qty=1, **kw):
        self.calls.append(("has_item", name))
        # bait and dynamite already in hand, so the bait step is a no-op and
        # this test stays about the cast/pull exchange.
        return name in ("Fishing Bait", "Fishing Dynamite")

    async def register_quest(self, quest_id):
        self.calls.append(("register_quest", quest_id))

    def cancel_registered_quests(self):
        self.calls.append(("cancel_registered_quests",))

    async def ensure_accept_quest(self, quest_id, **kw):
        self.calls.append(("ensure_accept_quest", quest_id))
        return True

    async def ensure_turn_in_quest(self, quest_id, **kw):
        self.calls.append(("ensure_turn_in_quest", quest_id))
        return True

    async def equip_item(self, name):
        self.calls.append(("equip_item", name))

    def get_equipped_class(self):
        return None

    def get_farm_class(self):
        return ""          # nothing configured: equip_class reports and moves on

    def get_solo_class(self):
        return ""

    def is_not_in_map(self, name):
        return False

    def is_still_connected(self):
        return True

    async def join_map(self, *a, **kw):
        self.calls.append(("join_map", a[0] if a else None))

    async def send_packet(self, packet):
        self.calls.append(("send_packet", packet))
        self.bot.write_message(packet)

    async def sleep(self, ms):
        self.bot.slept.append(ms)
        await asyncio.sleep(0)

    async def hunt_item(self, *a, **kw):
        self.calls.append(("hunt_item", a[0] if a else None))


def main() -> int:
    print("=" * 74)
    print("fishing: the cast timer comes from the server, not from a constant")
    print("=" * 74)

    for wait_ms in (4200, 7000, 2800):
        bot = StubBot(wait_ms)
        cmd = Stub(bot)

        # one cast is enough: the rank is bumped by the stub's has_item/getFish
        original_send = cmd.send_packet

        async def send_packet(packet, _b=bot, _c=cmd):
            await original_send(packet)
            if "getFish" in packet:
                _c.rank += 1

        cmd.send_packet = send_packet
        asyncio.run(fishing_rep(cmd, 10))

        casts = [p for _, p in cmd.calls if _ == "send_packet"]
        check(f"wait={wait_ms}: cast names the held dynamite, not a hard 30",
              any("FishCast%1%Dynamite%23%" in p for p in casts), True)
        check(f"wait={wait_ms}: pull sent",
              any("getFish%1%false%" in p for p in casts), True)
        check(f"wait={wait_ms}: slept the packet's timer", wait_ms in bot.slept, True)
        check(f"wait={wait_ms}: not the 3500 starter value",
              3500 in bot.slept, False)
        check(f"wait={wait_ms}: bait/dynamite checked first",
              ("has_item", "Fishing Dynamite") in cmd.calls, True)
        check(f"wait={wait_ms}: a catch is reported the source's way",
              "Dynamite cast completed [x1]" in bot.logs, True)
        check(f"wait={wait_ms}: no invented rank verdict per cast",
              [line for line in bot.logs
               if line in ("Successful cast", "Failed cast")], [])

    print()
    print("=" * 74)
    print("fishing: the cast counter's progress line")
    print("=" * 74)

    bot = StubBot(3000)
    cmd = Stub(bot)
    original_send = cmd.send_packet

    async def send_packet(packet, _b=bot, _c=cmd):
        await original_send(packet)
        if "getFish" in packet:
            _c.rank += 1

    cmd.send_packet = send_packet
    saved = core_farms.FISHING_PROGRESS_EVERY
    core_farms.FISHING_PROGRESS_EVERY = 1
    try:
        asyncio.run(fishing_rep(cmd, 10))
    finally:
        core_farms.FISHING_PROGRESS_EVERY = saved
    check("progress line names the cast count and the readable rank",
          any(line.startswith("[fish] 1 casts, rank ") for line in bot.logs),
          True)

    print()
    print("=" * 74)
    print(f"passed {PASS}   failed {FAIL}")
    print("=" * 74)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
