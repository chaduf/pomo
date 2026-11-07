"""The Textual application: it shows the current mode, routes the keys to it and runs the side
effects it reports (hooks, notifications, time entries form, waybar state). Also its screens:
help, profile menu and time entries form."""
import asyncio
import json
import os
import signal
from datetime import datetime
from pathlib import Path

from rich.cells import cell_len
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Middle, Vertical
from textual.screen import ModalScreen
from textual.widgets import (Button, DataTable, Digits, Input, Label, OptionList, ProgressBar, Static,
                             TextArea)
from textual.widgets.option_list import Option

from . import i18n, system
from .config import CONFIG_FILE, ConfigError, load_config, resolve_settings
from .entries import (DATA_DIR, MIN_ENTRY_SECONDS, entry_names, ics_path, keep_entries, record_entries,
                      recover_snapshots, snapshot_file, write_cycle_ics)
from .i18n import _
from .modes import POMODORO, STOPWATCH, PomodoroEvents, PomodoroMode, StopwatchMode, TimerMode, View

SNAPSHOT_EVERY = 30  # seconds between saves of the unrecorded work (crash recovery)


class Pomo(App):
    CSS = """
    Screen { align: center middle; }
    #phase { text-style: bold; margin-bottom: 1; width: auto; }
    Digits { width: auto; }
    ProgressBar { margin-top: 1; }
    #info { color: $text-muted; margin-top: 1; width: auto; }
    .work #phase { color: $error; }
    .short #phase, .long #phase { color: $success; }
    .stopwatch #phase { color: $accent; }
    .paused Digits { color: $text-disabled; }
    #laps { width: auto; height: auto; max-height: 12; margin-top: 1; }
    #hints { dock: bottom; width: 100%; height: auto; padding: 0 1;
             background: $panel; color: $text-muted; text-align: center;
             link-style: none; link-color: $text-muted; link-background: transparent;
             link-style-hover: none; link-color-hover: $text; link-background-hover: $boost; }
    """

    def __init__(self, settings: dict, profile: str | None, no_hooks: bool, mode: str = POMODORO) -> None:
        super().__init__()
        self.hooks_enabled = not no_hooks  # toggled with c, kept across resets and switches
        self.settings = settings
        self.profile = profile
        self.pending: list[list[dict]] = []  # cycles waiting to be named in the form
        self.last_snapshot = 0.0
        self.timer = self.make_mode(mode)    # the current mode: the App only delegates to it

    def make_mode(self, name: str) -> TimerMode:
        """A fresh mode, with the current settings and profile."""
        if name == STOPWATCH:
            return StopwatchMode(system.monotonic)
        events = PomodoroEvents(
            hook=self.run_work_hook,
            announce=lambda title, body, icon: system.notify(title, body, icon, "critical"),
            notice=lambda message, severity: self.notify(message, severity=severity),
            work_changed=self.save_snapshot,
            cycle_complete=lambda: self.record_then(self.timer.take_cycle(), "complete"))
        return PomodoroMode(system.monotonic, system.wall_time, self.settings, self.profile, events)

    def compose(self) -> ComposeResult:
        with Middle():
            with Center():
                yield Label(id="phase")
            with Center():
                yield Digits(id="clock")
            with Center():
                yield ProgressBar(show_eta=False, show_percentage=False, id="bar")
            with Center():
                yield Label(id="info")
            with Center():
                yield DataTable(id="laps", show_cursor=False, zebra_stripes=True)
        yield Static(id="hints")

    def on_mount(self) -> None:
        self.title = "pomo"
        self.main_screen = self.screen  # the profile menu is pushed on top of it
        # mode specific keys go through mode_action(); add / subtract are the keypad + / -
        for key, action in (("space", "toggle"), ("r", "reset"), ("p", "profiles"), ("m", "mode"),
                            ("c", "hooks"), ("h,question_mark,f1", "help"), ("q", "quit"),
                            ("n", "mode_action('skip')"), ("l", "mode_action('lap')"),
                            ("plus,add", "mode_action('extend')"), ("minus,subtract", "mode_action('shorten')"),
                            ("greater_than_sign", "mode_action('add_cycle')"),
                            ("less_than_sign", "mode_action('remove_cycle')")):
            self.bind(key, action, show=False)  # labels are rendered by render_hints()
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGUSR1, self.action_toggle)  # waybar click
        loop.add_signal_handler(signal.SIGUSR2, self.skip)           # waybar right click
        laps = self.query_one("#laps", DataTable)
        laps.add_column(_("Lap"), key="n")
        laps.add_column(_("Lap time"), key="lap")
        laps.add_column(_("Total"), key="total")
        self.set_interval(0.1, self.tick)
        self.render_state()  # wait for "space" to start
        for segments, profile, ics_dir in recover_snapshots():
            self.ask_entries(segments, "recovered", profile=profile, ics_dir=ics_dir)

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        """Enable only the keys of the current mode."""
        if action == "mode_action":
            return parameters[0] in self.timer.actions
        if action == "hooks":
            return self.timer.uses_hooks
        if action == "profiles":
            return self.timer.uses_profiles
        return True

    def tick(self) -> None:
        if not self.is_running:
            return  # shutting down: the widgets are being removed, do not render them
        self.timer.tick()
        segment, _cycle = self.timer.unrecorded()
        if segment and system.monotonic() - self.last_snapshot >= SNAPSHOT_EVERY:
            self.save_snapshot()
        self.render_state()

    # ---- time entries --------------------------------------------------
    def save_snapshot(self) -> None:
        """Persist the unrecorded work so that a crash or a closed window loses nothing."""
        self.last_snapshot = system.monotonic()
        segment, cycle = self.timer.unrecorded()
        if not (segment or cycle or self.pending):
            snapshot_file().unlink(missing_ok=True)
            return
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        snapshot_file().write_text(json.dumps({"profile": self.profile or "", "ics_dir": self.settings["ics_dir"],
                                               "segment": segment, "cycle": cycle, "pending": self.pending,
                                               "last_seen": system.wall_time()}))

    def record_then(self, segments: list[dict], kind: str, then=None) -> None:
        """Ask for a title/description for the work segments worth recording, then call `then`.
        kind: "complete", "unfinished" (r, q, switch) or "recovered"."""
        segments = keep_entries(segments)
        if not segments:
            self.save_snapshot()
            if kind == "complete":
                self.notify(_("No work to record (entries under {minutes} min are ignored)",
                              minutes=MIN_ENTRY_SECONDS // 60))
            if then:
                then()
            return
        self.ask_entries(segments, kind, then)

    def ask_entries(self, segments: list[dict], kind: str, then=None,
                    profile: str | None = None, ics_dir: str | None = None) -> None:
        self.pending.append(segments)
        self.save_snapshot()
        # captured now: r / p / m change the settings once the form is closed
        profile = self.profile or "" if profile is None else profile
        ics_dir = ics_dir or self.settings["ics_dir"]

        def done(result: dict | None) -> None:
            if result is None:
                self.notify(_("Work discarded"))
            else:
                entries = record_entries(segments, result["title"], result["description"], profile)
                try:
                    path = write_cycle_ics(entries, ics_dir, result["title"])
                    self.notify(_("{n} time entry(ies) recorded in {file}", n=len(entries), file=path))
                except OSError as e:
                    self.notify(_("Time entries kept in the log, but {file} could not be written: {error}",
                                  file=ics_dir, error=e.strerror or e), severity="error", timeout=10)
            self.pending.remove(segments)
            self.save_snapshot()
            if then:
                then()

        self.push_screen(EntryForm(segments, kind, ics_dir), done)

    def leave_mode(self, reason: str, then) -> None:
        """Interrupt the mode (reason: reset|switch|quit), offer to record its work, then call `then`."""
        self.record_then(self.timer.interrupt(reason), "unfinished", then)
        self.render_state()

    # ---- actions -------------------------------------------------------
    def action_toggle(self) -> None:
        self.timer.toggle()
        self.render_state()

    def skip(self) -> None:
        """waybar right click: next phase, or a lap with the stopwatch."""
        self.timer.skip()
        self.render_state()

    def action_mode_action(self, name: str) -> None:
        self.timer.actions[name]()
        self.render_state()

    def action_reset(self) -> None:
        def reset() -> None:
            self.timer.reset()
            self.render_state()
        self.leave_mode("reset", reset)

    def action_mode(self) -> None:
        """Switch between pomodoro and stopwatch; the new mode starts fresh."""
        def switch() -> None:
            self.timer = self.make_mode(POMODORO if self.timer.name == STOPWATCH else STOPWATCH)
            self.refresh_bindings()
            self.render_state()
            self.notify(_("Stopwatch mode") if self.timer.name == STOPWATCH else _("Pomodoro mode"))
        self.leave_mode("switch", switch)

    def action_profiles(self) -> None:
        if isinstance(self.screen, ProfileMenu):
            return
        try:
            cfg = load_config()  # reread so profiles added since launch show up
            profiles = cfg.get("profiles", {})
            if not profiles:
                raise ConfigError(_("No profiles in {file}", file=CONFIG_FILE))
            entries = {name: resolve_settings(cfg, name) for name in profiles}
        except ConfigError as e:
            self.notify(str(e), severity="error")
            return

        def chosen(name: str | None) -> None:
            if name is None:
                return

            def load() -> None:
                self.settings, self.profile = entries[name], name
                self.timer = self.make_mode(self.timer.name)
                self.render_state()
                self.notify(_("Profile '{name}' loaded", name=name))
            self.leave_mode("switch", load)

        self.push_screen(ProfileMenu(entries, self.profile), chosen)

    async def action_quit(self) -> None:
        if isinstance(self.screen, EntryForm):
            return  # finish the form first
        self.leave_mode("quit", self.quit_now)

    def quit_now(self) -> None:
        system.STATE_FILE.unlink(missing_ok=True)
        system.refresh_waybar()
        self.exit()

    def action_help(self) -> None:
        if not isinstance(self.screen, (HelpScreen, EntryForm)):
            self.push_screen(HelpScreen(self.help_sections()))

    def help_sections(self) -> list[tuple[str, list[tuple[str, str]]]]:
        """Keys of the current mode, as (section title, [(keys, description)])."""
        timer, app = self.timer.help_rows()
        if self.timer.uses_hooks:
            app.append(("c", _("disable the hooks (currently on)") if self.hooks_enabled
                        else _("enable the hooks (currently off)")))
        app += [("? h F1", _("this help")), ("q", _("quit"))]
        return [(_("Timer"), timer), (_("App"), app)]

    def action_hooks(self) -> None:
        """Enable / disable the work start / end hooks; takes effect from the next event."""
        self.hooks_enabled = not self.hooks_enabled
        self.render_state()
        self.notify(_("Hooks enabled") if self.hooks_enabled else _("Hooks disabled"))

    def run_work_hook(self, which: str, env: dict) -> None:
        """which: start|end; env: the POMO_* variables of the event."""
        if self.hooks_enabled:
            system.run_hook(self.settings["on_work_start" if which == "start" else "on_work_end"], env)

    # ---- display -------------------------------------------------------
    def hint_rows(self) -> list[list[tuple[str, str, str]]]:
        """Key hints as (key, action, label) on a single line: the essential timer keys, then
        help and quit (every other key is listed in the help). Labels say what the key will do now."""
        timer = self.timer
        toggle = _("Start") if timer.idle else _("Pause") if timer.running else _("Resume")
        return [[("space", "toggle", toggle), *timer.hints(), ("r", "reset", _("Reset")),
                 ("?", "help", _("Help")), ("q", "quit", _("Quit"))]]

    def render_hints(self) -> None:
        """Render the hint rows, wrapping whole "key label" items to the terminal width."""
        width = max(self.size.width - 2, 20)  # minus the horizontal padding
        sep = "   "
        lines = []
        for row in self.hint_rows():
            line, used = [], 0
            for key, action, label in row:
                size = cell_len(f"{key} {label}")
                if line and used + len(sep) + size > width:
                    lines.append(line)
                    line, used = [], 0
                used += (len(sep) if line else 0) + size
                click = f"mode_action('{action}')" if action in self.timer.actions else action
                # the label is the clickable part: link styling would override the key color
                line.append(f"[b $accent]{key}[/] [@click=app.{click}]{label}[/]")
            lines.append(line)
        markup = "\n".join(sep.join(line) for line in lines)
        if markup != getattr(self, "_hints", None):
            self._hints = markup
            self.main_screen.query_one("#hints", Static).update(markup)

    def on_resize(self) -> None:
        if hasattr(self, "main_screen"):
            self.render_hints()

    def render_state(self) -> None:
        self.render_hints()
        view = self.timer.view()
        if self.timer.uses_hooks and not self.hooks_enabled:
            view.info += _("  ·  hooks off")
        self.render_view(view)
        self.write_state(*self.timer.waybar_state(system.wall_time()))

    def render_view(self, view: View) -> None:
        screen = self.main_screen
        screen.set_classes(view.classes)
        screen.query_one("#phase", Label).update(view.title)
        screen.query_one("#clock", Digits).update(view.clock)
        screen.query_one("#info", Label).update(view.info)
        bar = screen.query_one("#bar", ProgressBar)
        bar.display = view.progress is not None
        if view.progress is not None:
            done, total = view.progress
            bar.update(total=total, progress=done)
        table = screen.query_one("#laps", DataTable)
        table.display = view.laps is not None
        if (view.laps or []) != getattr(self, "_lap_rows", []):  # rebuild only when laps change
            self._lap_rows = view.laps or []
            table.clear()
            for n, lap, style, total in self._lap_rows:
                table.add_row(n, Text(lap, style=style), total)

    def write_state(self, data: dict, key: tuple, tick: int) -> None:
        """Write the waybar state file when the displayed second changes;
        signal waybar right away only when `key` (mode, phase, running...) changes."""
        old = getattr(self, "_last_state", None)
        if old != (key, tick):
            tmp = system.STATE_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps({"pid": os.getpid(), "lang": i18n.lang, **data}))
            tmp.replace(system.STATE_FILE)
            if old is None or old[0] != key:
                system.refresh_waybar()
            self._last_state = (key, tick)

class HelpScreen(ModalScreen[None]):
    """Lists the keys of the current mode; closed with Esc, q or the help keys."""

    CSS = """
    HelpScreen { align: center middle; }
    #help { width: 84; max-width: 95%; height: auto; max-height: 100%; overflow-y: auto;
            padding: 0 2; border: round $accent; background: $surface; }
    #help-title { text-style: bold; margin: 1 0; }
    .help-section { text-style: bold; color: $text-muted; }
    .help-keys { margin-bottom: 1; }
    #help-note, #help-close { color: $text-muted; width: 100%; }
    #help-close { margin-bottom: 1; }
    """
    BINDINGS = [Binding("escape,q,question_mark,h,f1", "dismiss(None)", show=False)]

    def __init__(self, sections: list[tuple[str, list[tuple[str, str]]]]) -> None:
        super().__init__()
        self.sections = sections

    def compose(self) -> ComposeResult:
        width = max(len(keys) for _title, rows in self.sections for keys, _desc in rows) + 3
        with Vertical(id="help"):
            yield Label(_("Keys"), id="help-title")
            for title, rows in self.sections:
                yield Label(title, classes="help-section")
                text = Text()
                for i, (keys, desc) in enumerate(rows):
                    text.append(("\n" if i else "") + keys.ljust(width), style="bold")
                    text.append(desc)
                yield Static(text, classes="help-keys")
            yield Label(_("Work time is recorded at the end of each cycle (title asked in a form)."), id="help-note")
            yield Label(_("Esc, q or ?: close"), id="help-close")


class ProfileList(OptionList):
    BINDINGS = [
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
    ]


class ProfileMenu(ModalScreen[str | None]):
    """Profile picker: returns the chosen profile name, or None if cancelled."""

    CSS = """
    ProfileMenu { align: center middle; }
    #menu { width: auto; max-width: 90%; height: auto; padding: 1 2;
            border: round $accent; background: $surface; }
    #menu-title { text-style: bold; margin-bottom: 1; }
    ProfileList { width: auto; height: auto; max-height: 20; border: none; }
    #menu-help { color: $text-muted; margin-top: 1; }
    """
    BINDINGS = [Binding("escape", "dismiss(None)", show=False)]

    def __init__(self, entries: dict[str, dict], current: str | None) -> None:
        super().__init__()
        self.entries = entries
        self.current = current

    def compose(self) -> ComposeResult:
        options = [
            Option(f"{'●' if name == self.current else ' '} {name:<12} " + _(
                "work {work} min · break {short} min · long break {long} min · {cycles} cycles",
                work=v["work"], short=v["short_break"], long=v["long_break"], cycles=v["cycles"]), id=name)
            for name, v in self.entries.items()
        ]
        with Vertical(id="menu"):
            yield Label(_("Choose a profile"), id="menu-title")
            yield ProfileList(*options)
            yield Label(_("↑↓ / j k: move · Enter: select · Esc: cancel"), id="menu-help")

    def on_mount(self) -> None:
        menu = self.query_one(ProfileList)
        names = list(self.entries)
        menu.highlighted = names.index(self.current) if self.current in names else 0
        menu.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)


