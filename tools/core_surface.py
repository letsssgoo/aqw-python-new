"""Audit permukaan core: kelas mana di berkas mana, dan nama apa yang bertabrakan.

    python tools/core_surface.py             # semua kelas Core*
    python tools/core_surface.py --collide   # hanya nama yang muncul di >1 kelas

Kelas ``Core*`` di referensi **tidak saling mewarisi**, jadi nama yang sama di dua
kelas adalah dua implementasi berbeda, bukan override -- ``Adv.BuyItem``
(CoreAdvanced) menjalankan ``GetItemReq``, ``Core.BuyItem`` (CoreBots) tidak.
Skrip ini memetakannya supaya sebelum memetakan ``X.Method`` ke fungsi kita,
kelas penerimanya bisa dipastikan dulu.

Keluarga ``*2`` / ``CoreEngine*`` / ``CoreSkills`` / ``CoreEnhancements`` adalah
salinan dependensi bot ultra, bukan bagian dari pohon script utama; barisnya
ditandai supaya tidak dianggap tabrakan yang perlu diurus.
"""
from __future__ import annotations

import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = pathlib.Path(r"C:\Users\ACER\AppData\Roaming\Skua\Scripts")

#: Salinan dependensi (bukan bagian pohon script utama).
COPIES = ("CoreBots2", "CoreAdvanced2", "CoreFarms2", "CoreDailies2", "CoreEngine",
          "CoreEngine2", "CoreEnginev1", "CoreEnginev3", "CoreSkills",
          "CoreEnhancements")

CLASS_RE = re.compile(r"^[ \t]*public (?:sealed |abstract |partial )*class (\w+)", re.M)
METHOD_RE = re.compile(
    r"^[ \t]*public (?:static |async |override |virtual |new |sealed )*"
    r"[\w\?<>\[\],\. ]+?\s(\w+)\s*\(", re.M)


def scan() -> dict[str, dict]:
    found: dict[str, dict] = {}
    if not SOURCE.exists():
        print(f"!! sumber tidak ada: {SOURCE}")
        return found
    for path in SOURCE.rglob("Core*.cs"):
        text = path.read_text(encoding="utf-8", errors="replace")
        names = [m.group(1) for m in CLASS_RE.finditer(text)]
        for name in names:
            if not name.startswith("Core"):
                continue
            entry = found.setdefault(name, {"file": str(path.relative_to(SOURCE))
                                            .replace("\\", "/"), "methods": set()})
            entry["methods"].update(m.group(1) for m in METHOD_RE.finditer(text))
    return found


def main() -> int:
    collide_only = "--collide" in sys.argv
    cores = scan()
    if not cores:
        return 1

    if not collide_only:
        print("=== kelas Core* yang diport vs salinan dependensi ===")
        for name, info in sorted(cores.items()):
            mark = "  (salinan)" if name in COPIES else ""
            print(f"  {name:22} {len(info['methods']):4} metode  {info['file']}{mark}")

    owners: dict[str, list[str]] = {}
    for name, info in cores.items():
        for method in info["methods"]:
            owners.setdefault(method, []).append(name)

    print(f"\n=== nama metode di >1 kelas Core ({len(cores)} kelas dipindai) ===")
    main_tree = [(m, sorted(c)) for m, c in owners.items()
                 if len(c) > 1 and not all(n in COPIES for n in c)]
    for method, classes in sorted(main_tree):
        # yang penting: nama yang muncul di dua kelas pohon utama yang berbeda
        real = [c for c in classes if c not in COPIES]
        flag = "  <-- perlu dicek" if len(real) > 1 else ""
        print(f"  {method:34} {', '.join(classes)}{flag}")
    print(f"\n  {len(main_tree)} nama; yang bertanda perlu dipastikan kelas "
          f"penerimanya di tiap titik panggil.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
