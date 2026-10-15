"""Check that no ported line logs through the wrong channel.

    python tools/check_log_scope.py

The rule the ports follow: a line the source logs goes through the engine's log
(``cmd.bot.log``, i.e. the reference bot's ``Core.Logger``), never a bare
``print``, and it keeps the source's exact text so a run reads the same here as
it does there.  What is ours to add -- "this engine cannot do X" -- carries a tag
like ``[vhl]`` so the two are told apart in one stream.

Bare ``print`` is invisible to ``Bot.showLog`` and sits outside the engine's
timestamped output, so it is what this checks for.  ``cmd.bot.log`` inside a
function without ``cmd`` is the other half: that is a ``NameError`` waiting for
the one run that reaches it, which is why it is checked with the AST rather than
by eye.
"""
from __future__ import annotations

import ast
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

#: Ported modules -- everything under ``bot/`` that carries port logic.
ALLOW_BARE_PRINT = {
    # ``bot/ultra`` and the GUIs are the engine's own, not ports: they predate
    # the rule and print through the engine's output path.
    "bot/ultra/", "bot/semples/", "bot/templeshrine/", "bot/scion_flame/",
    "bot/slavery/", "bot/potion/",
}


def is_port(path: pathlib.Path) -> bool:
    rel = path.relative_to(REPO_ROOT).as_posix()
    return not any(rel.startswith(prefix) for prefix in ALLOW_BARE_PRINT)


def main() -> int:
    checked = 0
    problems = []
    for path in sorted((REPO_ROOT / "bot").rglob("*.py")):
        if not is_port(path):
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id == "print":
                problems.append(f"{rel}:{node.lineno} bare print")
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            args = {a.arg for a in node.args.args}
            args |= {a.arg for a in node.args.kwonlyargs}
            if node.args.vararg:
                args.add(node.args.vararg.arg)
            for call in ast.walk(node):
                if not isinstance(call, ast.Call):
                    continue
                fn = call.func
                if not isinstance(fn, ast.Attribute) or fn.attr not in ("log", "debug"):
                    continue
                owner = fn.value
                if not (isinstance(owner, ast.Attribute) and owner.attr == "bot"
                        and isinstance(owner.value, ast.Name)
                        and owner.value.id == "cmd"):
                    continue
                if "cmd" not in args:
                    problems.append(
                        f"{rel}:{call.lineno} cmd.bot.{fn.attr}() in "
                        f"{node.name}() without a cmd argument")
        checked += 1

    for line in problems:
        print("  FAIL " + line)
    print(f"  checked {checked} ported modules, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
