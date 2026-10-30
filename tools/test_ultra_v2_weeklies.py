"""Ultra V2 weeklies: Drakath and Nulgath.

    python tools/test_ultra_v2_weeklies.py
"""
from _ultra_v2_support import *  # noqa: F401,F403
import os      # noqa: E402
import shutil  # noqa: E402

from _ultra_v2_support import (check, finish, run, _StubBot,  # noqa: F401
                               _StubCommand)

# --- Ultra Drakath (weekly) ------------------------------------------------
# The fight is boss-only; what matters is the taunt ladder: StoneCrusher (slot
# 2) and ArchPaladin (slot 3) each take aggro once as the boss crosses fixed HP
# thresholds, in order, and Stable moves those numbers (``Adjusted*``).
from bot.ultra.v2.weeklies import drakath  # noqa: E402

check("drakath: quest 8300 in championdrakath",
      (drakath.SPEC.quest, drakath.SPEC.map), (8300, "championdrakath"))
check("drakath: pulled from r2/Left, boss id.1",
      (drakath.SPEC.boss_cell, drakath.SPEC.boss_pad, drakath.BOSS),
      ("r2", "Left", "id.1"))
check("drakath: level 80 gate", drakath.SPEC.min_level, 80)
check("drakath: registered for the menu", "drakath" in V2_ORDER, True)


def _drakath(slot, composition="Default"):
    return drakath.UltraDrakath(_StubCommand(), options.UltraOptions(
        players=("a", "b", "c", "d"), composition=composition), slot)


check("drakath: slots 2 and 3 taunt",
      [(_drakath(slot).is_taunter) for slot in (1, 2, 3, 4)],
      [False, True, True, False])
check("drakath: slot 1 and 4 never taunt",
      (_drakath(1).taunt_thresholds(), _drakath(4).taunt_thresholds()),
      ((), ()))
check("drakath: StoneCrusher ladder",
      _drakath(2).taunt_thresholds(),
      (16_500_000, 12_500_000, 6_200_000))
check("drakath: Stable's StoneCrusher ladder",
      _drakath(2, "Stable").taunt_thresholds(),
      (16_500_000, 12_500_000, 6_500_000))
check("drakath: ArchPaladin ladder",
      _drakath(3).taunt_thresholds(),
      (18_500_000, 14_500_000, 8_200_000, 4_200_000))
check("drakath: Stable's ArchPaladin ladder",
      _drakath(3, "Stable").taunt_thresholds(),
      (18_500_000, 14_500_000, 8_500_000, 4_500_000))
check("drakath: GenericPrebuff is 3, 2, 1 at 750 ms",
      (drakath.PREBUFF_SKILLS, drakath.PREBUFF_GAP_MS),
      ((3, 2, 1), 750))

# The ladder is walked once per attempt, in order, only when the HP is crossed.
class _Boss:
    def __init__(self, hp):
        self.current_hp = hp


class _BossCommand(_StubCommand):
    def __init__(self, hp):
        super().__init__()
        self.boss = _Boss(hp)

    def get_monster(self, target="*"):
        return self.boss

    def is_monster_alive(self, target="*"):
        return True


_ap = drakath.UltraDrakath(_BossCommand(19_000_000), options.UltraOptions(
    players=("a", "b", "c", "d")), 3)
check("drakath: nothing to taunt above the first threshold",
      _ap.due_taunt(), None)
_ap.cmd.boss.current_hp = 18_400_000
check("drakath: the first threshold fires", _ap.due_taunt(), 18_500_000)
check("drakath: and is not asked again", _ap.due_taunt(), None)
_ap.cmd.boss.current_hp = 14_000_000
check("drakath: the second threshold fires next", _ap.due_taunt(), 14_500_000)

# ``Fight`` starts its own ``tauntIndex`` at zero, so a wipeout and retry walks
# the ladder from the top again -- the boss comes back at full HP.
_retry = drakath.UltraDrakath(_BossCommand(18_000_000), options.UltraOptions(
    players=("a", "b", "c", "d")), 3)
