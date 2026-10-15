"""Print full payloads we have not modelled yet: one complete inventory item,
one sAct skill block, and anything mentioning enhancement patterns.

    python tools/dump_payloads.py [capture.jsonl ...]
"""
import json
import pathlib
import sys

FILES = sys.argv[1:] or [
    "capture_logs/capture_20261004_195658.jsonl",
    "capture_logs/capture_20261004_210744.jsonl",
]

printed: set[str] = set()


def emit(label: str, obj, limit: int = 1400) -> None:
    if label in printed:
        return
    printed.add(label)
    text = json.dumps(obj, indent=1, ensure_ascii=False)
    if len(text) > limit:
        text = text[:limit] + "\n  ... (truncated)"
    print(f"\n--- {label} ---\n{text}")


def main() -> None:
    for path in FILES:
        p = pathlib.Path(path)
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("dir") != "RX":
                continue
            raw = rec.get("raw")
            if not isinstance(raw, str) or not raw.startswith("{"):
                continue
            try:
                msg = json.loads(raw)
            except (ValueError, TypeError):
                continue
            body = msg.get("b") if isinstance(msg, dict) else None
            inner = body.get("o") if isinstance(body, dict) else None
            if not isinstance(inner, dict):
                continue
            cmd = inner.get("cmd")
            if not isinstance(cmd, str):
                continue

            if cmd in ("loadInventoryBig", "retrieveInventory", "loadInventory"):
                emit(f"{cmd} -> one item", inner.get("items"), limit=2500)
            elif cmd == "sAct":
                emit("sAct full", inner)
            elif cmd == "dropItem":
                for it in (inner.get("items") or {}).values():
                    if isinstance(it, dict) and "EnhPatternID" in it:
                        emit("dropItem item WITH EnhPatternID", it, limit=2200)
                        break
                else:
                    emit("dropItem -> one item", inner.get("items"), limit=2200)
            elif cmd == "stu":
                emit("stu full", inner)

    # anything in the whole corpus that names an enhancement
    print("\n" + "=" * 70)
    print("enhancement-name occurrences in raw payloads")
    print("=" * 70)
    hits: dict[str, int] = {}
    for path in FILES:
        p = pathlib.Path(path)
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            for needle in ("EnhPattern", "enhName", "strEnh", "Valiance",
                           "Penitence", "Dauntless", "Acheron", "Eclipse"):
                if needle in line:
                    hits[needle] = hits.get(needle, 0) + 1
    for k, v in sorted(hits.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<16} x{v}")
    if not hits:
        print("  (none)")


if __name__ == "__main__":
    main()
