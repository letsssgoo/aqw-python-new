"""Import smoke test for the one-class-per-file layout (plan.md 7.3).

Every module a launcher can be pointed at has to import cleanly and expose
either ``main(cmd)`` or a class with ``run()``, or ``start.py`` / ``gui.py``
will fail at startup rather than at the boss.  Importing ``daily`` and
``grammiel`` must also be *side-effect free* -- their ``input()`` and
``Bot(...)`` sit under ``if __name__ == "__main__"``, so a plain import has
to return instead of blocking on stdin.

Run:  python tools/test_imports.py
"""
from __future__ import annotations

import ast
import importlib
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PASSED = []
FAILED = []


def check(label, condition, detail=""):
    (PASSED if condition else FAILED).append(label)
    mark = "ok  " if condition else "FAIL"
    print(f"  {mark} {label}" + (f"   [{detail}]" if detail else ""))


#: Modules ``start.py`` / ``gui.py`` may be pointed at via ``BOT_PATH``.
ENTRY_MODULES = [
    "bot.ultra.ultra_tyndarius",
    "bot.ultra.ultra_engineer",
    "bot.ultra.ultra_ezrajal",
    "bot.ultra.ultra_warden",
    "bot.ultra.ultra_gramiel",
    "bot.ultra.ultra_gramiel_x",
    "bot.ultra.ultra_drakath",
    "bot.ultra.ultra_speaker",
    "bot.ultra.daily",
    "bot.ultra.grammiel",
    "bot.ultra.grimgaol",
    "bot.nation.materials.approval_and_favor",
    "bot.nation.materials.blood_from_the_void",
    "bot.nation.materials.fiend_emblem",
    "bot.nation.materials.0_max_bags",
    "bot.nation.materials.blood_gem",
    "bot.nation.materials.dark_crystal_shards",
    "bot.nation.materials.diamond_of_nulgath",
    "bot.nation.materials.fiend_token",
    "bot.nation.materials.gem_of_nulgath",
    "bot.nation.materials.tainted_gem",
    "bot.nation.materials.totem_of_nulgath",
    "bot.nation.materials.unidentified_10",
    "bot.nation.materials.unidentified_13",
    "bot.nation.materials.voucher_of_nulgath",
    "bot.nation.materials.voucher_of_nulgath_non_member",
    "bot.nation.contract_exchange",
    "bot.nation.dirty_deeds_done_dirt_cheap",
    "bot.nation.dragon_slayer_reward",
    "bot.nation.dreadrock_gem_exchange",
    "bot.nation.emblem_of_nulgath",
    "bot.nation.essence_of_defeat_reagent",
    "bot.nation.kissthe_void",
    "bot.nation.new_worlds_new_opportunities",
    "bot.nation.nulgath_larvae",
    "bot.nation.supplies_to_spin_the_wheel_of_chance",
    "bot.nation.swindle_return_policy",
    "bot.nation.the_assistant",
    "bot.nation.void_knight_sword_quest",
    "bot.nation.assisting_crag_and_bamboozle",
    "bot.nation.empowering_items",
    "bot.nation.nation_loyalty_rewarded",
    "bot.nation.time_is_money",
    "bot.nation.voucher_item_choose",
    "bot.nation.various.forge_gem_stones_for_nulgath",
    "bot.nation.various.carve_the_unidentified_gem_stone",
    "bot.nation.various.leery_exchange_gold",
    "bot.bank_check",
    "bot.farm.leveling",
    "bot.farm.gold_farm",
    "bot.farm.dark_war_legion_gold",
    "bot.farm.rep.good_rep",
    "bot.farm.rep.vampire_rep",
]

#: Modules that deliberately define no class -- they re-export one from
#: elsewhere so the historical ``BOT_PATH`` string keeps resolving.
RE_EXPORTS = {
    "bot.ultra.ultra_gramiel_x": "bot.ultra.ultra_gramiel",
    "bot.ultra.ultra_speaker": "bot.ultra.core_ultra",
}

#: Modules that only exist to be imported.
SUPPORT_MODULES = [
    "bot.ultra.config",
    "bot.ultra.core_ultra",
    "bot.nation.core_nation",
    "bot.core_bots",
    "bot.core_farms",
]


