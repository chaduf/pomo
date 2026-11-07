"""Everything that touches the system: clocks, hooks, desktop notifications, waybar.

Other modules call these through the module (`system.notify(...)`), so that tests can
replace them."""
import os
import subprocess
import time
from pathlib import Path

STATE_FILE = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "pomo.json"  # read by waybar
WAYBAR_SIGNAL = 9  # must match "signal" in the waybar module

# Directory holding pomo (and pomo-media), set by the launcher. Prepended to the hooks' PATH
# because launchers (rofi, app menus) often run pomo without ~/.local/bin in PATH.
BIN_DIR = ""


def monotonic() -> float:
    return time.monotonic()


def wall_time() -> float:
    return time.time()


def fail(message: str) -> None:
    raise SystemExit(f"pomo: {message}")


def sh(*cmd: str) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=3).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def run_hook(cmd: str, env: dict[str, str]) -> None:
    """Run a user shell command without blocking the TUI."""
    if not cmd.strip():
        return
    path = os.pathsep.join(p for p in (BIN_DIR, os.environ.get("PATH", "")) if p)
    try:
        subprocess.Popen(
            ["sh", "-c", cmd], env={**os.environ, **env, "PATH": path}, start_new_session=True,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass


def notify(title: str, body: str, icon: str, urgency: str = "normal") -> None:
    subprocess.Popen(
        ["notify-send", "-a", "pomo", "-u", urgency, "-i", icon,
         "-h", "string:x-canonical-private-synchronous:pomo", title, body],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def refresh_waybar() -> None:
    sh("pkill", f"-RTMIN+{WAYBAR_SIGNAL}", "-x", "waybar")