_retry._taunt_index = 2
_retry.cmd.is_monster_alive = lambda target="*": False
run(_retry.fight(2))
check("drakath: a retry starts the taunt ladder over", _retry._taunt_index, 0)
# A pane that already died and respawned this attempt must publish its next
# death too, or the wipe detector never counts four panes down.
_wr_run = "test_v2_deaths"
_previous_wr = os.environ.get("AQW_RUN_ID")
os.environ["AQW_RUN_ID"] = _wr_run
try:
    from bot.ultra import party as _party  # noqa: E402
    _dead_cmd = _BossCommand(0)
    _dead_cmd.bot.player.ISDEAD = True
    _dead = drakath.UltraDrakath(_dead_cmd, options.UltraOptions(
        players=("a", "b", "c", "d")), 3)
    _dead.note_death()
    _party.clear_death(_dead.sync.name, 3)          # it respawned
    _dead.note_death()                              # and died again
    check("deaths: a second death is published again",
          _party.death_times(_dead.sync.name, (3,)).get(3) is not None, True)
    check("deaths: but the log line stays once per attempt",
          _dead._death_reported, True)
finally:
    shutil.rmtree(REPO_ROOT / "capture_logs" / "ultra" / _wr_run,
                  ignore_errors=True)
    if _previous_wr is None:
        os.environ.pop("AQW_RUN_ID", None)
    else:
        os.environ["AQW_RUN_ID"] = _previous_wr

# Capes: AP always Penitence, slot 1 by composition, Stable's KE on Lament.
check("drakath: ArchPaladin wears Penitence in every composition",
      [presets.preset_for("drakath", composition, 3).cape
       for composition in ("Default", "Stable", "Reliable")],
      ["Penitence"] * 3)
check("drakath: slot 1 capes per composition",
      [presets.preset_for("drakath", composition, 1).cape
       for composition in ("Default", "Stable", "Reliable")],
      ["Penitence", "Lament", "Penitence"])

# --- Ultra Nulgath (weekly) ------------------------------------------------
# Blade id.1 / Nulgath id.2; the taunt relay hangs off an ``Abyss!`` packet
# detector on slot 4, and the target table is per slot *and* composition.
from bot.ultra.v2.weeklies import nulgath  # noqa: E402
from bot.ultra.v2.packets import PacketDetector  # noqa: E402

check("nulgath: quest 8692 in ultranulgath",
      (nulgath.SPEC.quest, nulgath.SPEC.map), (8692, "ultranulgath"))
check("nulgath: pulled from Boss/Right, boss id.2",
      (nulgath.SPEC.boss_cell, nulgath.SPEC.boss_pad, nulgath.SPEC.monster_id),
      ("Boss", "Right", 2))
check("nulgath: level 80 gate", nulgath.SPEC.min_level, 80)
check("nulgath: registered for the menu", "nulgath" in V2_ORDER, True)


class _TwoBossCommand(_StubCommand):
    """Blade id.1 and Nulgath id.2, with the Blade's HP under our control."""

    def __init__(self, blade_hp=1_000_000, blade_alive=True):
        super().__init__()
        self.blade = _Boss(blade_hp)
        self.blade_alive = blade_alive

    def get_monster(self, target="*"):
        return self.blade

    def is_monster_alive(self, target="*"):
        return str(target) != "id.1" or self.blade_alive


def _nulgath(slot, composition="Default"):
    return nulgath.UltraNulgath(_TwoBossCommand(), options.UltraOptions(
        players=("a", "b", "c", "d"), composition=composition), slot)


check("nulgath: Default taunters are slots 1 and 4",
      [_nulgath(slot).is_taunter for slot in (1, 2, 3, 4)],
      [True, False, False, True])
check("nulgath: Stable/Reliable taunters are slots 3 and 4",
      [(_nulgath(slot, composition).is_taunter)
       for composition in ("Stable", "Reliable") for slot in (3, 4)],
      [True, True, True, True])