class EntryForm(ModalScreen[dict | None]):
    """Names the work time entries of a cycle: returns {title, description}, or None to discard."""

    CSS = """
    EntryForm { align: center middle; }
    #form { width: 80; max-width: 95%; height: auto; max-height: 100%; overflow-y: auto;
            padding: 0 2; border: round $accent; background: $surface; }
    #form-title { text-style: bold; margin-bottom: 1; }
    #preview { color: $text-muted; margin-bottom: 1; }
    #form Input { margin-bottom: 1; }
    #desc { height: 4; }
    #error { color: $error; }
    #buttons { height: auto; align-horizontal: right; margin-top: 1; }
    #buttons Button { margin-left: 2; }
    #form-help { color: $text-muted; margin-top: 1; }
    #form-title { margin-top: 1; }
    """
    BINDINGS = [Binding("ctrl+s", "save", show=False)]
    HEADINGS = {
        "complete": "Cycle complete: record your work",
        "unfinished": "Unfinished cycle: record your work",
        "recovered": "Unrecorded work from a previous session",
    }

    def __init__(self, segments: list[dict], kind: str, ics_dir: str) -> None:
        super().__init__()
        self.segments = segments
        self.kind = kind
        self.ics_dir = ics_dir

    def compose(self) -> ComposeResult:
        with Vertical(id="form"):
            yield Label(_(self.HEADINGS[self.kind]), id="form-title")
            yield Static(id="preview")
            yield Label(_("Title (required)"))
            yield Input(id="title")
            yield Label(_("Description (optional)"))
            yield TextArea(id="desc", soft_wrap=True)
            yield Label(id="error")
            with Horizontal(id="buttons"):
                yield Button(_("Discard"), id="discard", variant="error", compact=True)
                yield Button(_("Save"), id="save", variant="primary", compact=True)
            yield Label(_("Enter: next field · Ctrl+S: save"), id="form-help")

    def on_mount(self) -> None:
        self.render_preview("")
        self.query_one("#title", Input).focus()

    def render_preview(self, title: str) -> None:
        """List the entries as they will be named, updated while the title is typed."""
        lines = []
        for seg, name in zip(self.segments, entry_names(title or "…", self.segments)):
            start, end = datetime.fromtimestamp(seg["start"]), datetime.fromtimestamp(seg["end"])
            minutes = round((seg["end"] - seg["start"]) / 60)
            lines.append(f"• {name}   {start:%H:%M}–{end:%H:%M}  ({minutes} min)")
        start = self.segments[0]["start"]
        target = (ics_path(self.ics_dir, title, start) if title else
                  Path(self.ics_dir).expanduser() / f"{datetime.fromtimestamp(start):%Y-%m-%d_%H%M}_….ics")
        home = str(Path.home())
        lines.append(_("Calendar file: {file}", file=str(target).replace(home, "~", 1)))
        self.query_one("#preview", Static).update(Text("\n".join(lines)))

    def on_input_changed(self, event: Input.Changed) -> None:
        self.render_preview(event.value.strip())
        self.query_one("#error", Label).update("")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.query_one("#desc", TextArea).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self.action_save()
        else:
            self.dismiss(None)

    def action_save(self) -> None:
        title = self.query_one("#title", Input).value.strip()
        if not title:
            self.query_one("#error", Label).update(_("The title is required"))
            self.query_one("#title", Input).focus()
            return
        self.dismiss({"title": title, "description": self.query_one("#desc", TextArea).text.strip()})

