#!/usr/bin/python3
"""JSON output for the waybar custom/pomo module (reads the state written by ~/.local/bin/pomo).

Usage: pomo.py            print the module JSON
       pomo.py toggle     pause/resume the timer (waybar on-click)
       pomo.py skip       jump to the next phase (waybar on-click-right)
"""
import json
import os
import signal
import sys
import time
from pathlib import Path

STATE_FILE = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "pomo.json"
ICONS = {"work": "🍅", "short": "☕", "long": "🌴"}
LABELS = {"work": "Work", "short": "Short break", "long": "Long break"}
# English strings are the keys; the language comes from the TUI state file.
TRANSLATIONS = {
    "fr": {
        "Work": "Travail",
        "Short break": "Pause courte",
        "Long break": "Pause longue",
        "Completed pomodoros: {done}": "Pomodoros terminés : {done}",
        "Click: pause/resume · Right click: next phase": "Clic : pause/reprise · Clic droit : phase suivante",
    },
}

try:
    state = json.loads(STATE_FILE.read_text())
    os.kill(state["pid"], 0)  # is the TUI still running?
    if len(sys.argv) > 1:
        os.kill(state["pid"], {"toggle": signal.SIGUSR1, "skip": signal.SIGUSR2}[sys.argv[1]])
        raise SystemExit
except Exception:
    print(json.dumps({"text": "", "class": "inactive"}))
    raise SystemExit


def _(text: str, **kwargs) -> str:
    text = TRANSLATIONS.get(state.get("lang", "en"), {}).get(text, text)
    return text.format(**kwargs) if kwargs else text


phase, running = state["phase"], state["running"]
secs = max(0, round(state["ends_at"] - time.time())) if running and state["ends_at"] else state["remaining"]
percent = int(100 * (state["total"] - secs) / state["total"]) if state["total"] else 0
print(json.dumps({
    "text": f"{ICONS[phase]} {secs // 60:02d}:{secs % 60:02d}" + ("" if running else " ⏸"),
    "tooltip": f"{_(LABELS[phase])} — {percent}%\n"
               + _("Completed pomodoros: {done}", done=state["done"]) + "\n"
               + _("Click: pause/resume · Right click: next phase"),
    "class": [phase, "running" if running else "paused"],
    "percentage": percent,
}))