check("nulgath: slot 4 is the packet watcher",
      [_nulgath(slot).is_watcher for slot in (1, 2, 3, 4)],
      [False, False, False, True])

# GetTargetMapId, the part that differs per slot and composition.
check("nulgath: Default slot 2 chips the Blade while it is healthy",
      _nulgath(2).target_map_id(), "id.1")
_weak = nulgath.UltraNulgath(_TwoBossCommand(blade_hp=700_000),
                             options.UltraOptions(
                                 players=("a", "b", "c", "d")), 2)
check("nulgath: Default slot 2 leaves the Blade under 750k",
      _weak.target_map_id(), "id.2")
check("nulgath: Default's other slots hit Nulgath",
      [_nulgath(slot).target_map_id() for slot in (1, 3, 4)],
      ["id.2", "id.2", "id.2"])
check("nulgath: Stable slot 1 chips the Blade above 500k",
      _nulgath(1, "Stable").target_map_id(), "id.1")
_stable_weak = nulgath.UltraNulgath(_TwoBossCommand(blade_hp=400_000),
                                    options.UltraOptions(
                                        players=("a", "b", "c", "d"),
                                        composition="Stable"), 1)
check("nulgath: Stable slot 1 leaves it under 500k",
      _stable_weak.target_map_id(), "id.2")
check("nulgath: Stable slot 2 stays on the Blade while it lives",
      _nulgath(2, "Stable").target_map_id(), "id.1")
check("nulgath: Reliable slot 1 stays on the Blade while it lives",
      _nulgath(1, "Reliable").target_map_id(), "id.1")
_gone = nulgath.UltraNulgath(_TwoBossCommand(blade_alive=False),
                             options.UltraOptions(
                                 players=("a", "b", "c", "d"),
                                 composition="Reliable"), 1)
check("nulgath: a dead Blade sends the slot to Nulgath",
      _gone.target_map_id(), "id.2")

# The Abyss relay: slot 4 sees the packet, waits 2 s, taunts and signals; the
# taunter one answers each signal 5 s later.
from datetime import datetime, timedelta  # noqa: E402

try:
    from bot.ultra import party as _party  # noqa: E402

    _abyss_run = "test_v2_nulgath"
    _previous_abyss = os.environ.get("AQW_RUN_ID")
    os.environ["AQW_RUN_ID"] = _abyss_run

    watcher = _nulgath(4)

    async def _handler(msg):
        return None

    watcher.bot.handle_server_response = _handler
    opened = watcher.detector.start()
    watcher.detector.inspect(
        '{"b":{"o":{"cmd":"ct","sarsa":{"ty":"h","t":2,"c":"Abyss!"}}}}')
    check("nulgath: the detector counts an Abyss packet",
          (opened, watcher.detector.count), (True, 1))
    watcher.detector.stop()
    check("nulgath: and stops counting when disarmed",
          watcher.detector.seen(1), False)

    watcher.detector.start()
    watcher.start_taunt_cycle()
    now = datetime.now()
    watcher.detector.inspect(
        '{"b":{"o":{"cmd":"ct","sarsa":{"ty":"h","t":2,"c":"Abyss!"}}}}')
    watcher.player_four_step(1, now)
    check("nulgath: slot 4 schedules a taunt on the detection",
          watcher._taunt_scheduled, True)
    watcher.player_four_step(1, now + timedelta(milliseconds=2500))
    check("nulgath: and sends ABYSS_TAUNT_DONE_1_1 when it fires",
          watcher.sync.read("ABYSS_TAUNT_DONE_1_1").get(4), True)
    check("nulgath: the cycle advances", watcher._abyss_cycle, 2)

    taunter = _nulgath(3, "Stable")
    taunter.start_taunt_cycle()
    later = datetime.now() + timedelta(milliseconds=6000)
    taunter.taunter_one_step(7, later)
    check("nulgath: the taunter one opens with a taunt after 5 s",
          taunter.taunt_requested, True)
    taunter.taunt_requested = False
    taunter.taunter_one_step(7, later)
    check("nulgath: the next step waits for the slot 4 signal",
          taunter._taunt_scheduled, False)
    _party.publish(f"{taunter.sync.name}.ABYSS_TAUNT_DONE_7_1", 4, True)
    taunter.taunter_one_step(7, later)
    check("nulgath: a signal schedules the answer taunt",
          (taunter._taunt_scheduled, taunter._taunt_at > later), (True, True))
