"""pomo — Pomodoro TUI that runs commands when work periods start and end
(default: pause/resume the media players that are playing, through pomo-media), sends desktop
notifications and exposes its state to waybar. Also has a stopwatch mode with laps.

Config:  ~/.config/pomo/config.toml  (pomo -L to list profiles, pomo -p NAME)
Hooks:   on_work_start / on_work_end (config) or --on-work-start / --on-work-end (CLI)
Keys:    press ? in the app (space, n, r, + / -, > / <, p, m, c, l, q)
Signals: SIGUSR1 = pause/resume, SIGUSR2 = next phase or lap (used by waybar)
UI language: --lang, $POMO_LANG, `language` in config, then the system locale.
Entries: at the end of each cycle, pomo asks for a title and description, logs the work time
         entries to ~/.local/share/pomo/sessions.jsonl and writes them as .ics;
         pomo --export-ics [FILE] exports them all as one iCalendar file.

This module parses the command line and starts the app."""
import argparse
import os
from datetime import date

from . import i18n, system
from .app import Pomo
from .config import CONFIG_FILE, DEFAULTS, ConfigError, load_config, resolve_settings
from .entries import export_ics
from .i18n import LANGUAGES, _, resolve_language
from .modes import POMODORO, STOPWATCH


def positive_int(v: str) -> int:
    n = int(v)
    if n <= 0:
        raise argparse.ArgumentTypeError(_("must be an integer > 0"))
    return n


def iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(_("invalid date: {value} (expected YYYY-MM-DD)", value=value))


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=_("Pomodoro TUI: runs commands when work starts/ends (pauses/resumes media by default)"),
        epilog=_("Config: {file}. Precedence: defaults < [hooks] < profile < CLI options. "
                 "Hooks receive POMO_EVENT (start|resume|end|pause|quit|switch|reset), POMO_PROFILE, "
                 "POMO_DONE, POMO_CYCLES, POMO_WORK_MIN.", file=CONFIG_FILE),
    )
    ap.add_argument("-p", "--profile", help=_("profile to use (default: default_profile from the config file)"))
    ap.add_argument("-L", "--list", action="store_true", help=_("list profiles and exit"))
    ap.add_argument("-w", "--work", type=positive_int, help=_("work minutes ({default})", default=DEFAULTS["work"]))
    ap.add_argument("-s", "--short-break", type=positive_int,
                    help=_("short break minutes ({default})", default=DEFAULTS["short_break"]))
    ap.add_argument("-l", "--long-break", type=positive_int,
                    help=_("long break minutes ({default})", default=DEFAULTS["long_break"]))
    ap.add_argument("-c", "--cycles", type=positive_int,
                    help=_("work sessions before the long break ({default})", default=DEFAULTS["cycles"]))
    ap.add_argument("--on-work-start", metavar="CMD",
                    help=_("command run when work starts (\"{default}\")", default=DEFAULTS["on_work_start"]))
    ap.add_argument("--ics-dir", metavar="DIR",
                    help=_("directory for the .ics file written at the end of each cycle ({default})",
                           default=DEFAULTS["ics_dir"]))
    ap.add_argument("--on-work-end", metavar="CMD",
                    help=_("command run when work ends (\"{default}\")", default=DEFAULTS["on_work_end"]))
    ap.add_argument("--no-hooks", action="store_true",
                    help=_("start with the hooks disabled (c toggles them in the app)"))
    ap.add_argument("--stopwatch", action="store_true", help=_("start in stopwatch mode"))
    ap.add_argument("--export-ics", nargs="?", const="pomo-sessions.ics", metavar="FILE",
                    help=_("export the recorded time entries as an iCalendar (.ics) file (default: {file}, - for stdout)",
                           file="pomo-sessions.ics"))
    ap.add_argument("--since", type=iso_date, metavar="DATE",
                    help=_("with --export-ics: only entries on or after DATE (YYYY-MM-DD)"))
    ap.add_argument("--until", type=iso_date, metavar="DATE",
                    help=_("with --export-ics: only entries on or before DATE (YYYY-MM-DD)"))
    ap.add_argument("--lang", choices=("auto", *LANGUAGES),
                    help=_("UI language: {langs} (default: auto)", langs=", ".join(LANGUAGES)))
    return ap


def main(bin_dir: str = "") -> None:
    """Entry point; `bin_dir` is the directory of the launcher (and of pomo-media)."""
    system.BIN_DIR = bin_dir
    # The language must be known before building translated help texts.
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--lang")
    cli_lang = pre.parse_known_args()[0].lang
    i18n.lang = resolve_language(cli_lang, os.environ.get("POMO_LANG"))
    try:
        cfg = load_config()
    except ConfigError as e:
        system.fail(str(e))
    i18n.lang = resolve_language(cli_lang, os.environ.get("POMO_LANG"), cfg.get("language"))

    args = build_parser().parse_args()
    try:
        run(args, cfg)
    except ConfigError as e:
        system.fail(str(e))


def run(args: argparse.Namespace, cfg: dict) -> None:
    profiles, default_profile = cfg.get("profiles", {}), cfg.get("default_profile")

    if args.export_ics:
        export_ics(args.export_ics, args.since, args.until)
        return

    if args.list:
        if not profiles:
            print(_("No profiles ({file})", file=CONFIG_FILE))
        for name in profiles:
            v = resolve_settings(cfg, name)
            mark = "*" if name == default_profile else " "
            print(f"{mark} {name:<12} " + _(
                "work {work} min · break {short} min · long break {long} min · {cycles} cycles",
                work=v["work"], short=v["short_break"], long=v["long_break"], cycles=v["cycles"]))
            print(f"  {'':<12} " + _("start: {start}  ·  end: {end}",
                                     start=v["on_work_start"] or _("(nothing)"),
                                     end=v["on_work_end"] or _("(nothing)")))
            print(f"  {'':<12} " + _("ics files: {dir}", dir=v["ics_dir"]))
        return

    name = args.profile or default_profile
    settings = resolve_settings(cfg, name)
    for key in DEFAULTS:  # explicit CLI options win
        if getattr(args, key) is not None:
            settings[key] = getattr(args, key)

    app = Pomo(settings, name, args.no_hooks, STOPWATCH if args.stopwatch else POMODORO)
    try:
        app.run()
    finally:
        app.save_snapshot()  # unrecorded work stays in the snapshot for the next launch
        system.STATE_FILE.unlink(missing_ok=True)
        system.refresh_waybar()