def main() -> int:
    print("=" * 74)
    print("import smoke test: entry points and the shared base")
    print("=" * 74)

    print("\n-- support modules --")
    for name in SUPPORT_MODULES:
        try:
            importlib.import_module(name)
            check(f"imports {name}", True)
        except Exception as exc:                                  # noqa: BLE001
            check(f"imports {name}", False, f"{type(exc).__name__}: {exc}")

    print("\n-- shared base --")
    core = importlib.import_module("bot.ultra.core_ultra")
    check("UltraSpeaker lives in core_ultra", hasattr(core, "UltraSpeaker"))
    check("CoreUltra has no boss methods left",
          not any(hasattr(core.CoreUltra, m) for m in
                  ("UltraTyndarius", "UltraEngineer", "UltraWarden",
                   "UltraEzrajal", "UltraGrammiel", "ChampionDrakath",
                   "DailyUltra", "gramiel_heal", "initUltraGrammiel")),
          str([m for m in ("UltraTyndarius", "UltraEngineer", "UltraWarden",
                           "UltraEzrajal", "UltraGrammiel", "ChampionDrakath",
                           "DailyUltra", "gramiel_heal", "initUltraGrammiel")
               if hasattr(core.CoreUltra, m)]))
    check("CoreUltra still has the shared machinery",
          all(hasattr(core.CoreUltra, m) for m in
              ("apply_loadout", "join_and_wait", "precast_buffs",
               "attack_loop", "finish", "message_handler", "_parse_message",
               "_on_counter_attack", "_abort")))

    print("\n-- entry modules --")
    for name in ENTRY_MODULES:
        try:
            mod = importlib.import_module(name)
        except Exception as exc:                                  # noqa: BLE001
            check(f"imports {name}", False, f"{type(exc).__name__}: {exc}")
            continue
        check(f"imports {name} without side effects", True)

        if name in ("bot.ultra.daily", "bot.ultra.grammiel"):
            # These two are `py -m` entry points: their slot comes from stdin
            # under __main__, so there is no main(cmd) for start.py to call.
            # What must exist is the class the __main__ block instantiates.
            cls = getattr(mod, "DailyUltra", None) or getattr(mod, "UltraGrammiel")
            check(f"{name} exposes a runnable class",
                  inspect.iscoroutinefunction(cls.run) if cls else False,
                  getattr(cls, "__name__", "?"))
        else:
            # Everything start.py / gui.py can be pointed at.
            check(f"{name}.main(cmd) exists",
                  callable(getattr(mod, "main", None)))

    print("\n-- per-boss classes --")
    for name in ENTRY_MODULES:
        if not name.startswith("bot.ultra.ultra_"):
            continue
        mod = importlib.import_module(name)
        owned = [o for _, o in inspect.getmembers(mod, inspect.isclass)
                 if o.__module__ == name and o.__name__.startswith("Ultra")]
        imported = [o for _, o in inspect.getmembers(mod, inspect.isclass)
                    if o.__module__ != name and o.__name__.startswith("Ultra")]
        if name in RE_EXPORTS:
            # Deliberately a shim: it must re-export the one real class and
            # define nothing of its own, or the two copies start drifting.
            check(f"{name} re-exports exactly one boss class",
                  len(imported) == 1 and not owned,
                  f"owned={owned} imported={imported}")
            if imported:
                check(f"{imported[0].__name__}.run() is awaitable",
                      inspect.iscoroutinefunction(imported[0].run))
                check(f"{name} re-exports it from {RE_EXPORTS[name]}",
                      imported[0].__module__ == RE_EXPORTS[name],
                      imported[0].__module__)
            continue
        check(f"{name} defines a class in its own file",
              len(owned) == 1, str([c.__name__ for c in owned]))
        if owned:
            check(f"{owned[0].__name__}.run() is awaitable",
                  inspect.iscoroutinefunction(owned[0].run))

    print("\n-- daily.py runs the four bosses in order --")
    daily = importlib.import_module("bot.ultra.daily")
    order = [m for m in ("step_tyndarius", "step_engineer",
                         "step_ezrajal", "step_warden")
             if hasattr(daily.DailyUltra, m)]
    check("all four steps present, in order",
          order == ["step_tyndarius", "step_engineer",
                    "step_ezrajal", "step_warden"], str(order))

    print("\n-- __main__ guard really guards --")
    # Parsed rather than grepped: the docstrings *mention* ``input()`` and
    # ``Bot(...)``, so a substring test would fail on prose.  What matters is
    # where the actual calls sit relative to the guard.
    for name in ("daily", "grammiel", "ultra_speaker"):
        path = Path(f"bot/ultra/{name}.py")
        tree = ast.parse(path.read_text(encoding="utf-8"))

        guard = None
        for node in tree.body:
            if (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
                    and isinstance(node.test.left, ast.Name)
                    and node.test.left.id == "__name__"):
                guard = node.lineno
        check(f"{name}.py has a __main__ guard", guard is not None,
              f"line {guard}")

        calls = sorted(
            (n.func.id, n.lineno) for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id in ("input", "Bot")
        )
        check(f"{name}.py calls input()/Bot() somewhere", bool(calls),
              str(calls))
        for fn, lineno in calls:
            check(f"{name}.py: {fn}() line {lineno} is under the guard",
                  guard is not None and lineno > guard,
                  f"guard at {guard}")

    print("\n-- speaker pane roles --")
    # ultra_speaker_pane.bat pipes 1..4; each number picks an account AND a
    # class.  If a role has no loadout, or roles run out before accounts do,
    # that pane stops the moment it starts -- so assert the pairing here.
    cfg = importlib.import_module("bot.ultra.config")
    check("SOLO_ROLES has one entry per account",
          len(cfg.SOLO_ROLES) == len(cfg.ACCOUNTS),
          f"{len(cfg.SOLO_ROLES)} roles / {len(cfg.ACCOUNTS)} accounts")
    for pane in range(1, len(cfg.ACCOUNTS) + 1):
        role = cfg.get_solo_role(pane)
        try:
            cfg.get_solo_loadout(role)
            ok, detail = True, "has a loadout"
        except KeyError as exc:
            ok, detail = False, str(exc)
        check(f"pane {pane} -> {role} is gearable", ok, detail)

    # A piped 5 must fail loudly instead of wrapping to role 1 via list[-1].
    try:
        cfg.get_solo_role(len(cfg.ACCOUNTS) + 1)
        check("out-of-range pane raises", False, "no exception")
    except KeyError as exc:
        check("out-of-range pane raises", "no speaker role" in str(exc), str(exc))

    print("=" * 74)
    print(f"passed {len(PASSED)}   failed {len(FAILED)}")
    print("=" * 74)
    if FAILED:
        print("FAILURES:")
        for f in FAILED:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
