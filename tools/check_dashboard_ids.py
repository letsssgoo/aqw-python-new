"""Cari `el('x').value = ...` yang elemennya tidak ada di halaman.

Error nyata: "Cannot set properties of null (setting 'value')" -> handler mati
tanpa pesan.  Skrip ini mendaftar setiap penulisan `.value`/`.textContent`/
`.innerHTML`/`.checked` pada elemen hasil `el('id')`/`getElementById('id')`, lalu
memeriksa id-nya ada sebagai `id="..."` di halaman sub-app itu (atau dibuat oleh
components.js / players_dropdown.js).

Dipakai:
    python tools/check_dashboard_ids.py
"""
import pathlib
import re

WEB = pathlib.Path("app/web_dashboard")
WRITE = re.compile(r"(?:el|getElementById)\(\s*'([^']+)'\s*\)\s*\.\s*(\w+)\s*=")
MAKE = re.compile(r"""id\s*=\s*["']{1,2}([A-Za-z0-9_-]+)["']{1,2}""")

rows = []
for page_dir in sorted(p for p in WEB.iterdir() if p.is_dir()):
    js = page_dir / "main.js"
    if not js.exists():
        continue
    html = (page_dir / "index.html").read_text(encoding="utf-8", errors="replace") \
        if (page_dir / "index.html").exists() else ""
    extra = "\n".join(
        f.read_text(encoding="utf-8", errors="replace")
        for f in (WEB / "components.js", WEB / "players_dropdown.js") if f.exists())
    known = set(MAKE.findall(html)) | set(MAKE.findall(extra))

    for line_no, line in enumerate(js.read_text(encoding="utf-8").splitlines(), 1):
        for item, prop in WRITE.findall(line):
            rows.append((page_dir.name, line_no, item, prop, item in known))

missing = [r for r in rows if not r[4]]
print(f"penulisan properti pada elemen: {len(rows)} | id tidak ditemukan: {len(missing)}")
for page, line_no, item, prop, _ in missing:
    print(f"  {page}/main.js:{line_no}  el('{item}').{prop} = ...   <- id tidak ada")
if not missing:
    print("  (semua id ada)")
