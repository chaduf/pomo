"""Timer modes: the pomodoro and the stopwatch, behind a common interface (TimerMode).

A mode holds the timer logic, without any Textual or system call: it gets the time from the
clocks it is given, describes the screen as a View and reports its side effects (pomodoro)
through PomodoroEvents. The App delegates to the current mode instead of testing which
mode it is."""
from collections.abc import Callable
from dataclasses import dataclass

from .i18n import _

POMODORO, STOPWATCH = "pomodoro", "stopwatch"
WORK, SHORT, LONG = "work", "short", "long"
ICONS = {WORK: "🍅", SHORT: "☕", LONG: "🌴", STOPWATCH: "⏱"}
EXTEND_MINUTES = 5  # added to / removed from the current pomodoro phase by the + / - keys


def format_elapsed(seconds: float) -> str:
    """MM:SS.d below one hour, H:MM:SS.d above."""
    tenths = int(seconds * 10)
    h, rest = divmod(tenths, 36000)
    m, rest = divmod(rest, 600)
    sec, d = divmod(rest, 10)
    return f"{h}:{m:02d}:{sec:02d}.{d}" if h else f"{m:02d}:{sec:02d}.{d}"


def phase_label(phase: str) -> str:
    return _({WORK: "Work", SHORT: "Short break", LONG: "Long break"}[phase])


@dataclass
class View:
    """What the main screen shows for a mode; the App turns it into widgets."""
    classes: list[str]                            # screen CSS classes (phase, paused...)
    title: str                                    # phase line, e.g. "🍅  Work (paused)"
    clock: str
    info: str
    progress: tuple[float, float] | None = None  # (done, total) for the progress bar; None hides it
    laps: list[tuple[str, str, str, str]] | None = None  # lap table rows; None hides the table


class TimerMode:
    """Interface shared by the modes. `clock` returns the current monotonic time."""

    name = ""
    uses_hooks = False     # the work start / end hooks (c toggles them) apply to this mode
    uses_profiles = False  # p switches profile in this mode

    def __init__(self, clock: Callable[[], float]) -> None:
        self.clock = clock
        self.running = False
        # mode specific actions (action name -> method), on top of toggle / skip / reset
        self.actions: dict[str, Callable[[], None]] = {}

    @property
    def idle(self) -> bool:
        """Not started yet: the space key starts rather than resumes."""
        raise NotImplementedError

    def tick(self) -> None:
        raise NotImplementedError

    def toggle(self) -> None:
        raise NotImplementedError

    def skip(self) -> None:
        """n in the TUI, right click in waybar."""
        raise NotImplementedError

    def reset(self) -> None:
        raise NotImplementedError

    def interrupt(self, reason: str) -> list[dict]:
        """Stop before a reset, a profile or mode switch or quitting (reason: reset|switch|quit);
        return the work segments of the current cycle that may be recorded."""
        return []

    def unrecorded(self) -> tuple[dict | None, list[dict]]:
        """(open work segment, finished segments of the cycle), saved against crashes."""
        return None, []

    def view(self) -> View:
        raise NotImplementedError

    def waybar_state(self, wall_time: float) -> tuple[dict, tuple, int]:
        """(state written for waybar, key whose change signals waybar, displayed second)."""
        raise NotImplementedError

    def hints(self) -> list[tuple[str, str, str]]:
        """Footer hints of the mode, as (key, action, label), between space and r."""
        raise NotImplementedError

    def help_rows(self) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        """(timer keys, app keys) of the mode for the help screen, as (keys, description)."""
        raise NotImplementedError


class StopwatchMode(TimerMode):
    name = STOPWATCH

    def __init__(self, clock: Callable[[], float]) -> None:
        super().__init__(clock)
        self.actions = {"lap": self.lap}
        self.reset()

    def update(self) -> None:
        """Add the time elapsed since the last update."""
        now = self.clock()
        if self.running:
            self.elapsed += now - self.last
        self.last = now

    @property
    def idle(self) -> bool:
        return not self.running and self.elapsed == 0

    def tick(self) -> None:
        self.update()

    def toggle(self) -> None:
        self.update()
        self.running = not self.running

    def lap(self) -> None:
        if self.running:
            self.update()
            self.laps.append(self.elapsed)

    def skip(self) -> None:
        self.lap()

    def reset(self) -> None:
        self.running = False
        self.elapsed = 0.0
        self.laps: list[float] = []  # total elapsed time at each lap
        self.last = self.clock()

    def lap_rows(self) -> list[tuple[str, str, str, str]]:
        """(lap, lap time, style, total), newest first; fastest lap green, slowest red."""
        splits = [t - (self.laps[i - 1] if i else 0.0) for i, t in enumerate(self.laps)]
        best = splits.index(min(splits)) if len(splits) > 1 else None
        worst = splits.index(max(splits)) if len(splits) > 1 else None
        return [(str(i + 1), format_elapsed(splits[i]),
                 "green" if i == best else "red" if i == worst else "", format_elapsed(self.laps[i]))
                for i in reversed(range(len(splits)))]

    def view(self) -> View:
        state = "" if self.running else _(" (paused)")
        return View(classes=[STOPWATCH] + ([] if self.running else ["paused"]),
                    title=f"{ICONS[STOPWATCH]}  {_('Stopwatch')}{state}",
                    clock=format_elapsed(self.elapsed),
                    info=_("Laps: {n}", n=len(self.laps)),
                    laps=self.lap_rows() or None)

    def waybar_state(self, wall_time: float) -> tuple[dict, tuple, int]:
        secs = int(self.elapsed)
        return ({"mode": STOPWATCH, "running": self.running, "elapsed": secs,
                 "laps": len(self.laps), "since": wall_time},
                (STOPWATCH, self.running, len(self.laps)), secs)

    def hints(self) -> list[tuple[str, str, str]]:
        return [("l", "lap", _("Lap"))]

    def help_rows(self) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        return ([("space", _("start / pause / resume")), ("l", _("record a lap")),
                 ("r", _("reset the time and laps"))],
                [("m", _("switch to the pomodoro"))])