finally:
    shutil.rmtree(REPO_ROOT / "capture_logs" / "ultra" / _abyss_run,
                  ignore_errors=True)
    if _previous_abyss is None:
        os.environ.pop("AQW_RUN_ID", None)
    else:
        os.environ["AQW_RUN_ID"] = _previous_abyss

check("nulgath: GenericPrebuff is 3, 2, 1 at 750 ms",
      (nulgath.PREBUFF_SKILLS, nulgath.PREBUFF_GAP_MS), ((3, 2, 1), 750))

# --- Ultra Drago (weekly) --------------------------------------------------
# Dene id.1 / Drago id.2 / Algie id.3.  Default and Reliable run the guard pair
# on every pane (slots 1+4 Algie, 2+3 Dene, Focus taunts alternating between
# partners); Stable splits off a damage dealer and an immediate Algie taunter.
from bot.ultra.v2.weeklies import drago  # noqa: E402

check("drago: quest 8397 in ultradrago",
      (drago.SPEC.quest, drago.SPEC.map), (8397, "ultradrago"))
check("drago: pulled from Boss/Left, boss id.2",
      (drago.SPEC.boss_cell, drago.SPEC.boss_pad, drago.SPEC.monster_id),
      ("Boss", "Left", 2))
check("drago: level 80 gate", drago.SPEC.min_level, 80)
check("drago: registered for the menu", "drago" in V2_ORDER, True)


def _drago(slot, composition="Default"):
    return drago.UltraDrago(_StubCommand(), options.UltraOptions(
        players=("a", "b", "c", "d"), composition=composition), slot)


check("drago: guards are Algie on 1/4 and Dene on 2/3",
      [_drago(slot).guard_map_id() for slot in (1, 2, 3, 4)],
      ["id.3", "id.1", "id.1", "id.3"])
check("drago: the guard partners are 1<->4 and 2<->3",
      [_drago(slot).partner_slot() for slot in (1, 2, 3, 4)],
      [4, 3, 2, 1])
check("drago: slots 1 and 3 open the taunt cycle",
      [_drago(slot).is_opening_owner() for slot in (1, 2, 3, 4)],
      [True, False, True, False])
check("drago: the signal prefix follows the guard",
      [_drago(slot).signal_prefix() for slot in (1, 2)],
      ["ALGIE_TAUNT_", "DENIE_TAUNT_"])
check("drago: odd signals belong to the opening owner",
      (drago.UltraDrago.align_signal(2, True),
       drago.UltraDrago.align_signal(2, False)),
      (3, 2))
check("drago: Default arms every pane as a taunter",
      [_drago(slot).is_taunter for slot in (1, 2, 3, 4)],
      [True, True, True, True])
check("drago: Stable arms slots 2-4",
      [_drago(slot, "Stable").is_taunter for slot in (1, 2, 3, 4)],
      [False, True, True, True])
check("drago: the ArchPaladin opens Dene, the rest Algie",
      [_drago(slot).initial_target() for slot in (1, 2, 3, 4)],
      ["id.3", "id.3", "id.1", "id.3"])
check("drago: Stable slot 2 opens Dene",
      _drago(2, "Stable").initial_target(), "id.1")


class _GuardCommand(_StubCommand):
    def __init__(self, alive=("id.1", "id.3")):
        super().__init__()
        self.alive = set(alive)

    def is_monster_alive(self, target="*"):
        return str(target) in self.alive


def _drago_with(slot, alive, composition="Default"):
    return drago.UltraDrago(_GuardCommand(alive), options.UltraOptions(
        players=("a", "b", "c", "d"), composition=composition), slot)


