"""Packet capture harness for analysing bot traffic.

Runs a bot script for a fixed duration while recording every packet sent to and
received from the game server, plus internal skill-decision events.

Usage:
    python tools/capture_run.py --duration 600
    python tools/capture_run.py --duration 600 --script bot.scion_flame.0_all_flames

Credentials are read from the .env file (USERNAME_AQW / PASSWORD_AQW / SERVER)
so they never appear on the command line or in the log.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

from core.bot import Bot  # noqa: E402
from core.command import Command, SkillMode  # noqa: E402
from core.player import Player  # noqa: E402

DEFAULT_SCRIPT = "bot.scion_flame.0_all_flames"
DEFAULT_DURATION = 600
DEFAULT_LOG_DIR = REPO_ROOT / "capture_logs"

# Anything carrying a session token must never reach the log.
_SENSITIVE_MARKERS = ("<pword>", "SPIDER#")


def _redact(message: str) -> str:
    lowered = message.lower()
    if "<pword>" in lowered:
        start = lowered.index("<pword>")
        end = lowered.find("</pword>", start)
        end = len(message) if end == -1 else end + len("</pword>")
        return message[:start] + "<pword>[REDACTED]</pword>" + message[end:]
    for marker in _SENSITIVE_MARKERS:
        if marker in message and marker == "SPIDER#":
            return "[REDACTED-LOGIN-NICK]"
    return message


def _classify(raw: str) -> tuple[str, str]:
    """Return (payload_kind, detail) for a raw server message."""
    stripped = raw.lstrip()
    if stripped.startswith("{"):
        try:
            data = json.loads(raw)
            cmd = data.get("b", {}).get("o", {}).get("cmd", "?")
            return "json", str(cmd)
        except Exception:
            return "json", "unparsed"
    if stripped.startswith("<"):
        tag = stripped[1:].split(None, 1)[0].rstrip(">/")
        return "xml", tag
    if stripped.startswith("%") and stripped.endswith("%"):
        parts = [p for p in stripped.split("%") if p]
        return "xt", parts[2] if len(parts) > 2 else "?"
    return "other", "?"


class CaptureLog:
    """Append-only JSONL writer shared by all capture hooks."""

    def __init__(self, path: Path):
        self.path = path
        self._fh = path.open("w", encoding="utf-8")
        self.count = 0

    def write(self, direction: str, kind: str, detail: str, **fields) -> None:
        record = {
            "t": round(time.time(), 3),
            "ts": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "dir": direction,
            "kind": kind,
            "detail": detail,
        }
        record.update(fields)
        self._fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.count += 1
        if self.count % 500 == 0:
            self._fh.flush()

    def close(self) -> None:
        try:
            self._fh.flush()
            self._fh.close()
        except Exception:
            pass


def install_capture(bot: Bot, log: CaptureLog) -> None:
    """Monkey-patch the bot so all TX/RX and skill decisions are recorded."""

    # ---- outbound -------------------------------------------------------
    original_write = bot.write_message

    def write_message(message):  # noqa: ANN001
        kind, detail = _classify(message)
        log.write(
            "TX",
            kind,
            detail,
            raw=_redact(message),
            monsters=bot.player.CELL if hasattr(bot.player, "CELL") else None,
            hp=bot.player.CURRENT_HP,
            mp=bot.player.MANA,
        )
        return original_write(message)

    bot.write_message = write_message

    # ---- inbound --------------------------------------------------------
    def on_message(raw: str) -> None:
        kind, detail = _classify(raw)
        fields = {"raw": raw}
        if kind == "xt" and detail in ("ct", "uotls"):
            fields["raw"] = raw  # kept; parser trims later
        log.write("RX", kind, detail, **fields)

    bot.subscribe(on_message)

    # ---- skill decision hooks -------------------------------------------
    original_can_use = Player.canUseSkill

    def canUseSkill(self, skillNumber: int):  # noqa: N802, ANN001
        # Run the real check first: a crash here must not be caused by this
        # hook, so every read below is guarded.
        result = original_can_use(self, skillNumber)
        reason = None
        if not result:
            if skillNumber >= len(self.SKILLS):
                reason = "out_of_range"
            else:
                skill = self.SKILLS[skillNumber]
                mana = skill.mana * self.ManaCost
                deadline = skill.next_use
                if self.MANA < mana:
                    reason = "mana"
                elif deadline is not None and deadline > datetime.now():
                    reason = "cooldown"
                else:
                    reason = "unknown"
        log.write(
            "EVT",
            "canUseSkill",
            "ok" if result else "blocked",
            skill=skillNumber,
            reason=reason,
            mp=self.MANA,
            hp=self.CURRENT_HP,
        )
        return result

    Player.canUseSkill = canUseSkill

    # ---- use_skill entry/exit -------------------------------------------
    original_use_skill = Command.use_skill

    async def use_skill(  # noqa: ANN001
        self,
        index: int = 0,
        target_monsters: str = "*",
        hunt: bool = False,
        skill_mode: SkillMode = SkillMode.ALL,
        reload_delay: int = Command.MIN_SKILL_GAP_MS,
        **kwargs,          # buff_only is keyword-only upstream
    ) -> bool:
        started = time.time()
        try:
            outcome = await original_use_skill(
                self, index, target_monsters, hunt, skill_mode, reload_delay,
                **kwargs,
            )
        except Exception as exc:  # pragma: no cover - defensive
            log.write(
                "EVT",
                "use_skill",
                "error",
                skill=index,
                target=target_monsters,
                error=repr(exc),
            )
            raise
        fields = dict(
            skill=index,
            target=target_monsters,
            hunt=hunt,
            mode=skill_mode.name,
            elapsed_ms=round((time.time() - started) * 1000, 1),
            mp=self.bot.player.MANA,
            hp=self.bot.player.CURRENT_HP,
        )
        if not outcome:
            # Why was a ready slot refused? canUseSkill already logged "ok"
            # for every call, so the cause is one of the later branches:
            # no target in the cell, skill_mode filtering this slot's `tgt`,
            # or the player dying mid-call. Capture enough state to tell them
            # apart without another instrumented run.
            cell = self.bot.player.CELL
            alive_here = sum(
                1 for m in self.bot.monsters
                if m.is_alive and m.frame == cell
            )
            skill = (self.bot.player.SKILLS[index]
                     if index < len(self.bot.player.SKILLS) else {})
            fields.update(
                cell=cell,
                alive_in_cell=alive_here,
                n_monsters=len(self.bot.monsters),
                tgt=skill.get("tgt"),
                safe=self.check_is_skill_safe(index),
                ready_ms=self.bot.player.skill_ready_in_ms(index),
                dead=self.bot.player.ISDEAD,
            )
        log.write("EVT", "use_skill", "ok" if outcome else "skipped", **fields)
        return outcome

    Command.use_skill = use_skill

    # ---- readiness scheduler entry/exit ---------------------------------
    # Logged separately from use_skill so the two questions stay separable:
    # "did the scheduler find something ready" (use_next_skill) vs
    # "did the cast go out" (use_skill).
    original_use_next_skill = Command.use_next_skill

    async def use_next_skill(  # noqa: ANN001
        self,
        skill_list,
        target_monsters: str = "*",
        hunt: bool = False,
        skill_mode: SkillMode = SkillMode.ALL,
        reload_delay: int = Command.MIN_SKILL_GAP_MS,
    ) -> bool:
        started = time.time()
        outcome = await original_use_next_skill(
            self, skill_list, target_monsters, hunt, skill_mode, reload_delay
        )
        log.write(
            "EVT",
            "use_next_skill",
            "cast" if outcome else "idle",
            waited_ms=round((time.time() - started) * 1000, 1),
            slots=list(dict.fromkeys(skill_list)),
            ms_since_last_cast=round(time.time() * 1000 - self.last_skill_cast_ms, 1),
            backoff_ms=getattr(self.bot, "spam_backoff_ms", 0),
        )
        return outcome

    Command.use_next_skill = use_next_skill

    # ---- skill load-out (captured once when sAct arrives) ---------------
    original_handle = bot.handle_server_response

    async def handle_server_response(msg: str):  # noqa: ANN001
        await original_handle(msg)
        if '"cmd":"sAct"' in msg or '"cmd": "sAct"' in msg:
            try:
                skills = [
                    {
                        "i": i,
                        "name": s.get("name"),
                        "tgt": s.get("tgt"),
                        "cd": s.get("cd"),
                        "mp": s.get("mp"),
                        "tgtMax": s.get("tgtMax"),
                    }
                    for i, s in enumerate(bot.player.SKILLS)
                ]
                log.write("EVT", "skill_loadout", "sAct", skills=skills)
            except Exception:
                pass

    bot.handle_server_response = handle_server_response


def _read_credentials() -> tuple[str, str, str]:
    load_dotenv(REPO_ROOT / ".env")
    users = os.getenv("USERNAME_AQW", "").strip().strip("[]")
    pwds = os.getenv("PASSWORD_AQW", "").strip().strip("[]")
    servers = os.getenv("SERVER", "").strip().strip("[]")
    if not users or not pwds:
        raise SystemExit(
            "Missing credentials. Set USERNAME_AQW / PASSWORD_AQW / SERVER in .env"
        )
    return users.split(",")[0].strip(), pwds.split(",")[0].strip(), (
        servers.split(",")[0].strip() if servers else "Gravelyn"
    )


MAX_ATTEMPTS = 5
RETRY_BACKOFF_S = 15


async def _run(script_module: str, duration: int, log_dir: Path) -> None:
    """Run the script for `duration` seconds, reconnecting on dropped sockets.

    A transient RST must not waste the whole capture window: each attempt gets a
    fresh Bot (Bot.__init__ state is heavily mutated by packet handling), and the
    script resumes from the item quantities already in inventory.
    """
    module = importlib.import_module(script_module)
    real_main = module.main

    username, password, server = _read_credentials()

    log_path = log_dir / f"capture_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
    log = CaptureLog(log_path)

    print(f"[capture] script={script_module} duration={duration}s")
    print(f"[capture] log={log_path}")

    started = time.time()
    attempt = 0
    try:
        while True:
            remaining = duration - (time.time() - started)
            if remaining <= 0:
                break
            attempt += 1
            if attempt > MAX_ATTEMPTS:
                log.write(
                    "EVT", "lifecycle", "max_attempts", attempts=attempt - 1
                )
                print(f"[capture] giving up after {attempt - 1} attempts")
                break

            bot = Bot(
                itemsDropWhiteList=[],
                cmdDelay=600,
                showDebug=False,
                autoRelogin=False,
                isScriptable=True,
                showChat=True,
            )
            bot.set_login_info(username, password, server)
            install_capture(bot, log)
            log.write(
                "EVT", "lifecycle", "attempt_start", attempt=attempt,
                remaining=round(remaining, 1),
            )

            async def bounded_main(cmd: Command, budget: float = remaining):
                try:
                    await asyncio.wait_for(real_main(cmd), timeout=budget)
                except asyncio.TimeoutError:
                    log.write(
                        "EVT", "lifecycle", "duration_reached", seconds=budget
                    )
                    print(f"\n[capture] budget exhausted - stopping bot")
                except Exception as exc:
                    log.write(
                        "EVT", "lifecycle", "script_error", error=repr(exc)
                    )
                    print(f"[capture] script error: {exc!r}")

            try:
                await bot.start_bot(bounded_main)
            except Exception as exc:
                log.write(
                    "EVT", "lifecycle", "attempt_error",
                    attempt=attempt, error=repr(exc),
                )
                print(f"[capture] attempt {attempt} error: {exc!r}")

            if time.time() - started >= duration:
                break

            if attempt < MAX_ATTEMPTS and time.time() - started < duration:
                log.write(
                    "EVT", "lifecycle", "reconnecting",
                    attempt=attempt, backoff=RETRY_BACKOFF_S,
                )
                print(
                    f"[capture] connection lost after "
                    f"{round(time.time() - started, 1)}s - "
                    f"retrying in {RETRY_BACKOFF_S}s"
                )
                await asyncio.sleep(RETRY_BACKOFF_S)
    finally:
        log.write(
            "EVT",
            "lifecycle",
            "stopped",
            elapsed=round(time.time() - started, 1),
            records=log.count,
            attempts=attempt,
        )
        log.close()
        print(f"[capture] wrote {log.count} records -> {log_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture bot packet traffic")
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION)
    parser.add_argument("--script", default=DEFAULT_SCRIPT)
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))
    args = parser.parse_args()

    log_dir = Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    try:
        asyncio.run(_run(args.script, args.duration, log_dir))
    except KeyboardInterrupt:
        print("\n[capture] interrupted")


if __name__ == "__main__":
    main()
