#!/usr/bin/python3
"""Sortie JSON pour le module waybar custom/pomo (lit l'état écrit par ~/.local/bin/pomo)."""
import json, os, signal, sys, time
from pathlib import Path

f = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "pomo.json"
try:
    s = json.loads(f.read_text())
    os.kill(s["pid"], 0)  # le TUI tourne-t-il encore ?
    if len(sys.argv) > 1:  # pomo.py toggle|skip  (clics waybar)
        os.kill(s["pid"], {"toggle": signal.SIGUSR1, "skip": signal.SIGUSR2}[sys.argv[1]])
        raise SystemExit
except Exception:
    print(json.dumps({"text": "", "class": "inactive"}))
    raise SystemExit

secs = max(0, round(s["ends_at"] - time.time())) if s["running"] and s["ends_at"] else s["remaining"]
icon = {"work": "🍅", "short": "☕", "long": "🌴"}[s["phase"]]
label = {"work": "Travail", "short": "Pause courte", "long": "Pause longue"}[s["phase"]]
text = f"{icon} {secs // 60:02d}:{secs % 60:02d}" + ("" if s["running"] else " ⏸")
pct = int(100 * (s["total"] - secs) / s["total"]) if s["total"] else 0
print(json.dumps({
    "text": text,
    "tooltip": f"{label} — {pct}%\nPomodoros terminés : {s['done']}\n"
               "Clic : pause/reprise · Clic droit : phase suivante",
    "class": [s["phase"], "running" if s["running"] else "paused"],
    "percentage": pct,
}))