@dataclass
class PomodoroEvents:
    """What a PomodoroMode reports; the App runs the side effects. All default to no-ops."""
    hook: Callable[[str, dict], None] = lambda which, env: None                 # start|end, hook env
    announce: Callable[[str, str, str], None] = lambda title, body, icon: None  # desktop notification
    notice: Callable[[str, str], None] = lambda message, severity: None         # in-app message
    work_changed: Callable[[], None] = lambda: None                             # unrecorded work changed
    cycle_complete: Callable[[], None] = lambda: None                           # the long break started


class PomodoroMode(TimerMode):
    name = POMODORO
    uses_hooks = True
    uses_profiles = True

    def __init__(self, clock: Callable[[], float], wall_clock: Callable[[], float], settings: dict,
                 profile: str | None, events: PomodoroEvents | None = None) -> None:
        super().__init__(clock)
        self.wall_clock = wall_clock  # wall time, for the time entries
        self.settings = settings
        self.profile = profile
        self.events = events or PomodoroEvents()
        self.actions = {"skip": self.skip, "extend": self.extend, "shorten": self.shorten,
                        "add_cycle": self.add_cycle, "remove_cycle": self.remove_cycle}
        self.reset()

    def reset(self) -> None:
        """Back to the freshly launched state: work, counters at zero, timer stopped."""
        s = self.settings
        self.durations = {WORK: s["work"] * 60, SHORT: s["short_break"] * 60, LONG: s["long_break"] * 60}
        self.cycles = s["cycles"]
        self.phase = WORK
        self.done_pomodoros = 0
        self.cycle_done = 0       # work sessions done in the current cycle (> / < change self.cycles)
        self.remaining = float(self.durations[WORK])
        self.phase_total = self.durations[WORK]  # length of the current phase, + extends it
        self.running = False
        self.started = False      # the first "space" is a start, not a resume
        self.last = self.clock()
        self.segment: dict | None = None  # the stretch of work in progress
        self.cycle: list[dict] = []        # finished segments of the current cycle

    @property
    def idle(self) -> bool:
        return not self.running and not self.started

    # ---- side effects, reported to the App
    def hook(self, which: str, event: str) -> None:
        """which: start|end; event: start|resume (start) or end|pause|quit|switch|reset (end)."""
        self.events.hook(which, {
            "POMO_EVENT": event, "POMO_PROFILE": self.profile or "",
            "POMO_DONE": str(self.done_pomodoros), "POMO_CYCLES": str(self.cycles),
            "POMO_WORK_MIN": str(self.durations[WORK] // 60),
        })

    def open_segment(self) -> None:
        if self.phase == WORK and self.running and self.segment is None:
            self.segment = {"work": self.cycle_done + 1, "start": self.wall_clock()}
            self.events.work_changed()

    def close_segment(self) -> None:
        if self.segment:
            self.cycle.append({**self.segment, "end": self.wall_clock()})
            self.segment = None
            self.events.work_changed()

    def take_cycle(self) -> list[dict]:
        """Hand over the finished segments of the cycle, to be recorded."""
        segments, self.cycle = self.cycle, []
        self.events.work_changed()
        return segments

    def unrecorded(self) -> tuple[dict | None, list[dict]]:
        return self.segment, self.cycle

    # ---- timer
    def start_phase(self, phase: str) -> None:
        leaving_work = self.phase == WORK and self.running
        self.phase = phase
        self.remaining = float(self.durations[phase])
        self.phase_total = self.durations[phase]
        self.running = True
        self.started = True
        self.last = self.clock()
        if phase == WORK:
            self.open_segment()
            self.hook("start", "start")
            self.events.announce(f"{ICONS[WORK]} {_('Back to work!')}",
                                 _("Session {n}/{total} — {minutes} min", n=self.cycle_done + 1,
                                   total=self.cycles, minutes=self.durations[WORK] // 60),
                                 "appointment-soon")
        else:
            if leaving_work:
                self.hook("end", "end")
            self.events.announce(f"{ICONS[phase]} {phase_label(phase)}",
                                 _("{minutes} min break — {done} pomodoro(s) done",
                                   minutes=self.durations[phase] // 60, done=self.done_pomodoros),
                                 "face-smile")

    def next_phase(self) -> None:
        if self.phase != WORK:
            self.start_phase(WORK)
            return
        self.close_segment()  # n during work cuts the entry short
        self.done_pomodoros += 1
        self.cycle_done += 1
        if self.cycle_done < self.cycles:
            self.start_phase(SHORT)
            return
        self.cycle_done = 0  # the long break opens the next cycle
        self.start_phase(LONG)
        self.events.cycle_complete()

    def tick(self) -> None:
        now = self.clock()
        if self.running:
            self.remaining -= now - self.last
        self.last = now
        if self.running and self.remaining <= 0:
            self.next_phase()

    def toggle(self) -> None:
        self.running = not self.running
        self.last = self.clock()
        if self.phase == WORK:
            if self.running:
                self.open_segment()
                self.hook("start", "resume" if self.started else "start")
            else:
                self.close_segment()  # a timer pause splits the entry
                self.hook("end", "pause")
        self.started = True

    def skip(self) -> None:
        self.next_phase()

    def interrupt(self, reason: str) -> list[dict]:
        if self.phase == WORK and self.running:
            self.hook("end", reason)
        self.close_segment()
        self.running = False
        return self.take_cycle()

    # ---- mode specific actions
    def extend(self) -> None:
        self.remaining += EXTEND_MINUTES * 60
        self.phase_total += EXTEND_MINUTES * 60
        self.events.notice(_("{phase}: +{minutes} min", phase=phase_label(self.phase),
                             minutes=EXTEND_MINUTES), "information")

    def shorten(self) -> None:
        """Remove 5 min from the current phase; with 5 min or less left, end it like n."""
        if self.remaining <= EXTEND_MINUTES * 60:
            self.next_phase()
            return
        self.remaining -= EXTEND_MINUTES * 60
        self.phase_total -= EXTEND_MINUTES * 60
        self.events.notice(_("{phase}: -{minutes} min", phase=phase_label(self.phase),
                             minutes=EXTEND_MINUTES), "information")

    def add_cycle(self) -> None:
        self.cycles += 1
        self.events.notice(_("Cycle: {n} work session(s) before the long break", n=self.cycles),
                           "information")

    def remove_cycle(self) -> None:
        """Remove a work session from the cycle, never below the current (or next) one."""
        minimum = self.cycle_done + 1
        if self.cycles <= minimum:
            self.events.notice(_("Cannot remove: this cycle needs at least {n} work session(s)",
                                 n=minimum), "warning")
            return
        self.cycles -= 1
        self.events.notice(_("Cycle: {n} work session(s) before the long break", n=self.cycles),
                           "information")

    # ---- display
    def seconds_left(self) -> int:
        return max(0, int(self.remaining + 0.999))

    def view(self) -> View:
        secs = self.seconds_left()
        mm, ss = divmod(secs, 60)
        state = "" if self.running else _(" (paused)")
        return View(classes=[self.phase] + ([] if self.running else ["paused"]),
                    title=f"{ICONS[self.phase]}  {phase_label(self.phase)}{state}",
                    clock=f"{mm:02d}:{ss:02d}",
                    info=(_("Profile: {name}  ·  ", name=self.profile) if self.profile else "")
                    + _("Pomodoros: {done}  ·  cycle {n}/{total}", done=self.done_pomodoros,
                        n=self.cycle_done + 1, total=self.cycles),
                    progress=(self.phase_total - secs, self.phase_total))

    def waybar_state(self, wall_time: float) -> tuple[dict, tuple, int]:
        secs = self.seconds_left()
        return ({"mode": POMODORO, "phase": self.phase, "running": self.running,
                 "remaining": secs, "total": self.phase_total, "done": self.done_pomodoros,
                 # end timestamp: waybar can count down without waiting for the TUI
                 "ends_at": wall_time + secs if self.running else None},
                (self.phase, self.running, self.done_pomodoros, self.phase_total), secs)

    def hints(self) -> list[tuple[str, str, str]]:
        return [("n", "skip", _("Next phase"))]

    def help_rows(self) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        return ([("space", _("start / pause / resume")), ("n", _("next phase (ends the current one)")),
                 ("+", _("add {minutes} min to the current phase", minutes=EXTEND_MINUTES)),
                 ("-", _("remove {minutes} min (ends the phase when {minutes} min or less remain)",
                         minutes=EXTEND_MINUTES)),
                 (">", _("add a work session to the cycle (the long break comes later)")),
                 ("<", _("remove a work session from the cycle (never below the current one)")),
                 ("r", _("full reset: back to work, counters at zero"))],
                [("p", _("switch profile")), ("m", _("switch to the stopwatch"))])

