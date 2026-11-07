"""Configuration: defaults, reading and validating config.toml, resolving a profile's settings."""
import os
import tomllib
from pathlib import Path

from .i18n import _

CONFIG_FILE = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "pomo" / "config.toml"


class ConfigError(Exception):
    """Invalid config: fatal at startup, shown as an in-app error when switching profiles."""


DEFAULTS = {
    "work": 25, "short_break": 5, "long_break": 15, "cycles": 4,
    "on_work_start": "pomo-media resume",
    "on_work_end": "pomo-media pause",
    "ics_dir": "~/.local/share/pomo/ics",
}
INT_KEYS = ("work", "short_break", "long_break", "cycles")
HOOK_KEYS = ("on_work_start", "on_work_end")
PATH_KEYS = ("ics_dir",)
LEGACY_KEYS = ("profils", "defaut", "commandes")


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        with CONFIG_FILE.open("rb") as f:
            cfg = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(_("error in {file}: {error}", file=CONFIG_FILE, error=e))
    if any(k in cfg for k in LEGACY_KEYS):
        raise ConfigError(_("{file} uses the old French keys (profils, defaut, commandes...): "
               "update it, see config.toml in the project", file=CONFIG_FILE))
    return cfg


def parse_values(table: dict, where: str, allowed: tuple[str, ...]) -> dict:
    for key, val in table.items():
        if key not in allowed:
            raise ConfigError(_("unknown key '{key}' in {where} (expected: {keys})",
                   key=key, where=where, keys=", ".join(allowed)))
        if key in INT_KEYS and (not isinstance(val, int) or isinstance(val, bool) or val <= 0):
            raise ConfigError(_("'{key}' must be an integer > 0 ({where})", key=key, where=where))
        if key in HOOK_KEYS + PATH_KEYS and not isinstance(val, str):
            raise ConfigError(_("'{key}' must be a string ({where})", key=key, where=where))
    return dict(table)


def profile_values(profiles: dict, name: str) -> dict:
    if name not in profiles:
        raise ConfigError(_("profile '{name}' not found (available: {names})",
               name=name, names=", ".join(profiles) or _("none")))
    return parse_values(profiles[name], _("profile '{name}'", name=name), INT_KEYS + HOOK_KEYS + PATH_KEYS)


def resolve_settings(cfg: dict, profile: str | None) -> dict:
    """defaults < [hooks] < profile."""
    settings = {**DEFAULTS, **parse_values(cfg.get("hooks", {}), "[hooks]", HOOK_KEYS)}
    if profile:
        settings.update(profile_values(cfg.get("profiles", {}), profile))
    return settings
