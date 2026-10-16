"""Extract SmartEnhance's two enhancement libraries into bot/core_advanced_tables.py.

Dev tool: it reads the reference tree (outside this repo) and rewrites the
table module, so a source update can be re-checked instead of trusted.

    python tools/extract_smart_enhance_tables.py

Old docstring:

Sumber: CoreAdvanced.cs -> SmartEnhance -> ForgeEnhancementLibrary / AweEnhancementLibrary.

Keluaran: berkas .py berisi FORGE_LIBRARY dan AWE_LIBRARY, tiap entri:

    Plan(classes=(...), requires=("Vainglory", ...), condition=None,
         type="Lucky", cape="Vainglory", helm="Anima", weapon=None)

  * classes   : nama kelas, lowercase, seperti di sumber
  * requires  : flag `unlocked` yang harus True; kalau ada yang False -> fallback
  * condition : lambda(u) untuk blok yang syaratnya bukan sekadar AND flag
  * type/cape/helm/weapon : nilai yang di-set; kalau sumbernya ekspresi
                (ternary), nilainya lambda(u)
  * others    : pernyataan lain di blok itu, apa adanya (dilaporkan, tidak dijalankan)
"""
from __future__ import annotations

import pathlib
import re
import sys

SOURCE = pathlib.Path(r"C:\Users\ACER\AppData\Roaming\Skua\Scripts\CoreAdvanced.cs")
REPO = pathlib.Path(__file__).resolve().parent.parent
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else \
    REPO / "bot" / "core_advanced_tables.py"
text = SOURCE.read_text(encoding="utf-8", errors="replace")
lines = text.splitlines()


def find_line(needle: str) -> int:
    for n, line in enumerate(lines, 1):
        if needle in line:
            return n
    raise SystemExit(f"tidak ditemukan: {needle}")


def brace_end(start: int) -> int:
    depth = 0
    for n in range(start - 1, len(lines)):
        depth += lines[n].count("{") - lines[n].count("}")
        if n > start - 1 and depth <= 0:
            return n + 1
    raise SystemExit("brace tidak seimbang")


def strip_comment(line: str) -> str:
    in_str, out, i = False, [], 0
    while i < len(line):
        ch = line[i]
        if ch == '"':
            in_str = not in_str
        if not in_str and line[i:i + 2] == "//":
            break
        out.append(ch)
        i += 1
    return "".join(out)


def statements(start: int, end: int) -> list[tuple[int, str]]:
    result, buffer, first = [], "", 0
    for n in range(start, end):
        raw = strip_comment(lines[n - 1]).strip()
        if not raw or raw in ("{", "}") or raw.startswith(("#region", "#endregion")):
            continue
        # label case/default menutup pernyataan sebelumnya dan berdiri sendiri
        if re.match(r'(case "[^"]+":|default:)', raw):
            if buffer:
                result.append((first, buffer.rstrip("{}").strip()))
                buffer = ""
            result.append((n, raw))
            continue
        if not buffer:
            first = n
        buffer = f"{buffer} {raw}".strip()
        if buffer.endswith((";", "{", "}")):
            result.append((first, buffer.rstrip("{}").strip()))
            buffer = ""
    if buffer:
        result.append((first, buffer))
    return result