# GetNormalTarget: Default sends only slot 3 to Dene; Stable sends 1 and 4 to
# Algie and 2/3 to Dene.
check("drago/default: everyone but slot 3 hits Algie",
      [_drago_with(slot, {"id.1", "id.3"}).normal_target()
       for slot in (1, 2, 3, 4)],
      ["id.3", "id.3", "id.1", "id.3"])
check("drago/stable: 1 and 4 hit Algie, 2 and 3 hit Dene",
      [_drago_with(slot, {"id.1", "id.3"}, "Stable").normal_target()
       for slot in (1, 2, 3, 4)],
      ["id.3", "id.1", "id.1", "id.3"])
check("drago: a dead guard sends the pane to the other one",
      _drago_with(1, {"id.1"}).normal_target(), "id.1")
check("drago: with both guards down it hits Drago",
      _drago_with(1, set()).normal_target(), "id.2")

# The pull is a timestamp: slot 1 stamps it two seconds ahead, the rest read it.
_drago_run = "test_v2_drago"
_previous_drago = os.environ.get("AQW_RUN_ID")
os.environ["AQW_RUN_ID"] = _drago_run
try:
    leader = _drago_with(1, {"id.1", "id.3"})
    stamp = leader.publish_entry_time(1)
    check("drago: slot 1 publishes a future entry timestamp",
          stamp > 0, True)
    follower = _drago_with(2, {"id.1", "id.3"})
    check("drago: the others read the same timestamp",
          run(follower.entry_time(1)), stamp)
    check("drago: and the pull waits for it",
          run(follower.wait_entry_time(stamp - 60)), True)
finally:
    shutil.rmtree(REPO_ROOT / "capture_logs" / "ultra" / _drago_run,
                  ignore_errors=True)
    if _previous_drago is None:
        os.environ.pop("AQW_RUN_ID", None)
    else:
        os.environ["AQW_RUN_ID"] = _previous_drago

# --- Ultra Dage (weekly) ---------------------------------------------------
# One boss (id.1) and three scroll duties: Enrage on the taunt pair, Decay
# answered from the ``ct`` packet, Mystify on slot 4 (not on Stable).  Slots 3
# and 4 also use the safe-window heal (skill 2 while no Noxious Decay aura).
from bot.ultra.v2.weeklies import dage  # noqa: E402

check("dage: quest 8547 in ultradage",
      (dage.SPEC.quest, dage.SPEC.map), (8547, "ultradage"))
check("dage: pulled from Boss/Right, boss id.1",
      (dage.SPEC.boss_cell, dage.SPEC.boss_pad, dage.SPEC.monster_id),
      ("Boss", "Right", 1))
check("dage: level 80 gate", dage.SPEC.min_level, 80)
check("dage: registered for the menu", "dage" in V2_ORDER, True)
check("dage: the Decay announcement is verbatim",
      dage.DECAY_MESSAGE,
      "I possess the full power of the Legion at my disposal.")


def _dage(slot, composition="Default"):
    return dage.UltraDage(_StubCommand(), options.UltraOptions(
        players=("a", "b", "c", "d"), composition=composition), slot)


check("dage/default: Enrage taunters are slots 1 and 3",
      [_dage(slot).is_taunter() for slot in (1, 2, 3, 4)],
      [True, False, True, False])
check("dage/stable: Enrage taunters are slots 3 and 4",
      [_dage(slot, "Stable").is_taunter() for slot in (1, 2, 3, 4)],
      [False, False, True, True])
check("dage: the opening owner is slot 1 (slot 3 on Stable)",
      ([_dage(slot).opening_owner() for slot in (1, 3)],
       [_dage(slot, "Stable").opening_owner() for slot in (1, 3)]),
      ([True, False], [False, True]))
check("dage: the taunt partners are 1<->3 and 3<->4",
      ([_dage(1).partner_slot(), _dage(3).partner_slot()],
       [_dage(3, "Stable").partner_slot(), _dage(4, "Stable").partner_slot()]),
      ([3, 1], [4, 3]))
