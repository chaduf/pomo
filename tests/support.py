"""Test helpers: load bin/pomo as a module in an isolated environment and drive its TUI.

The tests only look at what pomo shows or does (widgets, notifications, hooks run, waybar
state file, recorded entries), never at its internal attributes, so they keep working when
the code behind them is reorganised.
"""
import contextlib
import importlib.machinery
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POMO = ROOT / "bin" / "pomo"
XDG_VARS = ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_RUNTIME_DIR")


class FakeClock:
    """Replaces the `time` module inside pomo: wall clock and monotonic clock advance together."""

    def __init__(self) -> None:
        self.wall = 1_800_000_000.0  # a fixed date, so that entry names and files are stable
        self.mono = 1000.0

    def time(self) -> float:
        return self.wall

    def monotonic(self) -> float:
        return self.mono

    def advance(self, seconds: float) -> None:
        self.wall += seconds
        self.mono += seconds


def load_pomo(base: Path):
    """Import bin/pomo with its config, data and runtime directories inside `base`."""
    for var in XDG_VARS:
        path = base / var.lower()
        path.mkdir()
        os.environ[var] = str(path)
    loader = importlib.machinery.SourceFileLoader("pomo_under_test", str(POMO))
    spec = importlib.util.spec_from_loader("pomo_under_test", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class ModeTestCase(unittest.TestCase):
    """Base class for testing the mode objects directly, without Textual: a fresh pomo module
    and a fake clock (`self.clock.mono` / `self.clock.wall`) per test."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.saved_env = {var: os.environ.get(var) for var in XDG_VARS}
        self.pomo = load_pomo(Path(self.tmp.name))
        self.pomo.lang = "en"
        self.clock = FakeClock()

    def tearDown(self) -> None:
        for var, value in self.saved_env.items():
            if value is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = value
        self.tmp.cleanup()


class PomoTestCase(unittest.IsolatedAsyncioTestCase):
    """Base class: a fresh pomo module per test, a fake clock and recorded side effects."""

    WORK_START = "work-start-hook"
    WORK_END = "work-end-hook"

    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.saved_env = {var: os.environ.get(var) for var in XDG_VARS}
        self.pomo = load_pomo(self.base)
        self.pomo.lang = "en"
        self.clock = FakeClock()
        self.pomo.time = self.clock
        self.hooks_run: list[tuple[str, dict]] = []  # (command, environment)
        self.desktop_notifications: list[str] = []   # titles sent to notify-send
        self.pomo.run_hook = lambda cmd, env: self.hooks_run.append((cmd, env))
        self.pomo.notify = lambda title, body, *a, **k: self.desktop_notifications.append(title)
        self.pomo.refresh_waybar = lambda: None
        self.ics_dir = self.base / "ics"

    async def asyncTearDown(self) -> None:
        for var, value in self.saved_env.items():
            if value is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = value
        self.tmp.cleanup()

    # ---- running the app -------------------------------------------------
    def settings(self, **overrides) -> dict:
        return {**self.pomo.DEFAULTS, "on_work_start": self.WORK_START, "on_work_end": self.WORK_END,
                "ics_dir": str(self.ics_dir), **overrides}

    @contextlib.asynccontextmanager
    async def run_app(self, *, profile: str | None = "classic", no_hooks: bool = False,
                      stopwatch: bool = False, size=(110, 40), **overrides):
        mode = self.pomo.STOPWATCH if stopwatch else self.pomo.POMODORO
        app = self.pomo.Pomo(self.settings(**overrides), profile, no_hooks, mode)
        async with app.run_test(size=size) as pilot:
            self.app, self.pilot = app, pilot
            await pilot.pause(0.2)
            yield app

    async def press(self, *keys: str) -> None:
        await self.pilot.press(*keys)
        await self.pilot.pause(0.25)

    async def advance(self, seconds: float) -> None:
        """Let `seconds` pass on the fake clock, then let pomo's timer tick."""
        self.clock.advance(seconds)
        await self.pilot.pause(0.3)

    # ---- what pomo shows or does -----------------------------------------
    def widget_text(self, selector: str) -> str:
        return str(self.app.main_screen.query_one(selector).render())

    def clock_text(self) -> str:
        return self.app.main_screen.query_one("#clock").value

    def phase_text(self) -> str:
        return self.widget_text("#phase")

    def info_text(self) -> str:
        return self.widget_text("#info")

    def hints_text(self) -> str:
        hints = self.app.main_screen.query_one("#hints")
        return " / ".join(hints.render_line(y).text.strip() for y in range(hints.size.height))

    def screen_name(self) -> str:
        return type(self.app.screen).__name__

    def notifications(self) -> list[str]:
        return [n.message for n in self.app._notifications]

    def hook_events(self) -> list[tuple[str, str]]:
        """Hooks run so far, as (start|end, POMO_EVENT)."""
        which = {self.WORK_START: "start", self.WORK_END: "end"}
        return [(which[cmd], env["POMO_EVENT"]) for cmd, env in self.hooks_run]

    def waybar_state(self) -> dict | None:
        path = self.pomo.STATE_FILE
        return json.loads(path.read_text()) if path.exists() else None

    def recorded_entries(self) -> list[dict]:
        path = self.pomo.SESSIONS_FILE
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def lap_rows(self) -> list[tuple[str, str, str, str]]:
        """Lap table rows as (lap, lap time, lap time style, total), newest first."""
        table = self.app.main_screen.query_one("#laps")
        rows = []
        for r in range(table.row_count):
            n, lap, total = table.get_row_at(r)
            rows.append((str(n), lap.plain, str(lap.style or ""), str(total)))
        return rows
