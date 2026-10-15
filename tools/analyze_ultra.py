"""Team report from a `bot/ultra` telemetry run.

Reads ``capture_logs/ultra/<run_id>/slot*.jsonl`` (written by
``bot/ultra/telemetry.py``) and prints, per boss, what each slot actually did:
damage dealt and its share, damage taken, heals, deaths, and where the damage
landed.

Usage:
    python tools/analyze_ultra.py                 # latest run
    python tools/analyze_ultra.py 20261009_120000 # a specific run id
"""

from __future__ import annotations

import glob
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO_ROOT / "capture_logs" / "ultra"

#: Per-hit damage cap ("Boss Shield") by boss name; see bot/ultra/reference/MONSTERS.md.
BOSS_SHIELD = {"speaker": 150_000}


def latest_run() -> str:
    runs = [p for p in RUNS_DIR.iterdir() if p.is_dir()] if RUNS_DIR.is_dir() else []
    if not runs:
        raise SystemExit(f"no runs under {RUNS_DIR}")
    return max(runs, key=lambda p: p.stat().st_mtime).name


def load_records(path: Path) -> list[dict]:
    out = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def slot_data(records: list[dict]) -> dict:
    """Group one account's records by boss, accumulating the fight totals."""
    boss = "?"
    bosses: dict[str, dict] = {}
    monsters: dict[str, str] = {}

    def bucket() -> dict:
        return bosses.setdefault(
            boss, {"start": None, "end": None, "last": None, "dmg": 0, "hits": 0,
                   "taken": 0, "heals": 0, "heal_amt": 0, "deaths": 0, "big": 0,
                   "by_monster": defaultdict(int), "skills": defaultdict(int),
                   "equipped": [], "stats": {}, "auras": defaultdict(int),
                   "anims": defaultdict(int), "boss_auras": defaultdict(int),
                   "zone_seq": [], "zone_lost": 0, "zone_apply": 0, "events": []}
        )

    for r in records:
        kind = r.get("kind")
        t = r.get("t")
        if kind == "boss_start":
            boss = r.get("boss", "?")
            data = bucket()
            data["start"] = t
        elif kind == "boss_end":
            bucket()["end"] = t
        elif kind == "map":
            pass
        elif kind == "monsters":
            for mon in r.get("monsters", []):
                if mon.get("name"):
                    monsters[str(mon.get("id"))] = mon["name"]
        elif kind == "monster":
            if r.get("name"):
                monsters[str(r.get("id"))] = r["name"]
        elif kind == "equipped":
            bucket()["equipped"] = r.get("worn") or []
        elif kind == "stats":
            bucket()["stats"] = r.get("values") or {}
        elif kind == "auras":
            data = bucket()
            names = []
            for aura in r.get("auras", []):
                data["auras"][aura.get("name")] += 1
                names.append(aura.get("name"))
            data["events"].append((t, "auras", names))
        elif kind == "anims":
            data = bucket()
            for message in r.get("msgs", []):
                data["anims"][message] += 1
            data["events"].append((t, "anims", r.get("msgs")))
        elif kind == "pos":
            bucket()["events"].append((t, "pos", r.get("x")))
        elif kind == "monster_aura" and r.get("op") == "+":
            if r.get("name"):
                bucket()["boss_auras"][str(r["name"]).lower()] += 1
        elif kind == "zone":
            bucket()["zone_seq"].append(
                (t, r.get("step"), r.get("msg"), r.get("taunt"),
                 r.get("zone"), r.get("what")))
        elif kind == "zone_lost":
            bucket()["zone_lost"] += 1
        elif kind == "zone_apply":
            bucket()["zone_apply"] += 1
        elif kind == "damage":
            data = bucket()
            amount = abs(r.get("amount") or 0)
            data["dmg"] += amount
            data["hits"] += 1
            if amount >= 150_000:
                data["big"] += 1
            target = str(r.get("target"))
            data["by_monster"][monsters.get(target, target)] += amount
            data["skills"][str(r.get("act"))] += 1
        elif kind == "hurt":
            bucket()["taken"] += abs(r.get("amount") or 0)
        elif kind == "heal":
            data = bucket()
            data["heals"] += 1
            data["heal_amt"] += abs(r.get("amount") or 0)
        elif kind == "death":
            data = bucket()
            data["deaths"] += 1
            data["events"].append((t, "death", None))

        # A stopped/interrupted run never reaches boss_end; fall back to the last
        # record so a window and DPS can still be reported.
        if boss != "?":
            bucket()["last"] = t

    return {"bosses": bosses, "monsters": monsters}


def fmt(n: int) -> str:
    return f"{n:,}"


