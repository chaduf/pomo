"""Work time entries: segments, the entries log, crash recovery and iCalendar (.ics) files.

A "segment" is a stretch of actual work: {"work": <work number in the cycle>, "start": ts, "end": ts}.
Segments are collected during a cycle and recorded as time entries once the user names them."""
import json
import os
import re
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from . import system
from .i18n import _

DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "pomo"
SESSIONS_FILE = DATA_DIR / "sessions.jsonl"
MIN_ENTRY_SECONDS = 5 * 60  # work time entries shorter than this are not recorded


def snapshot_file(pid: int | None = None) -> Path:
    return DATA_DIR / f"current-{pid or os.getpid()}.json"


def keep_entries(segments: list[dict]) -> list[dict]:
    return [s for s in segments if s["end"] - s["start"] >= MIN_ENTRY_SECONDS]


def entry_names(title: str, segments: list[dict]) -> list[str]:
    """One entry: the title. Several: <title>_work_<n>, plus .<k> when a work was split by pauses."""
    if len(segments) == 1:
        return [title]
    per_work: dict[int, int] = {}
    for seg in segments:
        per_work[seg["work"]] = per_work.get(seg["work"], 0) + 1
    names, seen = [], {}
    for seg in segments:
        n = seg["work"]
        seen[n] = seen.get(n, 0) + 1
        names.append(f"{title}_work_{n}" + (f".{seen[n]}" if per_work[n] > 1 else ""))
    return names


def record_entries(segments: list[dict], title: str, description: str, profile: str) -> list[dict]:
    entries = [{"id": uuid.uuid4().hex, "start": seg["start"], "end": seg["end"], "title": name,
                "description": description, "profile": profile}
               for seg, name in zip(segments, entry_names(title, segments))]
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with SESSIONS_FILE.open("a") as f:
        f.writelines(json.dumps(e) + "\n" for e in entries)
    return entries


def ics_path(ics_dir: str, title: str, start: float) -> Path:
    """<ics_dir>/YYYY-MM-DD_HHMM_<title>.ics, with a numeric suffix if the name is taken."""
    slug = re.sub(r"[^\w.-]+", "_", title).strip("_.")[:60] or "pomo"
    base = Path(ics_dir).expanduser() / f"{datetime.fromtimestamp(start):%Y-%m-%d_%H%M}_{slug}"
    path, n = base.with_suffix(".ics"), 1
    while path.exists():
        n += 1
        path = Path(f"{base}-{n}.ics")
    return path


def write_cycle_ics(entries: list[dict], ics_dir: str, title: str) -> Path:
    path = ics_path(ics_dir, title, entries[0]["start"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_ics(entries), newline="")
    return path


def recover_snapshots() -> list[tuple[list[dict], str, str | None]]:
    """Collect the unrecorded work (segments, profile, ics_dir) left by pomo instances no longer running."""
    recovered = []
    for snap in DATA_DIR.glob("current-*.json"):
        try:
            pid = int(snap.stem.split("-", 1)[1])
            if pid != os.getpid():
                os.kill(pid, 0)
                continue  # that pomo is still running
        except ProcessLookupError:
            pass
        except (ValueError, PermissionError):
            continue
        try:
            data = json.loads(snap.read_text())
            cycle = list(data.get("cycle", []))
            if data.get("segment"):
                cycle.append({**data["segment"], "end": data["last_seen"]})
            recovered += [(kept, data.get("profile", ""), data.get("ics_dir"))
                          for segs in [*data.get("pending", []), cycle]
                          if (kept := keep_entries(segs))]
        except (OSError, ValueError, KeyError):
            pass
        snap.unlink(missing_ok=True)
    return recovered


def read_sessions() -> list[dict]:
    if not SESSIONS_FILE.exists():
        return []
    sessions = []
    for line in SESSIONS_FILE.read_text().splitlines():
        try:
            entry = json.loads(line)
            if "title" in entry:  # skip anything that is not a recorded time entry
                sessions.append(entry)
        except ValueError:
            pass  # a truncated line must not break the export
    return sessions


def ics_escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\n", "\\n"))


def ics_fold(line: str) -> str:
    """Fold a content line at 75 octets (RFC 5545) without splitting UTF-8 characters."""
    out, current, size = [], "", 0
    for char in line:
        n = len(char.encode())
        if size + n > 75:
            out.append(current)
            current, size = " ", 1  # continuation lines start with a space
        current += char
        size += n
    out.append(current)
    return "\r\n".join(out)


def ics_time(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_ics(entries: list[dict]) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//pomo//EN", "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH", "X-WR-CALNAME:Pomodoro"]
    stamp = ics_time(system.wall_time())
    for e in entries:
        lines += ["BEGIN:VEVENT",
                  f"UID:{e['id']}@pomo",  # stable: re-importing updates instead of duplicating
                  f"DTSTAMP:{stamp}",
                  f"DTSTART:{ics_time(e['start'])}",
                  f"DTEND:{ics_time(e['end'])}",
                  f"SUMMARY:{ics_escape(e['title'])}"]
        if e.get("description"):
            lines.append(f"DESCRIPTION:{ics_escape(e['description'])}")
        lines += ["CATEGORIES:Pomodoro", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "".join(ics_fold(line) + "\r\n" for line in lines)


def export_ics(target: str, since: date | None, until: date | None) -> None:
    def day(s: dict) -> date:
        return datetime.fromtimestamp(s["start"]).date()
    sessions = [s for s in read_sessions()
                if (since is None or day(s) >= since) and (until is None or day(s) <= until)]
    if not sessions:
        system.fail(_("no time entry to export ({file})", file=SESSIONS_FILE))
    ics = build_ics(sorted(sessions, key=lambda s: s["start"]))
    if target == "-":
        sys.stdout.write(ics)
    else:
        Path(target).write_text(ics, newline="")
        print(_("{n} time entry(ies) exported to {file}", n=len(sessions), file=target))
