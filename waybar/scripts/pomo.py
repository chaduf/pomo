#!/usr/bin/python3
"""JSON output for the waybar custom/pomo module (reads the state written by ~/.local/bin/pomo).

Usage: pomo.py            print the module JSON
       pomo.py toggle     pause/resume the timer (waybar on-click)
       pomo.py skip       next phase, or lap in stopwatch mode (waybar on-click-right)
"""
import json
import os
import signal
import sys
import time
from pathlib import Path

STATE_FILE = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "pomo.json"
ICONS = {"work": "🍅", "short": "☕", "long": "🌴", "stopwatch": "⏱"}
LABELS = {"work": "Work", "short": "Short break", "long": "Long break"}
# English strings are the keys; the language comes from the TUI state file.
TRANSLATIONS = {
    "fr": {
        "Work": "Travail",
        "Short break": "Pause courte",
        "Long break": "Pause longue",
        "Completed pomodoros: {done}": "Pomodoros terminés : {done}",
        "Click: pause/resume · Right click: next phase": "Clic : pause/reprise · Clic droit : phase suivante",
        "Stopwatch — {n} lap(s)": "Chronomètre — {n} tour(s)",
        "Click: start/pause · Right click: lap": "Clic : démarrer/pause · Clic droit : tour",
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


def clock(secs: int) -> str:
    h, rest = divmod(secs, 3600)
    return f"{h}:{rest // 60:02d}:{rest % 60:02d}" if h else f"{rest // 60:02d}:{rest % 60:02d}"


running = state["running"]
paused = "" if running else " ⏸"
if state.get("mode") == "stopwatch":
    secs = int(state["elapsed"] + (time.time() - state["since"] if running else 0))
    print(json.dumps({
        "text": f"{ICONS['stopwatch']} {clock(secs)}{paused}",
        "tooltip": _("Stopwatch — {n} lap(s)", n=state["laps"]) + "\n"
                   + _("Click: start/pause · Right click: lap"),
        "class": ["stopwatch", "running" if running else "paused"],
    }))
    raise SystemExit

phase = state["phase"]
secs = max(0, round(state["ends_at"] - time.time())) if running and state["ends_at"] else state["remaining"]
percent = int(100 * (state["total"] - secs) / state["total"]) if state["total"] else 0
print(json.dumps({
    "text": f"{ICONS[phase]} {clock(secs)}{paused}",
    "tooltip": f"{_(LABELS[phase])} — {percent}%\n"
               + _("Completed pomodoros: {done}", done=state["done"]) + "\n"
               + _("Click: pause/resume · Right click: next phase"),
    "class": [phase, "running" if running else "paused"],
    "percentage": percent,
}))
