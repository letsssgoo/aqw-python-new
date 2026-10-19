"""Peta `Bot.Quests.UpdateQuest(...)` -> story yang mengerjakan quest itu.

Tujuan: setiap pemanggilan `UpdateQuest(q)` diganti dengan "kerjakan story yang
memiliki quest q".  Skrip ini memetakan dulu:

  - quest id -> method story yang memanggil KillQuest/MapItemQuest/QuestProgression
    dengan id itu (berkas + method)
  - status di repo ini: quest id itu sudah muncul di port kita atau belum
  - apa yang menyusul pemanggilan (join map / farm / cek state)

Dipakai:
    python tools/map_update_quest.py             # ringkasan + tulis peta
    python tools/map_update_quest.py --detail    # plus tiap pemanggilan
Output: update_quest_map.md (lokal, tidak di-commit)
"""
import pathlib
import re
import sys
from collections import Counter, defaultdict

SKUA = pathlib.Path(r"C:\Users\ACER\AppData\Roaming\Skua\Scripts")
REPO = pathlib.Path(__file__).resolve().parent.parent
OUT = REPO / "update_quest_map.md"

CALL = re.compile(r"Quests\.UpdateQuest\(\s*([^)]*)\)")
STORY = re.compile(r"(?:Story\.)?(?:KillQuest|MapItemQuest|QuestProgression)\(\s*(\d+)")
NAME = re.compile(r"//\s*(.+?)\s+(\d{2,5})\s*$")
OWNER = re.compile(r"(?:public|private|internal)\s+(?:static\s+)?(?:async\s+)?[\w<>\[\]]+\s+(\w+)\s*\(")
ALIGN_SLOT = "41"


def code_of(line: str) -> str:
    return line.split("//")[0]


def repo_has(qid: str) -> str:
    """Apakah quest id ini muncul di port kita (bot/ atau model/)?"""
    pat = re.compile(r"\b" + re.escape(qid) + r"\b")
    for path in list((REPO / "bot").rglob("*.py")) + list((REPO / "model").rglob("*.py")):
        try:
            if pat.search(path.read_text(encoding="utf-8", errors="replace")):
                return path.relative_to(REPO).as_posix()
        except OSError:
            continue
    return ""


calls = []
story_owner = {}
story_name = {}

for path in sorted(SKUA.rglob("*.cs")):
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        continue
    method = ""
    last_comment = ""
    for i, raw in enumerate(lines, 1):
        code = code_of(raw)
        m = OWNER.search(raw)
        if m:
            method = m.group(1)
        cm = NAME.search(raw.rstrip())
        if cm:
            story_name[cm.group(2)] = cm.group(1)
        if "//" in raw and not code.strip():
            last_comment = raw.split("//", 1)[1].strip()
        sm = STORY.search(code)
        if sm and sm.group(1) not in story_owner:
            story_owner[sm.group(1)] = (path.name, method)
        um = CALL.search(code)
        if not um:
            continue
        args = [a.strip() for a in um.group(1).split(",")]
        nxt = ""
        for follow in lines[i:i + 4]:
            f = code_of(follow).strip()
            if f:
                nxt = f
                break
        calls.append({"file": path.name, "line": i, "args": args,
                      "method": method, "comment": last_comment, "next": nxt})

groups = defaultdict(list)          # (file, method) -> [quest id]
two_arg = []                        # (value, questID): gerbang akses map
dynamic = []                        # argumen bukan angka
unowned = []                        # quest id yang tak dipakai Story.* mana pun
for c in calls:
    if len(c["args"]) == 2:
        two_arg.append(c)
        continue
    qid = c["args"][0]
    if not qid.isdigit():
        dynamic.append(c)
        continue
    owner = story_owner.get(qid)
    if owner:
        groups[owner].append(qid)
    else:
        unowned.append(c)

lines_out = ["# Peta `Bot.Quests.UpdateQuest` -> story", "",
             f"Total {len(calls)} pemanggilan, {len(set(c['args'][-1] for c in calls))} quest id unik.", "",
             "| story yang mengerjakan | quest id (jumlah pemanggilan) | sudah ada di repo ini |",
             "|---|---|---|"]
for (sfile, smethod), qids in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    uniq = Counter(qids)
    ids_txt = ", ".join(f"{q} (x{n})" if n > 1 else q for q, n in sorted(uniq.items()))
    local = sorted({repo_has(q) for q in uniq if repo_has(q)})
    lines_out.append(f"| `{sfile}:{smethod}()` | {ids_txt} | {', '.join(local) or '—'} |")

lines_out += ["", "## Bentuk 2 argumen `UpdateQuest(nilai, questID)` -- gerbang akses map",
              "",
              "| berkas:baris | panggilan | method | sesudahnya |",
              "|---|---|---|---|"]
for c in two_arg:
    lines_out.append(f"| `{c['file']}:{c['line']}` | `UpdateQuest({', '.join(c['args'])})` | "
                     f"{c['method']} | `{c['next'][:60]}` |")

lines_out += ["", "## Argumen bukan angka (dinamis)", "",
              "| berkas:baris | panggilan | method | sesudahnya |", "|---|---|---|---|"]
for c in dynamic:
    lines_out.append(f"| `{c['file']}:{c['line']}` | `UpdateQuest({', '.join(c['args'])})` | "
                     f"{c['method']} | `{c['next'][:60]}` |")

lines_out += ["", "## Quest id yang tidak dipakai `Story.*` mana pun", "",
              "| quest id | berkas:baris | method | komentar | sesudahnya |", "|---|---|---|---|---|"]
for c in sorted(unowned, key=lambda c: c["args"][0]):
    lines_out.append(f"| {c['args'][0]} | `{c['file']}:{c['line']}` | {c['method']} | "
                     f"{c['comment'][:36]} | `{c['next'][:50]}` |")

if "--detail" in sys.argv:
    lines_out += ["", "## Detail tiap pemanggilan", "",
                  "| berkas:baris | panggilan | method | komentar | sesudahnya |",
                  "|---|---|---|---|---|"]
    for c in sorted(calls, key=lambda c: (c["args"][-1], c["file"], c["line"])):
        args = ", ".join(c["args"])
        lines_out.append(f"| `{c['file']}:{c['line']}` | `UpdateQuest({args})` | "
                         f"{c['method']} | {c['comment'][:40]} | `{c['next'][:60]}` |")

OUT.write_text("\n".join(lines_out) + "\n", encoding="utf-8", newline="\n")

print(f"peta ditulis ke {OUT.name}: {len(calls)} pemanggilan, "
      f"{len(groups)} grup story, {len(two_arg)} bentuk 2-argumen, "
      f"{len(dynamic)} dinamis, {len(unowned)} tanpa pemilik story\n")
for (sfile, smethod), qids in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:18]:
    uniq = Counter(qids)
    ids_txt = ", ".join(sorted(uniq))
    print(f"  {sfile}:{smethod}()  <- {len(uniq)} quest: {ids_txt[:80]}")
