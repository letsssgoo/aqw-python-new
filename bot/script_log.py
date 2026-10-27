"""``[Tag]`` prefixed logging for a script.

The reference for this is ``bot/enhancements/valiance.py``: every line it prints
carries the script's own name, so a run can be read without guessing which step
is talking -- ``[10:01:53][Valiance] Farming 'Eternity Blade' ...``.

That file prints straight to the terminal, which is right for a standalone
script.  The scripts ported into the bot also run inside panes, where
``cmd.bot.log`` is the channel the log tab and the per-account console read, so
the label is added there instead of on stdout -- the output is the same shape
(``[HH:MM:SS] [Tag] message``), and nothing loses its routing.

Usage::

    from bot.script_log import ScriptLog
    ...
    async def main(cmd):
        log = ScriptLog(cmd, "Cape of Awe")
        log.info("Farming the relic ...")
        log.success("Cape of Awe obtained.")
"""
from core.command import Command


class ScriptLog:
    """One script's log lines, prefixed with the script's own tag."""

    def __init__(self, cmd: Command, tag: str):
        self.cmd = cmd
        self.tag = tag

    def _emit(self, marker: str, message: str) -> None:
        self.cmd.bot.log(f"[{self.tag}] {marker}{message}")

    def info(self, message: str) -> None:
        """Ordinary progress: what the step is doing right now."""
        self._emit("", message)

    def success(self, message: str) -> None:
        """A step finished: something was obtained, unlocked or completed."""
        self._emit("OK: ", message)

    def warning(self, message: str) -> None:
        """Something was skipped or is missing, and the run goes on."""
        self._emit("warning: ", message)

    def error(self, message: str) -> None:
        """Something failed; the step (or the run) stops here."""
        self._emit("error: ", message)

    def farming(self, item: str, qty: int, where: str = "",
                held=None) -> None:
        """Report one farm step: what, how many, where, and how many are held.

        Every hunt already logs its own ``[farm]`` line; this is for a script that
        wants the step to say what it is doing *before* it starts, e.g.
        ``Farming Enchanted Scale x75 (held 12/75) @ dragontown/r4 vs Tempest
        Dracolich``.
        """
        line = f"Farming {item} x{qty}"
        if held is not None:
            line += f" (held {held}/{qty})"
        if where:
            line += f" @ {where}"
        self.info(line)
