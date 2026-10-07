#!/usr/bin/env bash
# pomo installer (Pomodoro TUI + mpv + notifications + waybar)
#
#   ./install.sh               install (copy files)
#   ./install.sh --link        install as symlinks to this directory
#   ./install.sh --no-waybar   skip the waybar integration
#   ./install.sh --force       also overwrite an existing config.toml and waybar style
#   ./install.sh --uninstall   uninstall (~/.config/pomo is kept)
#
# The waybar bar config (e.g. bars/top-bar.jsonc) is NEVER modified:
# adding the "custom/pomo" module is a manual step (see README).
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
CONF_DIR="${XDG_CONFIG_HOME:-$HOME/.config}"
POMO_CONF="$CONF_DIR/pomo"
WAYBAR="$CONF_DIR/waybar"
DEPS=(python python-textual mpv mpv-mpris playerctl libnotify)

MODE=copy WITH_WAYBAR=1 UNINSTALL=0 FORCE=0
while (($#)); do
  case "$1" in
    --link) MODE=link ;;
    --no-waybar) WITH_WAYBAR=0 ;;
    --uninstall) UNINSTALL=1 ;;
    --force) FORCE=1 ;;
    -h|--help) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
  shift
done

c_ok=$'\e[32m' c_warn=$'\e[33m' c_err=$'\e[31m' c_off=$'\e[0m'
ok()   { echo "${c_ok}✓${c_off} $*"; }
warn() { echo "${c_warn}!${c_off} $*"; }
die()  { echo "${c_err}✗${c_off} $*" >&2; exit 1; }

install_file() {  # install_file SOURCE DEST MODE
  mkdir -p "$(dirname "$2")"
  if [[ "$MODE" == link ]]; then ln -sfn "$1" "$2"; else install -m "$3" "$1" "$2"; fi
  ok "$2"
}

remove_css() {  # remove the pomo block from style.css
  python3 - "$1" <<'EOF'
import re, sys
p = sys.argv[1]; s = open(p).read()
s = re.sub(r"\n*/\* ---- pomo \(pomodoro\) ---- \*/.*?(?=\n/\*(?! ---- pomo)|\Z)", "\n", s, flags=re.S)
open(p, "w").write(s.rstrip("\n") + "\n")
EOF
}

bar_reminder() {
  warn "Manual step: $1 your waybar bar config (e.g. $WAYBAR/bars/top-bar.jsonc):"
  echo "    - \"~/.config/waybar/modules/custom-pomo.jsonc\" in \"include\""
  echo "    - \"custom/pomo\" in \"modules-left\", \"modules-center\" or \"modules-right\""
}

reload_waybar() {
  if pgrep -x waybar >/dev/null; then
    pkill -SIGUSR2 -x waybar && ok "waybar reloaded"
  fi
}

# ---------------------------------------------------------------- uninstall
if ((UNINSTALL)); then
  rm -fv "$BIN_DIR/pomo" "$WAYBAR/scripts/pomo.py" "$WAYBAR/modules/custom-pomo.jsonc"
  if [[ -f "$WAYBAR/style.css" ]] && grep -q '/\* ---- pomo (pomodoro) ---- \*/' "$WAYBAR/style.css"; then
    cp "$WAYBAR/style.css" "$WAYBAR/style.css.bak-pomo"
    remove_css "$WAYBAR/style.css"
    ok "style removed from $WAYBAR/style.css"
  fi
  reload_waybar
  bar_reminder "remove these from"
  warn "config kept: $POMO_CONF (delete it manually if needed)"
  exit 0
fi

# ---------------------------------------------------------------- dependencies
echo "== Dependencies"
if command -v pacman >/dev/null; then
  missing=()
  for p in "${DEPS[@]}"; do pacman -Qq "$p" &>/dev/null || missing+=("$p"); done
  ((WITH_WAYBAR)) && ! pacman -Qq waybar &>/dev/null && missing+=(waybar)
  if ((${#missing[@]})); then
    warn "missing: ${missing[*]}"
    read -rp "Install with pacman? [Y/n] " r
    if [[ ! "$r" =~ ^[nN] ]]; then sudo pacman -S --needed "${missing[@]}"
    else warn "dependencies not installed, pomo may not work"; fi
  else
    ok "all present"
  fi
else
  warn "pacman not found: check ${DEPS[*]} manually"
fi

# ---------------------------------------------------------------- files
echo "== Files ($MODE)"
install_file "$SRC/bin/pomo" "$BIN_DIR/pomo" 755
if [[ -e "$POMO_CONF/config.toml" ]] && ((!FORCE)); then
  ok "$POMO_CONF/config.toml already exists, kept"
  grep -qE '^\s*(\[profils|defaut\s*=|\[commandes)' "$POMO_CONF/config.toml" \
    && warn "it uses the old French keys and will be rejected: migrate it or rerun with --force"
else
  [[ -e "$POMO_CONF/config.toml" && ! -L "$POMO_CONF/config.toml" ]] \
    && cp "$POMO_CONF/config.toml" "$POMO_CONF/config.toml.bak-pomo" \
    && warn "previous config backed up: $POMO_CONF/config.toml.bak-pomo"
  install_file "$SRC/config/pomo/config.toml" "$POMO_CONF/config.toml" 644
fi
[[ ":$PATH:" == *":$BIN_DIR:"* ]] || warn "$BIN_DIR is not in your PATH"

# ---------------------------------------------------------------- waybar
if ((WITH_WAYBAR)); then
  echo "== Waybar"
  install_file "$SRC/waybar/scripts/pomo.py" "$WAYBAR/scripts/pomo.py" 755
  install_file "$SRC/waybar/modules/custom-pomo.jsonc" "$WAYBAR/modules/custom-pomo.jsonc" 644

  css="$WAYBAR/style.css"
  if [[ ! -f "$css" ]]; then
    warn "$css not found: add the content of waybar/pomo.css to your style"
  elif grep -q '#custom-pomo' "$css" && ((!FORCE)); then
    ok "style already present in $css"
  else
    cp "$css" "$css.bak-pomo"
    grep -q '/\* ---- pomo (pomodoro) ---- \*/' "$css" && remove_css "$css"
    { echo; cat "$SRC/waybar/pomo.css"; } >> "$css"
    ok "style added to $css"
    grep -q '@define-color \(red\|green\|lavender\)\b' "$WAYBAR"/*.css 2>/dev/null \
      || warn "pomo.css uses @red/@green/@lavender: adjust the colors if your theme does not define them"
  fi
  reload_waybar
  echo
  bar_reminder "add these to (if not done yet)"
fi

echo
ok "Installation complete. Run: pomo   (pomo -h for help, pomo -L to list profiles)"