def report(run_id: str) -> None:
    directory = RUNS_DIR / run_id
    files = sorted(glob.glob(str(directory / "slot*.jsonl")))
    if not files:
        raise SystemExit(f"no slot*.jsonl in {directory}")

    slots = {}
    for path in files:
        records = load_records(Path(path))
        if not records:
            continue
        slot = records[0].get("slot")
        account = records[0].get("account")
        slots[slot] = {"account": account, "data": slot_data(records)}

    bosses = sorted({b for s in slots.values() for b in s["data"]["bosses"]})
    print(f"run {run_id}  ({len(slots)} slots: "
          + ", ".join(f"{k}={v['account']}" for k, v in sorted(slots.items())) + ")")

    for boss in bosses:
        rows = []
        team_dmg = team_taken = team_deaths = 0
        start = end = None
        for slot, info in sorted(slots.items()):
            data = info["data"]["bosses"].get(boss)
            if not data:
                continue
            dmg = data["dmg"]
            team_dmg += dmg
            team_taken += data["taken"]
            team_deaths += data["deaths"]
            if data["start"] is not None:
                start = data["start"] if start is None else min(start, data["start"])
            boss_end = data["end"] or data["last"]
            if boss_end is not None:
                end = boss_end if end is None else max(end, boss_end)
            rows.append((slot, info["account"], data))

        if not rows:
            continue
        span = f"{end - start:.0f}s" if start and end else "n/a"
        print(f"\n== {boss}  window={span}  team_dmg={fmt(team_dmg)}  "
              f"taken={fmt(team_taken)}  deaths={team_deaths}")
        for slot, account, data in rows:
            share = (data["dmg"] / team_dmg * 100) if team_dmg else 0
            top = sorted(data["by_monster"].items(), key=lambda kv: -kv[1])[:3]
            targets = " ".join(f"{name}:{fmt(v)}" for name, v in top)
            boss_end = data["end"] or data["last"]
            dur = (boss_end - data["start"]) if data["start"] and boss_end else 0
            dps = (data["dmg"] / dur) if dur else 0
            print(f"  slot{slot} {account:<10} dmg={fmt(data['dmg']):>10} "
                  f"({share:4.1f}%)  dps={dps:>8,.0f}  hits={data['hits']:>5}  "
                  f"taken={fmt(data['taken']):>9}  heals={data['heals']:>4}  "
                  f"deaths={data['deaths']}  {dur:.0f}s")
            if targets:
                print(f"          targets: {targets}")
            worn = data.get("equipped") or []
            if worn:
                gear = " ".join(
                    f"{g.get('slot')}={g.get('name')}"
                    + (f"[{g.get('enh')}]" if g.get("enh") else "")
                    for g in worn
                )
                print(f"          gear: {gear}")
            values = data.get("stats") or {}
            if values:
                def g(key):
                    return values.get(key, 0) or 0
                print(f"          stats: ap={g('$ap'):.0f} sp={g('$sp'):.0f} "
                      f"crit={g('$tcr'):.3f} hit={g('$thi'):.3f} eva={g('$tdo'):.3f} "
                      f"haste={g('$tha'):.3f} all={g('$cao'):.2f}/{g('$cai'):.2f} "
                      f"phy={g('$cpo'):.2f}/{g('$cpi'):.2f} mag={g('$cmo'):.2f}/{g('$cmi'):.2f} "
                      f"dot={g('$cdo'):.2f}/{g('$cdi'):.2f} heal={g('$cho'):.2f}/{g('$chi'):.2f}")
            if data.get("auras"):
                top = sorted(data["auras"].items(), key=lambda kv: -kv[1])[:6]
                print("          status: " + " ".join(f"{n}x{c}" for n, c in top))
            if data.get("boss_auras"):
                top = sorted(data["boss_auras"].items(), key=lambda kv: -kv[1])[:5]
                print("          boss auras: " + " ".join(f"{n}x{c}" for n, c in top))
            if data.get("anims"):
                top = sorted(data["anims"].items(), key=lambda kv: -kv[1])[:4]
                print("          telegraphs: " + " | ".join(f'"{m}"x{c}' for m, c in top))
            if data.get("zone_seq"):
                print(f"          zone: triggers={len(data['zone_seq'])} "
                      f"applied={data['zone_apply']} lost={data['zone_lost']}")
                base = data.get("start") or 0
                for t_ev, step, msg, taunt, zone, what in data["zone_seq"][:24]:
                    tag = "Truth" if "truth" in str(msg).lower() else "Listn"
                    print(f"            {t_ev - base:6.0f}s  step={step:<3} {tag} "
                          f"taunt={taunt} zone={zone}/{what}")
            # What the character was holding the moment it died -- the aura,
            # the X position and the last telegraph seen before each death.
            last_aura = last_x = last_anim = None
            for t_ev, kind_ev, payload in data.get("events") or []:
                if kind_ev == "auras":
                    last_aura = payload
                elif kind_ev == "pos":
                    last_x = payload
                elif kind_ev == "anims":
                    last_anim = payload
                elif kind_ev == "death" and data["start"]:
                    print(f"          death@{t_ev - data['start']:.0f}s "
                          f"aura={last_aura} x={last_x} anim={last_anim}")

        if team_deaths:
            print(f"  note: {team_deaths} deaths across the party")
        cap = BOSS_SHIELD.get(boss)
        for slot, account, data in rows:
            if data["dmg"] == 0:
                print(f"  note: slot{slot} dealt no damage")
            tha = (data.get("stats") or {}).get("$tha", 0) or 0
            if tha > 0.5:
                print(f"  note: slot{slot} haste {tha:.2f} is above the 50% cap (wasted)")
            if cap and data.get("big"):
                print(f"  note: slot{slot} {data['big']} hits at the Boss Shield cap "
                      f"(~{cap:,}) -- burst is decayed, value is hit frequency/uptime")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    run_id = args[0] if args else latest_run()
    report(run_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
