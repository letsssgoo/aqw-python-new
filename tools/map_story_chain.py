"""Peta rantai sebuah core story: siapa memanggil siapa, mana basisnya.

    python tools/map_story_chain.py "C:/.../CoreSoW.cs"
    python tools/map_story_chain.py "C:/.../CoreAOR.cs" --detail

Untuk setiap method ``public void X(...)`` di berkas itu dicetak:

  - quest gerbang  : ``isCompletedBefore(N)`` paling awal
  - quest terakhir : id quest tertinggi yang dipakai (biasanya penutup region)
  - memanggil      : method lain **di berkas yang sama** (urutan rantai)
  - luar           : core lain yang dipanggil (``SoW.``, ``Story.``, ``Adv.`` ...)

Urutan rantai = method yang tidak dipanggil method lain di berkas itu adalah
basisnya; sisanya tersusun dari situ.
"""
import pathlib
import re
import sys
from collections import Counter, defaultdict

METHOD = re.compile(r"public void (\w+)\s*\(")
# Hanya di posisi *id quest* -- angka biasa juga muncul sebagai item id.
QUEST = re.compile(r"(?:isCompletedBefore|KillQuest|MapItemQuest|QuestProgression"
                   r"|EnsureAccept|EnsureComplete|EnsureAcceptmultiple"
                   r"|RegisterQuests)\(\s*(\d+)")
GATE = re.compile(r"isCompletedBefore\(\s*(\d+)")
SAME_CALL = re.compile(r"\b(\w+)\s*\(")
OUTSIDE = re.compile(r"\b(SoW|AOR|AoR|Adv|Story|Core|Farm|Bot|Legion|YNR|DoT)\.(\w+)\s*\(")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = pathlib.Path(sys.argv[1])
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    starts = [(i, m.group(1)) for i, line in enumerate(lines)
              if (m := METHOD.match(line.strip()))]
    names = {name for _, name in starts}
    names.discard("ScriptMain")

    report = []
    for idx, (line_no, name) in enumerate(starts):
        if name == "ScriptMain":
            continue
        end = starts[idx + 1][0] if idx + 1 < len(starts) else len(lines)
        body = "\n".join(lines[line_no:end])
        quests = [int(q) for q in QUEST.findall(body)]
        # Method agregat (CompleteCoreSoW/DoAll) memanggil hampir semuanya dan
        # menyembunyikan akar rantai; jangan dihitung sebagai pemanggil.
        if len(quests) and False:
            pass
        gate = GATE.search(body)
        calls = Counter(m.group(1) for m in SAME_CALL.finditer(body))
        same = sorted(n for n in calls if n in names and n != name)
        outside = sorted({f"{m.group(1)}.{m.group(2)}"
                          for m in OUTSIDE.finditer(body)})
        report.append({
            "name": name,
            "gate": gate.group(1) if gate else "-",
            "last": max(quests) if quests else 0,
            "calls": same,
            "outside": outside,
        })

    aggregate = {r["name"] for r in report if len(r["calls"]) >= 5}
    called_by_others = {n for r in report if r["name"] not in aggregate
                        for n in r["calls"]}
    print(f"{path.name}: {len(report)} method")
    print(f"{'method':22} {'gerbang':>8} {'terakhir':>9}  memanggil (di berkas ini)")
    for r in report:
        if r["name"] in aggregate:
            base = "  (agregat)"
        elif r["name"] in called_by_others:
            base = ""
        else:
            base = "  <- basis"
        print(f"{r['name']:22} {r['gate']:>8} {r['last']:>9}  "
              f"{', '.join(r['calls']) or '-'}{base}")

    if "--detail" in sys.argv:
        print("\n== panggilan ke luar berkas ==")
        for r in report:
            if r["outside"]:
                print(f"  {r['name']:22} {', '.join(r['outside'])}")

    bases = [r["name"] for r in report if r["name"] not in called_by_others]
    print(f"\nbasis (tidak dipanggil method lain di berkas ini): "
          f"{', '.join(bases) or '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
