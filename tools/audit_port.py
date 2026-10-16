"""Audit padanan port: bandingkan panggilan di metode sumber vs fungsi kita.

    python tools/audit_port.py                 # semua yang berpasangan
    python tools/audit_port.py core_nation     # batasi ke satu berkas port

Untuk tiap fungsi port (``snake_case``), cari metode sumber bernama PascalCase/
camelCase yang sama di pohon script, kumpulkan nama panggilan di kedua sisi,
terjemahkan sisi sumber lewat tabel ``EQUIVALENT``, lalu laporkan:

  ``-``  ada di sumber, tidak ada di port kita   -> logika hilang?
  ``+``  ada di port kita, tidak ada di sumber   -> tambahan buatan sendiri?

Hanya baris yang bisa dijelaskan yang masuk tabel; sisanya sengaja dibiarkan
muncul supaya tiap temuan harus diperiksa, bukan diabaikan.
"""
from __future__ import annotations

import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = pathlib.Path(r"C:\Users\ACER\AppData\Roaming\Skua\Scripts")

#: Nama sisi sumber -> nama di port kita (salah satu cukup).
EQUIVALENT = {
    "Core.Logger": ("cmd.bot.log", "print"),
    "Core.Sleep": ("cmd.sleep",),
    "Bot.Sleep": ("cmd.sleep",),
    "Core.Join": ("join_map",),
    "Core.JoinMap": ("join_map",),
    "Core.HuntMonster": ("hunt_item",),
    "Core.HuntMonsterMulti": ("hunt_item",),
    "Core.KillMonster": ("hunt_item", "hunt_item_by_id"),
    "Core.EnsureAccept": ("ensure_accept_quest",),
    "Core.EnsureComplete": ("ensure_turn_in_quest",),
    "Core.CheckInventory": ("has_item", "all_owned", "has_any_item",
                            "has_item_id", "is_in_inventory", "first_missing"),
    "Core.AddDrop": ("add_drop",),
    "Core.ToBank": ("inv_to_bank",),
    "Core.EquipClass": ("equip_class",),
    "Core.Equip": ("equip_item",),
    "Core.SellItem": ("sell_item",),
    "Core.RegisterQuests": ("register_quest",),
    "Core.CancelRegisteredQuests": ("cancel_registered_quests",),
    "Core.GetMapItem": ("get_map_item",),
    "Core.FarmingLogger": ("farming_logger",),
    "Core.BuyItem": ("buy_item",),
    "Adv.BuyItem": ("adv_buy_item", "buy_item"),
    "Core.ResetQuest": ("ensure_accept_quest",),
    "Core.DarkMakaiItem": ("dark_makai_item",),
    "Farm.Experience": ("farm_experience",),
    "Farm.Gold": ("farm_gold",),
    "Farm.FactionRank": ("get_faction_rank",),
    "Story.KillQuest": ("kill_quest",),
    "Story.MapItemQuest": ("map_item_quest",),
    "Story.PreLoad": (),
    "Daily.EldersBlood": ("elders_blood",),
    "Bot.Wait.ForPickup": ("wait_for_item", "hunt_item"),
    "Bot.ShouldExit": ("is_still_connected",),
}

#: Panggilan sisi kita yang memang milik kita (pagar/laporan), bukan logika.
OURS = {
    "report_once", "cmd.bot.log", "cmd.sleep", "is_still_connected", "print",
    "shop_entry", "load_shop_entry", "meet_shop_requirements", "points_to_level",
    "is_in_bank", "bank_to_inv", "get_player", "get_quest_reward_entries",
    "get_loaded_quest", "quest_in_progress", "is_in_inventory",
    "cmd.farming_logger", "farming_logger", "has_item_id", "sell_item",
    "random", "len", "int", "str", "bool", "list", "dict", "range", "getattr",
    "min", "max", "any", "all", "enumerate", "tuple", "set", "sorted",
}

CALL_CS = re.compile(r"\b([A-Z]\w*)\.(\w+)\s*\(")
METHOD_CS = re.compile(r"^[ \t]*(?:public|private|protected|internal)[^\n=;]*"
                       r"\b(\w+)\s*\(", re.M)
CALL_PY = re.compile(r"\b([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)*)\s*\(")
DEF_PY = re.compile(r"^(?:async )?def (\w+)\(", re.M)


def bodies(text: str) -> dict[str, str]:
    """nama metode -> badannya, untuk satu berkas C#."""
    found: dict[str, str] = {}
    for match in METHOD_CS.finditer(text):
        name = match.group(1)
        brace = text.find("{", match.end())
        if brace < 0:
            continue
        depth, index = 0, brace
        while index < len(text):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    break
            index += 1
        found[name] = text[brace:index]
    return found


def pascal_camel(snake: str) -> tuple[str, str]:
    parts = snake.split("_")
    return ("".join(p.capitalize() for p in parts),
            parts[0] + "".join(p.capitalize() for p in parts[1:]))


def source_index() -> dict[str, tuple[str, str]]:
    """PascalCase/camelCase -> (berkas, badan) untuk seluruh pohon Nation + core."""
    index: dict[str, tuple[str, str]] = {}
    targets = list((SOURCE / "Nation").rglob("*.cs"))
    targets += [SOURCE / f for f in
                ("CoreBots.cs", "CoreFarms.cs", "CoreStory.cs", "CoreDailies.cs",
                 "CoreAdvanced.cs")]
    targets += list((SOURCE / "Story" / "Nation").rglob("*.cs"))
    for path in targets:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for name, body in bodies(text).items():
            index.setdefault(name, (path.name, body))
    return index


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    index = source_index()
    print(f"metode sumber terindeks: {len(index)}")

    checked = 0
    flagged: list[str] = []
    for path in sorted((REPO_ROOT / "bot").rglob("*.py")):
        if only and only not in path.name:
            continue
        text = path.read_text(encoding="utf-8")
        for match in DEF_PY.finditer(text):
            func = match.group(1)
            if func.startswith("_"):
                continue
            big, small = pascal_camel(func)
            hit = index.get(big) or index.get(small)
            if hit is None:
                continue
            source_file, body = hit
            ours = text[match.start():text.find("\ndef ", match.end())]
            checked += 1

            have = {c.split(".")[-1] for c in CALL_PY.findall(ours)}
            have_all = set(CALL_PY.findall(ours))
            missing = []
            for receiver, method in CALL_CS.findall(body):
                full = f"{receiver}.{method}"
                if full not in EQUIVALENT:
                    continue
                aliases = EQUIVALENT[full]
                if aliases and not any(a.split(".")[-1] in have for a in aliases):
                    missing.append(full)
            extras = sorted(
                c for c in have_all
                if "." in c and c not in OURS
                and not c.startswith(("cmd.", "self.", "bot."))
                and c.split(".")[-1] not in OURS
                and c.split(".")[-1] not in {m.split(".")[-1] for m in
                                             (f"{r}.{m2}" for r, m2 in
                                              CALL_CS.findall(body))})
            if missing or extras:
                line = (f"{path.relative_to(REPO_ROOT)}::{func}  "
                        f"(sumber {source_file})")
                for item in sorted(set(missing)):
                    line += f"\n     - {item}"
                for item in extras[:5]:
                    line += f"\n     + {item}"
                flagged.append(line)

    print(f"fungsi diperiksa: {checked}, ada selisih: {len(flagged)}")
    for line in flagged:
        print("\n" + line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