check("dage: slot 2 holds Decay, slot 4 holds Mystify",
      ([_dage(2).is_decay_holder(), _dage(4).is_mystify_holder()],
       _dage(4, "Stable").is_mystify_holder()),
      ([True, True], False))
check("dage: only Stable's slot 1 is a damage dealer",
      ([_dage(1).is_damage_dealer()],
       _dage(1, "Stable").is_damage_dealer()), ([False], True))
check("dage: slots 3 and 4 are the safe healers",
      [_dage(slot).is_safe_healer() for slot in (1, 2, 3, 4)],
      [False, False, True, True])
check("dage: only Stable's slot 1 brings the full potion set",
      ([_dage(1).uses_full_potions()],
       _dage(1, "Stable").uses_full_potions()), ([False], True))


def _scroll_of(slot, composition="Default"):
    runner = _dage(slot, composition)
    runner.prepare_scrolls()
    return getattr(runner, "scroll", None)


check("dage: the scroll each pane stocks",
      [_scroll_of(slot) for slot in (1, 2, 3, 4)],
      [dage.ENRAGE, dage.DECAY_SCROLL, dage.ENRAGE, dage.MYSTIFY_SCROLL])
check("dage/stable: no Mystify holder, slot 4 taunts",
      _scroll_of(4, "Stable"), dage.ENRAGE)

# Decay cycles: slot 2 owns the odd ones, Default's slot 4 the even ones.
_decay_run = "test_v2_dage_decay"
_previous_decay = os.environ.get("AQW_RUN_ID")
os.environ["AQW_RUN_ID"] = _decay_run
try:
    holder = _dage(2)
    holder.detector.count = 3
    holder.detector.running = True
    holder.handle_decay_detections()
    check("dage: the Decay holder answers its cycles",
          (holder.next_decay_cycle, holder.taunt_requested), (4, True))
    even = _dage(4)
    even.detector.count = 2
    even.detector.running = True
    even.handle_decay_detections()
    check("dage: Default's slot 4 only answers even cycles",
          (even.next_decay_cycle, even.taunt_requested), (3, True))
finally:
    shutil.rmtree(REPO_ROOT / "capture_logs" / "ultra" / _decay_run,
                  ignore_errors=True)
    if _previous_decay is None:
        os.environ.pop("AQW_RUN_ID", None)
    else:
        os.environ["AQW_RUN_ID"] = _previous_decay

# The zone listener: the reference's RunToArea feed.  A ``ct`` packet carries
# ``args.zoneSet`` ("A"/"B"), and DrainZoneEvents **walks** to the spot that
# letter names -- it never jumps.
from bot.ultra.v2.packets import ZoneWatcher  # noqa: E402


class _ZoneBot:
    def __init__(self):
        async def handler(msg):
            return None

        self.handle_server_response = handler


class _WalkCommand(_StubCommand):
    def __init__(self):
        super().__init__()
        self.walks = []

    async def walk_to(self, x, y, speed=8):
        self.walks.append((x, y))

    def is_monster_alive(self, target="*"):
        return True


async def _zone_watch():
    watcher = ZoneWatcher(_ZoneBot())
    started = watcher.start()
    watcher.inspect('{"b":{"o":{"cmd":"event","args":{"zoneSet":"A"}}}}')
    watcher.inspect('{"b":{"o":{"cmd":"event","args":{"zoneSet":"B"}}}}')
    watcher.inspect('{"b":{"o":{"cmd":"event","args":{}}}}')
    drained = watcher.drain()
    watcher.stop()
    return started, drained, watcher.running


_zone_started, _zone_events, _zone_running = run(_zone_watch())
check("dage: the zone listener queues zoneSet letters",
      (_zone_started, _zone_events), (True, ["A", "B"]))
check("dage: and it stops cleanly", _zone_running, False)


