"""Fail when a module references an upper-case global it never defines.

A typo like ``DWARHFOLD_QUESTS`` (one extra H) compiles fine and only raises
when that farm actually runs -- which, on a live account, is hours in.  This
walks every module's top-level functions and lists uppercase ``Name`` loads that
are neither a module global, a parameter, a local, nor a builtin.

    python tools/check_undefined.py
"""
import ast
import builtins
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKIP = {".git", "__pycache__", "node_modules", "capture_logs", "android"}
BUILTINS = set(dir(builtins))
#: Only names that look like a constant; locals and helpers are covered by the
#: normal test suites running the code.
CONSTANT = re.compile(r"[A-Z][A-Z0-9_]+")


def _assigned(target, out: set) -> None:
    if isinstance(target, ast.Name):
        out.add(target.id)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            _assigned(element, out)


def module_globals(tree) -> set:
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                _assigned(target, names)
        elif isinstance(node, ast.AnnAssign):
            _assigned(node.target, names)
    return names


def function_locals(fn) -> set:
    names = set()
    args = fn.args
    for group in (args.posonlyargs, args.args, args.kwonlyargs):
        for arg in group:
            names.add(arg.arg)
    if args.vararg:
        names.add(args.vararg.arg)
    if args.kwarg:
        names.add(args.kwarg.arg)
    for statement in fn.body:
        for node in ast.walk(statement):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                names.add(node.id)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                   ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                names.add(node.name)
            elif isinstance(node, ast.arg):
                names.add(node.arg)
    return names


def main() -> int:
    problems = []
    for path in sorted(ROOT.rglob("*.py")):
        if any(part in SKIP for part in path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue        # compileall owns syntax; this check is about names
        globals_ = module_globals(tree)
        for fn in [n for n in tree.body
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            scope = globals_ | function_locals(fn) | BUILTINS
            for statement in fn.body:
                for node in ast.walk(statement):
                    if not isinstance(node, ast.Name):
                        continue
                    if not isinstance(node.ctx, ast.Load):
                        continue
                    if node.id in scope or not CONSTANT.fullmatch(node.id):
                        continue
                    problems.append(f"{path.relative_to(ROOT)}:{node.lineno}: "
                                    f"{fn.name}() uses undefined {node.id}")

    for line in sorted(set(problems)):
        print(line)
    print(f"undefined constants: {len(set(problems))}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
