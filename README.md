# pomo

Pomodoro TUI (Textual) that runs commands when work periods start and end
(default: play/pause mpv through MPRIS), sends desktop notifications and shows up in waybar.

Dependencies: `python-textual`, `libnotify`, `waybar`; for the default hooks: `mpv`, `mpv-mpris`, `playerctl`.

## Installation

```bash
./install.sh               # install (offers to install missing dependencies with pacman)
./install.sh --link        # symlinks to this directory (edits here take effect immediately)
./install.sh --no-waybar   # skip the waybar integration
./install.sh --force       # also overwrite an existing config.toml and waybar style
./install.sh --uninstall   # uninstall (~/.config/pomo is kept)
```

Without `--force`, an existing `config.toml` is never touched. `style.css` is backed up as
`*.bak-pomo` before being modified, and the script can be rerun safely without creating duplicates.

> **⚠ Required manual step: the waybar bar config.**
> The script **never modifies** the waybar bar file (`~/.config/waybar/bars/top-bar.jsonc`,
> or `~/.config/waybar/config.jsonc` depending on your setup). It installs the module, but
> adding it to the bar is up to you:
>
> 1. add the module to `include`:
>    ```jsonc
>    "include": [
>      ...
>      "~/.config/waybar/modules/custom-pomo.jsonc",
>    ],
>    ```
> 2. put `"custom/pomo"` wherever you like in `modules-left`, `modules-center` or `modules-right`:
>    ```jsonc
>    "modules-center": ["custom/music", "custom/pomo"],
>    ```
> 3. reload waybar: `pkill -SIGUSR2 waybar`
>
> When uninstalling, remove those two lines manually the same way.

### Manual installation

| Project file                         | Destination                                      |
|--------------------------------------|--------------------------------------------------|
| `bin/pomo`                           | `~/.local/bin/pomo`                              |
| `config/pomo/config.toml`            | `~/.config/pomo/config.toml`                     |
| `waybar/scripts/pomo.py`             | `~/.config/waybar/scripts/pomo.py`               |
| `waybar/modules/custom-pomo.jsonc`   | `~/.config/waybar/modules/custom-pomo.jsonc`     |
| `waybar/pomo.css`                    | append to `~/.config/waybar/style.css`           |

Then do the manual bar config step described above.

## Usage

```bash
pomo                    # default profile
pomo -p deep            # profile "deep"
pomo -w 40 -s 8 -c 2    # work / short break / cycles (override the profile)
pomo -L                 # list profiles
pomo --on-work-start "CMD" --on-work-end "CMD"   # one-off hooks
pomo --no-hooks         # run no hook at all
pomo --lang en          # force the UI language
```

Keys: `space` pause/resume · `n` next phase · `r` reset · `q` quit.
Waybar: click = pause/resume, right click = next phase.

## Configuration

`~/.config/pomo/config.toml`:

```toml
default_profile = "classic"
language = "auto"                 # auto | en | fr

[hooks]                           # applies to every profile
on_work_start = "playerctl -a -p mpv play"
on_work_end = "playerctl -a -p mpv pause"

[profiles.classic]
work = 25                         # minutes
short_break = 5
cycles = 4                        # work sessions before the long break
long_break = 15                   # optional

[profiles.silent]                 # per-profile hook override
work = 25
short_break = 5
cycles = 4
on_work_start = ""
on_work_end = '[ "$POMO_EVENT" = pause ] || echo "end $POMO_PROFILE" >> ~/.local/state/pomo.log'
```

| Config key      | CLI option          | Default |
|-----------------|---------------------|---------|
| `work`          | `-w, --work`        | `25` |
| `short_break`   | `-s, --short-break` | `5`  |
| `long_break`    | `-l, --long-break`  | `15` |
| `cycles`        | `-c, --cycles`      | `4`  |
| `on_work_start` | `--on-work-start`   | `playerctl -a -p mpv play`  |
| `on_work_end`   | `--on-work-end`     | `playerctl -a -p mpv pause` |
| `language`      | `--lang`            | `auto` |

Precedence: defaults < `[hooks]` < profile < CLI options. An empty string `""` disables a hook.

### Hooks

| Hook            | Runs when                                                                    |
|-----------------|------------------------------------------------------------------------------|
| `on_work_start` | a work period starts; the timer resumes during work                          |
| `on_work_end`   | work ends (naturally or with `n`); timer paused during work; `q` during work |

Environment variables passed to hooks:
`POMO_EVENT` (`start`/`resume` for the start hook, `end`/`pause`/`quit` for the end hook),
`POMO_PROFILE`, `POMO_DONE` (completed pomodoros), `POMO_CYCLES`, `POMO_WORK_MIN`.

## Localization

User-facing text (TUI, notifications, waybar tooltip, CLI help) is in English by default.
The language is resolved from `--lang`, then `$POMO_LANG`, then `language` in the config,
then the system locale (`LC_ALL`, `LC_MESSAGES`, `LANG`). Available: `en`, `fr`.

To add a language, add an entry to `TRANSLATIONS` in `bin/pomo` and `waybar/scripts/pomo.py`
(English strings are the keys).