async def _zone_walk():
    cmd = _WalkCommand()
    runner = dage.UltraDage(cmd, options.UltraOptions(
        players=("a", "b", "c", "d")), 1)

    async def _handler(msg):
        return None

    cmd.bot.handle_server_response = _handler
    runner.zones.start()
    runner.zones.inspect('{"b":{"o":{"cmd":"event","args":{"zoneSet":"A"}}}}')
    runner.zones.inspect('{"b":{"o":{"cmd":"event","args":{"zoneSet":"B"}}}}')
    runner.zones.inspect('{"b":{"o":{"cmd":"event","args":{"zoneSet":""}}}}')
    await runner.drain_zone_events(move=True)
    runner.zones.stop()
    return cmd.walks


check("dage: DrainZoneEvents walks A, B and the middle",
      run(_zone_walk()), [(122, 420), (856, 420), (500, 420)])
check("dage: each attempt starts with a fresh zone listener",
      _dage(1).zones.running, False)

# The safe-window heal: once per window, and never while Noxious Decay is up.
class _HealCommand(_StubCommand):
    def __init__(self, aura=None):
        super().__init__()
        self.heals = []
        self.bot.player.canUseSkill = lambda slot: True
        self.bot.player.getAura = lambda name: aura

    def is_monster_alive(self, target="*"):
        return True

    async def use_skill(self, slot, **kwargs):
        self.heals.append(slot)
        return True


_clean = dage.UltraDage(_HealCommand(), options.UltraOptions(
    players=("a", "b", "c", "d")), 3)
check("dage: the safe heal fires once", run(_clean.handle_safe_heal()), True)
check("dage: and not twice in the same window",
      run(_clean.handle_safe_heal()), False)
_debuffed = dage.UltraDage(_HealCommand(aura=object()), options.UltraOptions(
    players=("a", "b", "c", "d")), 3)
check("dage: no heal while Noxious Decay is up",
      run(_debuffed.handle_safe_heal()), False)

# Reliable's Verus DoomKnight keeps skill 2 out of its rotation under
# Unleashed Doom (the reference's blockedStrictSkill).
_vdk = _dage(1, "Reliable")
check("dage: the VDK blocks skill 2 under Unleashed Doom",
      (_vdk.blocked_skill, _vdk.blocked_aura), (2, "Unleashed Doom"))
check("dage: every pane wears Health Vamp and Vainglory",
      {(presets.preset_for("dage", composition, slot).weapon,
        presets.preset_for("dage", composition, slot).cape)
       for composition in ("Default", "Stable", "Reliable")
       for slot in (1, 2, 3, 4)},
      {("Health Vamp", "Vainglory")})

# --- Ultra Gramiel (weekly) ------------------------------------------------
# Phase 1 balances the Grace Crystals (20 start / 2 stop) and answers crystal
# charge packets with alternating taunts; phase 2 walks three nuke cycles with
# a healing hold at 75 / 45 / 15 percent Gramiel HP.  Optimized puts a Shaman on
# slot 1, which also queues skill 4 on Gramiel.
from bot.ultra.v2.weeklies import gramiel  # noqa: E402

check("gramiel: quest 10301 in ultragramiel",
      (gramiel.SPEC.quest, gramiel.SPEC.map), (10301, "ultragramiel"))
check("gramiel: pulled from r2/Down, boss id.1",
      (gramiel.SPEC.boss_cell, gramiel.SPEC.boss_pad, gramiel.SPEC.monster_id),
      ("r2", "Down", 1))
check("gramiel: level 80 gate", gramiel.SPEC.min_level, 80)
check("gramiel: registered for the menu", "gramiel" in V2_ORDER, True)


def _gramiel(slot, composition="Default"):
    return gramiel.UltraGramiel(_StubCommand(), options.UltraOptions(
        players=("a", "b", "c", "d"), composition=composition), slot)


check("gramiel: slots 1-2 hold crystal A, 3-4 crystal B",
      [_gramiel(slot).assigned_crystal() for slot in (1, 2, 3, 4)],
      ["id.2", "id.2", "id.3", "id.3"])
check("gramiel: slots 1 and 3 own the odd cycles",
      [_gramiel(slot).owns_cycle(1) for slot in (1, 2, 3, 4)],
      [True, False, True, False])
