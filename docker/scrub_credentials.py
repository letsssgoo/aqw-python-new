"""Blank out real credentials so they are never baked into a Docker image.

``bot/ultra/config.py`` is tracked with placeholders, but a developer's working
copy may hold the real ultra logins, and ``COPY . /app`` would copy that working
copy.  The Dockerfile runs this right after the copy, so the image only ever
contains the placeholders.  Real logins are supplied at runtime through the web
UI (stored under ``HUB_DATA_DIR``).

Usage:
    python docker/scrub_credentials.py [project_root]   (default: current dir)
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

PLACEHOLDER = 'AccConfig("ACCOUNT_USERNAME", "ACCOUNT_PASSWORD")'
ACCOUNTS_RE = re.compile(r'AccConfig\("[^"]*",\s*"[^"]*"\)')


def scrub_ultra_config(root: pathlib.Path) -> None:
    path = root / "bot" / "ultra" / "config.py"
    if not path.exists():
        return
    src = path.read_text(encoding="utf-8")
    scrubbed, count = ACCOUNTS_RE.subn(PLACEHOLDER, src)
    if count:
        path.write_text(scrubbed, encoding="utf-8")
    print(f"[scrub] {path}: {count} credential(s) replaced")


def scrub_players(root: pathlib.Path) -> None:
    path = root / "players.json"
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        data = None
    if isinstance(data, list) and data:
        path.write_text("[]\n", encoding="utf-8")
        print(f"[scrub] {path}: {len(data)} player(s) removed")
    else:
        print(f"[scrub] {path}: already empty")


def main() -> None:
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    scrub_ultra_config(root)
    scrub_players(root)


if __name__ == "__main__":
    main()
