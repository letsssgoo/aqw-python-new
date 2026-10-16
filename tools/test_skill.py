"""Regression test for model.Skill against a real sAct payload.

The payload below is copied verbatim from
``capture_logs/capture_20261004_210744.jsonl`` (Legion Revenant, 21:07:50).

Run:  python tools/test_skill.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model import Skill  # noqa: E402

# Verbatim from the wire: note slot 5 ships tgtMax/tgtMin/id as null.
SACT = [
    {"nam": "Malevolent Burst", "typ": "aa", "ref": "aa", "tgt": "h", "tgtMax": 3,
     "tgtMin": 1, "mp": -15, "cd": 1500, "id": 1558, "anim": "AttackEff",
     "strl": "attack", "range": 1, "damage": 1.0, "dsrc": "SP1", "auto": True},
    {"nam": "Atramentous Shade", "typ": "m", "ref": "a1", "tgt": "h", "tgtMax": 3,
     "tgtMin": 1, "mp": 10, "cd": 6000, "id": 1559, "anim": "a1", "strl": "a1",
     "forceResult": "crit", "damage": 0.85, "dsrc": "SP1"},
    {"nam": "Bone Besieger", "typ": "m", "ref": "a2", "tgt": "h", "tgtMax": 3,
     "tgtMin": 1, "mp": 15, "cd": 6000, "id": 1560, "anim": "a2", "strl": "a2",
     "damage": 1.4, "dsrc": "SP1"},
    {"nam": "Legion Feast", "typ": "m", "ref": "a3", "tgt": "f", "tgtMax": 7,
     "tgtMin": 1, "mp": 15, "cd": 6000, "id": 1561, "anim": "a3", "strl": "a3",
     "auras": [{"nam": "Infernal Contract", "dur": 6}]},
    {"nam": "Unrelenting", "typ": "m", "ref": "a4", "tgt": "h", "tgtMax": 3,
     "tgtMin": 1, "mp": 20, "cd": 12000, "id": 1562, "anim": "a4", "strl": "a4"},
    {"nam": None, "typ": "i", "ref": "i1", "tgt": "f", "tgtMax": None,
     "tgtMin": None, "mp": 0, "cd": 60000, "id": None, "anim": "", "strl": ""},
]

ok = 0
failures = []


def check(label: str, got, want) -> None:
    global ok
    if got == want:
        ok += 1
    else:
        failures.append(f"{label}: got {got!r}, want {want!r}")


skills = [Skill.from_payload(s) for s in SACT]


# --- dict compatibility: this is why Skill subclasses dict -------------------
s0 = skills[0]
check("dict: item access", s0["cd"], 1500)
check("dict: .get with default", s0.get("nope", "dflt"), "dflt")
check("dict: .get without default", s0.get("nope"), None)
s0["nextUse"] = datetime.now()
check("dict: item assignment", isinstance(s0.get("nextUse"), datetime), True)
check("dict: keys preserved", "dsrc" in s0, True)
check("isinstance dict", isinstance(s0, dict), True)
check("len", len(skills), 6)


# --- null-tolerant coercion: the scroll slot ships null ----------------------
s5 = skills[5]
check("slot5 tgtMax None -> 1", s5.max_targets, 1)
check("slot5 tgtMin None -> 1", s5.min_targets, 1)
check("slot5 id None -> 0", s5.id, 0)
check("slot5 name None -> ''", s5.name, "")
check("slot5 mana", s5.mana, 0)
check("slot5 cooldown", s5.cooldown_ms, 60000)


# --- the int(None) crash this replaces --------------------------------------
try:
    int(s5.get("tgtMax", 1))          # what use_skill used to do
    check("old expression raised", "TypeError", "no exception")
except TypeError:
    check("old expression raised", "TypeError", "TypeError")
check("Skill.max_targets does not raise", s5.max_targets, 1)


# --- signed mana: the auto-attack returns mana ------------------------------
check("aa mana is negative", s0.mana, -15)
check("aa mana_cost", s0.mana_cost(), -15)
check("aa mana_cost with multiplier", s0.mana_cost(2.0), -30.0)
# canUseSkill does `MANA < mana * ManaCost`; with a negative cost this can
# never be true, so the auto-attack is never starved of mana.
check("aa never mana-starved", 100 < s0.mana, False)
check("skill 1 mana", skills[1].mana, 10)


# --- classification ---------------------------------------------------------
check("aa type", s0.type, "aa")
check("aa is_auto_attack", s0.is_auto_attack, True)
check("aa is_auto", s0.is_auto, True)
check("skill 1 type", skills[1].type, "m")
check("scroll is_item", s5.is_item, True)
check("skill 1 needs monster", skills[1].needs_monster, True)
check("skill 1 is_attack", skills[1].is_attack, True)
check("skill 1 not buff", skills[1].is_buff, False)
check("skill 3 friendly", skills[3].target, "f")
check("skill 3 is_buff", skills[3].is_buff, True)
check("skill 3 needs_monster False", skills[3].needs_monster, False)


# --- the SkillMode branches in use_skill ------------------------------------
check("h + ATTACK_ONLY passes filter", skills[1].target == "h", True)
check("f + BUFF_ONLY passes filter", skills[3].target == "f", True)
check("f + ATTACK_ONLY filtered", skills[3].target == "h", False)


# --- cooldown reduction: capped at 0.5, same as Player.updateNextUse --------
check("cdr 0 -> full cd", s0.effective_cooldown_ms(0.0), 1500.0)
check("cdr 0.5 -> half cd", s0.effective_cooldown_ms(0.5), 750.0)
check("cdr 0.8444 clamped to 0.5", s0.effective_cooldown_ms(0.8444), 750.0)
check("cdr clamped above 1", s0.effective_cooldown_ms(1.5), 750.0)
check("cdr negative -> full cd", s0.effective_cooldown_ms(-1.0), 1500.0)
check("slot4 cdr 0.5", skills[4].effective_cooldown_ms(0.5), 6000.0)
check("slot5 cdr 0.5", s5.effective_cooldown_ms(0.5), 30000.0)


# --- cast state / readiness -------------------------------------------------
check("no nextUse -> ready", s5.is_ready(), True)
check("no nextUse -> 0 ms", s5.ready_in_ms(), 0.0)

soon = datetime.now() + timedelta(milliseconds=800)
skills[1].next_use = soon
check("next_use setter wrote through", skills[1].next_use, soon)
check("not ready while armed", skills[1].is_ready(), False)
wait = skills[1].ready_in_ms()
check("ready_in_ms ~800", 700 <= wait <= 850, True)
check("ready_in_ms never negative", skills[1].ready_in_ms(
    datetime.now() + timedelta(seconds=5)), 0.0)
check("past deadline ready", skills[1].is_ready(
    datetime.now() + timedelta(seconds=5)), True)


# --- absent keys must not raise --------------------------------------------
bare = Skill()
check("bare mana", bare.mana, 0)
check("bare cd", bare.cooldown_ms, 0)
check("bare tgtMax", bare.max_targets, 1)
check("bare target", bare.target, "")
check("bare is_ready", bare.is_ready(), True)
check("bare auras", bare.auras, [])
check("bare type", bare.type, "")
check("bare damage", bare.damage, 0.0)
check("bare name", bare.name, "")


# --- from_payload copies, does not alias ------------------------------------
orig = {"nam": "X", "cd": 100}
copied = Skill.from_payload(orig)
copied["cd"] = 999
check("from_payload copies", orig["cd"], 100)
check("from_payload handles None", isinstance(Skill.from_payload(None), Skill), True)


# --- non-numeric garbage in numeric fields ----------------------------------
weird = Skill({"mp": "abc", "cd": None, "tgtMax": [], "damage": "n/a"})
check("bad mp -> 0", weird.mana, 0)
check("bad cd -> 0", weird.cooldown_ms, 0)
check("bad tgtMax -> 1", weird.max_targets, 1)
check("bad damage -> 0.0", weird.damage, 0.0)


# --- display helper ---------------------------------------------------------
desc = skills[4].describe()
check("describe mentions cd", "cd 12000" in desc, True)
check("describe mentions name", "Unrelenting" in desc, True)
check("str", str(skills[4]).startswith("<Skill "), True)


print("=" * 74)
for line in failures:
    print("FAIL", line)
print(f"passed {ok}   failed {len(failures)}")
print("=" * 74)
sys.exit(1 if failures else 0)
