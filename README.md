# pomo

Pomodoro TUI (Textual) qui pilote mpv via MPRIS, envoie des notifications et s'affiche dans waybar.

Dépendances : `python-textual`, `mpv-mpris`, `playerctl`, `libnotify`, `waybar`.

## Installation

```bash
./install.sh               # installe (propose d'installer les dépendances manquantes via pacman)
./install.sh --link        # liens symboliques vers ce dossier (les modifs ici sont prises en compte)
./install.sh --no-waybar   # sans l'intégration waybar
./install.sh --bar FICHIER # préciser la config de barre waybar à modifier
./install.sh --force       # écrase aussi config.toml et le style waybar en place
./install.sh --uninstall   # désinstaller (~/.config/pomo est conservé)
```

Sans `--force`, le script ne touche pas à un `config.toml` existant. Il sauvegarde les fichiers waybar modifiés
en `*.bak-pomo` et peut être relancé sans risque de doublon.

### Installation manuelle

| Fichier du projet                    | Emplacement                                      |
|--------------------------------------|--------------------------------------------------|
| `bin/pomo`                           | `~/.local/bin/pomo`                              |
| `config/pomo/config.toml`            | `~/.config/pomo/config.toml`                     |
| `waybar/scripts/pomo.py`             | `~/.config/waybar/scripts/pomo.py`               |
| `waybar/modules/custom-pomo.jsonc`   | `~/.config/waybar/modules/custom-pomo.jsonc`     |
| `waybar/pomo.css`                    | à ajouter à la fin de `~/.config/waybar/style.css` |

Dans la config de la barre (`bars/top-bar.jsonc`) :
- ajouter `"~/.config/waybar/modules/custom-pomo.jsonc"` dans `include`
- ajouter `"custom/pomo"` dans un `modules-*` (ex. `"modules-center": ["custom/music", "custom/pomo"]`)

## Utilisation

```bash
pomo                 # profil par défaut
pomo -p deep         # profil « deep »
pomo -w 40 -s 8 -c 2 # travail / pause / répétitions (priment sur le profil)
pomo -L              # lister les profils
```

Touches : `espace` pause/reprise · `n` phase suivante · `r` reset · `q` quitter.
Waybar : clic = pause/reprise, clic droit = phase suivante.