check("gramiel: the phase-2 taunt attacks are 1/3/5/7",
      [_gramiel(slot).phase_two_taunt_attack() for slot in (1, 2, 3, 4)],
      [1, 3, 5, 7])
check("gramiel: healing-hold thresholds are 75/45/15",
      [gramiel.UltraGramiel.healing_hold_threshold(cycle)
       for cycle in (1, 2, 3)],
      [75, 45, 15])
check("gramiel: slots 1-2 hold with skill 3, slots 3-4 with skill 2",
      ([_gramiel(slot).healing_hold_skills() for slot in (1, 2)],
       [_gramiel(slot).healing_hold_skills() for slot in (3, 4)]),
      ([(3,), (3,)], [(2,), (2,)]))
check("gramiel/default: only slot 4 balances",
      [_gramiel(slot).is_balancer() for slot in (1, 2, 3, 4)],
      [False, False, False, True])
check("gramiel/reliable: slots 2 and 4 balance",
      [_gramiel(slot, "Reliable").is_balancer() for slot in (1, 2, 3, 4)],
      [False, True, False, True])
check("gramiel: Reliable's VDK blocks skill 4 under Safeguard",
      (_gramiel(1, "Reliable").blocked_skill,
       _gramiel(1, "Reliable").blocked_skill_target_aura),
      (4, "Safeguard"))
check("gramiel: the Optimized Shaman is slot 1 only",
      ([_gramiel(1, "Optimized").is_shaman,
        _gramiel(2, "Optimized").is_shaman],
       _gramiel(1, "Optimized").preset.skills),
      ([True, False], (0, 1, 2)))


class _CrystalCommand(_StubCommand):
    def __init__(self, a_hp, b_hp):
        super().__init__()
        self.hp = {"id.2": a_hp, "id.3": b_hp}

    def is_monster_alive(self, target="*"):
        return self.hp.get(str(target), 1) > 0

    def get_monster(self, target="*"):
        value = self.hp.get(str(target), 0)
        return type("M", (), {"current_hp": value, "max_hp": 1000})()


def _balance(slot, a_hp, b_hp):
    runner = gramiel.UltraGramiel(_CrystalCommand(a_hp, b_hp),
                                  options.UltraOptions(
                                      players=("a", "b", "c", "d")), slot)
    run(runner.maintain_phase_one_target(a_hp, b_hp))
    return runner.target_priority, runner.crystal_balancing


check("gramiel: an even pair sends the balancer to its own crystal",
      _balance(4, 1000, 990)[0], ("id.3",))
check("gramiel: a 20+ gap starts balancing on the healthier crystal",
      (lambda r: (r[0], r[1]))(_balance(4, 1000, 700)), (("id.2",), True))
check("gramiel: balancing stops within 2",
      (lambda r: (r[0], r[1]))(_balance(4, 1000, 999)), (("id.3",), False))
check("gramiel: a dead crystal becomes everyone's target",
      _balance(4, 0, 700)[0], ("id.3",))

# The Shaman queues skill 4 once opening and once after Safeguard.
class _ShamanCommand(_StubCommand):
    def __init__(self):
        super().__init__()
        self.casts = []
        self.bot.player.canUseSkill = lambda slot: True

    def is_monster_alive(self, target="*"):
        return True

    async def use_skill(self, slot, **kwargs):
        self.casts.append(slot)
        return True


_shaman = gramiel.UltraGramiel(_ShamanCommand(), options.UltraOptions(
    players=("a", "b", "c", "d"), composition="Optimized"), 1)
_shaman.taunt_target_until = __import__("datetime").datetime.min
run(_shaman.maintain_shaman_skill_four(True))
check("gramiel: the Shaman queues its opening skill 4",
      (_shaman._shaman_opening, _shaman.cmd.casts), (True, [4]))
_shaman.safeguard_active = True
run(_shaman.maintain_shaman_skill_four(True))
check("gramiel: and a second one after Safeguard",
      (_shaman._shaman_safeguard, _shaman.cmd.casts), (True, [4, 4]))

finish('ultra v2 weekly tests')