def _split_ternary(expr: str):
    """Pecah ``t ? a : b`` pada kedalaman 0; None kalau bukan ternary."""
    depth, q = 0, None
    for i, ch in enumerate(expr):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "?" and depth == 0:
            q = i
            break
    if q is None:
        return None
    depth, colon, nested = 0, None, 0
    for i in range(q + 1, len(expr)):
        ch = expr[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "?" and depth == 0:
            nested += 1
        elif ch == ":" and depth == 0:
            if nested == 0:
                colon = i
                break
            nested -= 1
    if colon is None:
        return None
    return expr[:q].strip(), expr[q + 1:colon].strip(), expr[colon + 1:].strip()


def strip_outer(expr: str) -> str:
    """Lepas kurung yang membungkus seluruh ekspresi, berulang."""
    expr = expr.strip()
    while expr.startswith("(") and expr.endswith(")"):
        depth, closes_at_end = 0, False
        for i, ch in enumerate(expr):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    closes_at_end = (i == len(expr) - 1)
                    break
        if not closes_at_end:
            break
        expr = expr[1:-1].strip()
    return expr


def convert_ternaries(expr: str) -> str:
    """C# ternary kanan-asosiatif -> Python conditional, secara rekursif."""
    expr = strip_outer(expr)
    parts = _split_ternary(expr)
    if parts is None:
        return expr
    condition, taken, other = parts
    return (f"({convert_ternaries(taken)} if {convert_ternaries(condition)} "
            f"else {convert_ternaries(other)})")


def to_python(expr: str) -> str:
    expr = expr.strip().rstrip(";").strip()
    for prefix in ("EnhancementType.", "CapeSpecial.", "HelmSpecial.",
                   "WeaponSpecial.", "(EnhancementType)"):
        expr = expr.replace(prefix, "")
    expr = re.sub(r"\bCore\.isCompletedBefore\((\d+)\)", r"completed_before(\1)", expr)
    expr = re.sub(r"\bu(\w+)\(\)", r'unlocked["\1"]', expr)
    expr = expr.replace("CurrentHelmSpecial()", 'current_special("helm")')
    expr = expr.replace("CurrentCapeSpecial()", 'current_special("cape")')
    expr = expr.replace("CurrentWeaponSpecial()", 'current_special("weapon")')
    expr = convert_ternaries(expr)
    expr = re.sub(r"!(?!=)", " not ", expr)
    expr = expr.replace("||", " or ").replace("&&", " and ")
    expr = re.sub(r"\s+", " ", expr).strip()
    # nama enum (Ravenous, Awe_Blast, ...) -> string; sisanya variabel kita
    keep = {"unlocked", "completed_before", "current_special", "and", "or",
            "not", "None", "True", "False", "if", "else", "is", "in"}
    def quote(match):
        word = match.group(0)
        return word if word in keep else f'"{word}"'
    return re.sub(r"\b[A-Za-z_][A-Za-z0-9_]*\b(?![\"\'])(?![\w\[])", quote, expr)


def case_indent(start: int, end: int) -> int:
    indents = [len(lines[n - 1]) - len(lines[n - 1].lstrip())
               for n in range(start, end) if re.match(r'\s*case "', lines[n - 1])]
    return min(indents)


CASE = re.compile(r'case "([^"]+)":')
SIMPLE_FLAG = re.compile(r'^unlocked\["(\w+)"\]( and unlocked\["\w+"\])*$')


def parse(start: int, end: int, indent: int) -> list[dict]:
    rows: list[dict] = []
    current: dict | None = None
    for n, raw in statements(start, end):
        line = lines[n - 1]
        case = CASE.match(strip_comment(line).strip())
        if case and (len(line) - len(line.lstrip())) == indent:
            if current is None:
                current = {"classes": [case.group(1)], "requires": [],
                           "condition": None, "type": None, "cape": None,
                           "helm": None, "weapon": None, "others": []}
            else:
                current["classes"].append(case.group(1))
            continue
        if current is None:
            continue
        if raw.startswith("goto default"):
            current["condition"] = "False"
            continue
        if raw.startswith("if ("):
            condition = to_python(raw[raw.find("(") + 1:raw.rfind(")")])
            if SIMPLE_FLAG.match(condition) and not current["condition"]:
                current["requires"] += re.findall(r'unlocked\["(\w+)"\]', condition)
            else:
                # beberapa if/goto default di satu blok: fallback kalau SALAH SATU
                # gagal, jadi syaratnya digabung dengan 'or'
                if current["condition"]:
                    current["condition"] = f"({current['condition']}) or ({condition})"
                else:
                    current["condition"] = condition
            continue
        if raw.startswith("default:"):
            continue
        if raw.startswith(("break", "return")):
            rows.append(current)
            current = None
            continue
        assign = re.match(r"(type|cSpecial|hSpecial|wSpecial)\s*=\s*(.+)$", raw)
        if assign:
            key = {"type": "type", "cSpecial": "cape",
                   "hSpecial": "helm", "wSpecial": "weapon"}[assign.group(1)]
            current[key] = to_python(assign.group(2))
            continue
        current["others"].append(raw)
    if current:
        rows.append(current)
    return rows


def render(name: str, rows: list[dict]) -> str:
    out = [f"{name}: Tuple[Plan, ...] = ("]
    for row in rows:
        classes = ", ".join(f'"{c}"' for c in row["classes"])
        requires = ", ".join(f'"{r}"' for r in sorted(set(row["requires"])))
        parts = [f"classes=({classes},)"]
        if requires or row["condition"] == "False":
            parts.append(f"requires=({requires},)")
        if row["condition"] and row["condition"] != "False":
            parts.append(f"condition=lambda unlocked: {row['condition']}")
        for key in ("type", "cape", "helm", "weapon"):
            value = row[key]
            if value is None:
                continue
            if re.fullmatch(r'"[^"]*"', value) or (re.fullmatch(r"[\w\.]+", value)
                                                  and " if " not in value):
                parts.append(f"{key}={value}"
                             if value.startswith('"') else f'{key}="{value}"')
            else:
                parts.append(f"{key}=lambda unlocked: {value}")
        if row["others"]:
            others = ", ".join(f'"{o}"' for o in row["others"])
            parts.append(f"others=({others},)")
        out.append("    Plan(" + ", ".join(parts) + "),")
    out.append(")")
    return "\n".join(out)


forge_start = find_line("bool ForgeEnhancementLibrary()")
awe_start = find_line("void AweEnhancementLibrary()")
smart_start = find_line("public void SmartEnhance(string? className, bool ForceEnh, WeaponSpecial? weaponOverride)")
smart_end = brace_end(smart_start)
forge = parse(forge_start, awe_start, case_indent(forge_start, awe_start))
awe = parse(awe_start, smart_end, case_indent(awe_start, smart_end))

OUT.write_text(
    '"""Tabel SmartEnhance, diekstrak dari CoreAdvanced.cs (jangan diedit tangan).\n\n'
    'Tiap Plan = satu blok ``case`` di sumber: kelas apa yang kena, flag apa yang\n'
    'harus terbuka, dan enhancement apa yang dipasang.  ``requires`` kosong dan\n'
    '``condition`` None berarti blok itu tanpa syarat; ``condition`` lambda dipakai\n'
    'untuk blok yang syaratnya bukan sekadar AND flag.\n"""\n'
    'from dataclasses import dataclass\nfrom typing import Callable, Optional, Tuple\n\n\n'
    '@dataclass(frozen=True)\n'
    'class Plan:\n'
    '    classes: Tuple[str, ...]\n'
    '    requires: Tuple[str, ...] = ()\n'
    '    condition: Optional[Callable[[dict], bool]] = None\n'
    '    type: Optional[object] = None\n'
    '    cape: Optional[object] = None\n'
    '    helm: Optional[object] = None\n'
    '    weapon: Optional[object] = None\n'
    '    others: Tuple[str, ...] = ()\n\n\n'
    + render("FORGE_LIBRARY", forge) + "\n\n" + render("AWE_LIBRARY", awe) + "\n",
    encoding="utf-8", newline="\n")

print(f"forge: {len(forge)} blok | awe: {len(awe)} blok -> {OUT}")
print(f"tanpa syarat: {len([r for r in forge + awe if r['condition'] is None and not r['requires']])}")
print(f"pakai requires: {len([r for r in forge + awe if r['requires']])}")
print(f"pakai condition lambda: {len([r for r in forge + awe if r['condition'] and r['condition'] != 'False'])}")
print(f"blok dengan others: {len([r for r in forge + awe if r['others']])}")
for r in forge + awe:
    if r["others"]:
        print("   others:", r["classes"][:2], "->", r["others"][:1])
