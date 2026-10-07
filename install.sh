#!/usr/bin/env bash
# Installation de pomo (TUI Pomodoro + mpv + notifications + waybar)
#
#   ./install.sh               installe (copie les fichiers)
#   ./install.sh --link        installe via liens symboliques vers ce dossier
#   ./install.sh --no-waybar   n'installe pas l'intégration waybar
#   ./install.sh --force       écrase aussi config.toml et le style waybar existants
#   ./install.sh --uninstall   désinstalle (la config ~/.config/pomo est conservée)
#
# La config de barre waybar (ex. bars/top-bar.jsonc) n'est JAMAIS modifiée :
# l'ajout du module "custom/pomo" se fait à la main (voir README).
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
    *) echo "Option inconnue : $1" >&2; exit 1 ;;
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

remove_css() {  # retire le bloc pomo de style.css
  python3 - "$1" <<'EOF'
import re, sys
p = sys.argv[1]; s = open(p).read()
s = re.sub(r"\n*/\* ---- pomo \(pomodoro\) ---- \*/.*?(?=\n/\*(?! ---- pomo)|\Z)", "\n", s, flags=re.S)
open(p, "w").write(s.rstrip("\n") + "\n")
EOF
}

bar_reminder() {
  warn "Étape manuelle : $1 dans ta config de barre waybar (ex. $WAYBAR/bars/top-bar.jsonc) :"
  echo "    - \"~/.config/waybar/modules/custom-pomo.jsonc\" dans \"include\""
  echo "    - \"custom/pomo\" dans \"modules-left\", \"modules-center\" ou \"modules-right\""
}

reload_waybar() {
  if pgrep -x waybar >/dev/null; then
    pkill -SIGUSR2 -x waybar && ok "waybar rechargée"
  fi
}

# ---------------------------------------------------------------- désinstallation
if ((UNINSTALL)); then
  rm -fv "$BIN_DIR/pomo" "$WAYBAR/scripts/pomo.py" "$WAYBAR/modules/custom-pomo.jsonc"
  if [[ -f "$WAYBAR/style.css" ]] && grep -q '/\* ---- pomo (pomodoro) ---- \*/' "$WAYBAR/style.css"; then
    cp "$WAYBAR/style.css" "$WAYBAR/style.css.bak-pomo"
    remove_css "$WAYBAR/style.css"
    ok "style retiré de $WAYBAR/style.css"
  fi
  reload_waybar
  bar_reminder "retire"
  warn "config conservée : $POMO_CONF (supprime-la à la main si besoin)"
  exit 0
fi

# ---------------------------------------------------------------- dépendances
echo "== Dépendances"
if command -v pacman >/dev/null; then
  missing=()
  for p in "${DEPS[@]}"; do pacman -Qq "$p" &>/dev/null || missing+=("$p"); done
  ((WITH_WAYBAR)) && ! pacman -Qq waybar &>/dev/null && missing+=(waybar)
  if ((${#missing[@]})); then
    warn "manquant : ${missing[*]}"
    read -rp "Installer avec pacman ? [O/n] " r
    if [[ ! "$r" =~ ^[nN] ]]; then sudo pacman -S --needed "${missing[@]}"
    else warn "dépendances non installées, pomo risque de ne pas fonctionner"; fi
  else
    ok "toutes présentes"
  fi
else
  warn "pacman introuvable : vérifie à la main ${DEPS[*]}"
fi

# ---------------------------------------------------------------- fichiers
echo "== Fichiers ($MODE)"
install_file "$SRC/bin/pomo" "$BIN_DIR/pomo" 755
if [[ -e "$POMO_CONF/config.toml" ]] && ((!FORCE)); then
  ok "$POMO_CONF/config.toml existe déjà, conservé"
else
  [[ -e "$POMO_CONF/config.toml" && ! -L "$POMO_CONF/config.toml" ]] \
    && cp "$POMO_CONF/config.toml" "$POMO_CONF/config.toml.bak-pomo" \
    && warn "ancienne config sauvegardée : $POMO_CONF/config.toml.bak-pomo"
  install_file "$SRC/config/pomo/config.toml" "$POMO_CONF/config.toml" 644
fi
[[ ":$PATH:" == *":$BIN_DIR:"* ]] || warn "$BIN_DIR n'est pas dans ton PATH"

# ---------------------------------------------------------------- waybar
if ((WITH_WAYBAR)); then
  echo "== Waybar"
  install_file "$SRC/waybar/scripts/pomo.py" "$WAYBAR/scripts/pomo.py" 755
  install_file "$SRC/waybar/modules/custom-pomo.jsonc" "$WAYBAR/modules/custom-pomo.jsonc" 644

  css="$WAYBAR/style.css"
  if [[ ! -f "$css" ]]; then
    warn "$css introuvable : ajoute le contenu de waybar/pomo.css à ton style"
  elif grep -q '#custom-pomo' "$css" && ((!FORCE)); then
    ok "style déjà présent dans $css"
  else
    cp "$css" "$css.bak-pomo"
    grep -q '/\* ---- pomo (pomodoro) ---- \*/' "$css" && remove_css "$css"
    { echo; cat "$SRC/waybar/pomo.css"; } >> "$css"
    ok "style ajouté à $css"
    grep -q '@define-color \(red\|green\|lavender\)\b' "$WAYBAR"/*.css 2>/dev/null \
      || warn "pomo.css utilise @red/@green/@lavender : adapte les couleurs si ton thème ne les définit pas"
  fi
  reload_waybar
  echo
  bar_reminder "ajoute (si ce n'est pas déjà fait)"
fi

echo
ok "Installation terminée. Lance : pomo   (pomo -h pour l'aide, pomo -L pour les profils)"
