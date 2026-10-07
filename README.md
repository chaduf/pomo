# pomo

Pomodoro TUI (Textual) qui lance des commandes au début et à la fin des périodes de travail
(par défaut : play/pause de mpv via MPRIS), envoie des notifications et s'affiche dans waybar.

Dépendances : `python-textual`, `libnotify`, `waybar` ; pour les commandes par défaut : `mpv`, `mpv-mpris`, `playerctl`.

## Installation

```bash
./install.sh               # installe (propose d'installer les dépendances manquantes via pacman)
./install.sh --link        # liens symboliques vers ce dossier (les modifs ici sont prises en compte)
./install.sh --no-waybar   # sans l'intégration waybar
./install.sh --force       # écrase aussi config.toml et le style waybar en place
./install.sh --uninstall   # désinstaller (~/.config/pomo est conservé)
```

Sans `--force`, le script ne touche pas à un `config.toml` existant. Il sauvegarde `style.css`
en `*.bak-pomo` avant de le modifier et peut être relancé sans risque de doublon.

> **⚠ Étape manuelle obligatoire : la config de la barre waybar.**
> Le script **ne modifie jamais** le fichier de barre waybar (`~/.config/waybar/bars/top-bar.jsonc`,
> ou `~/.config/waybar/config.jsonc` selon ta config). Il installe le module, mais c'est à toi
> de l'afficher dans la barre :
>
> 1. ajouter le module dans `include` :
>    ```jsonc
>    "include": [
>      ...
>      "~/.config/waybar/modules/custom-pomo.jsonc",
>    ],
>    ```
> 2. placer `"custom/pomo"` où tu veux dans `modules-left`, `modules-center` ou `modules-right` :
>    ```jsonc
>    "modules-center": ["custom/music", "custom/pomo"],
>    ```
> 3. recharger waybar : `pkill -SIGUSR2 waybar`
>
> À la désinstallation, retire ces deux lignes à la main de la même façon.

### Installation manuelle

| Fichier du projet                    | Emplacement                                      |
|--------------------------------------|--------------------------------------------------|
| `bin/pomo`                           | `~/.local/bin/pomo`                              |
| `config/pomo/config.toml`            | `~/.config/pomo/config.toml`                     |
| `waybar/scripts/pomo.py`             | `~/.config/waybar/scripts/pomo.py`               |
| `waybar/modules/custom-pomo.jsonc`   | `~/.config/waybar/modules/custom-pomo.jsonc`     |
| `waybar/pomo.css`                    | à ajouter à la fin de `~/.config/waybar/style.css` |

Puis faire l'étape manuelle de la config de barre décrite ci-dessus.

## Utilisation

```bash
pomo                 # profil par défaut
pomo -p deep         # profil « deep »
pomo -w 40 -s 8 -c 2 # travail / pause / répétitions (priment sur le profil)
pomo -L              # lister les profils
pomo --debut-travail "CMD" --fin-travail "CMD"   # commandes ponctuelles
pomo --no-hooks      # ne lancer aucune commande
```

## Commandes de début / fin de travail

Deux commandes shell, configurables :

| Config (`config.toml`) | CLI               | Quand                                                        | Défaut                       |
|------------------------|-------------------|--------------------------------------------------------------|------------------------------|
| `debut_travail`        | `--debut-travail` | début d'une période de travail, reprise du minuteur          | `playerctl -a -p mpv play`   |
| `fin_travail`          | `--fin-travail`   | fin du travail (naturelle ou `n`), pause du minuteur, `q`    | `playerctl -a -p mpv pause`  |

Priorité : défauts < section `[commandes]` (tous les profils) < profil < options CLI.
Une chaîne vide `""` désactive la commande.

```toml
[commandes]                       # pour tous les profils
debut_travail = "playerctl -a -p mpv play"
fin_travail = "playerctl -a -p mpv pause"

[profils.silence]                 # surcharge pour un profil
travail = 25
pause = 5
repetitions = 4
debut_travail = ""
fin_travail = '[ "$POMO_EVENT" = pause ] || echo "fin $POMO_PROFILE" >> ~/.local/state/pomo.log'
```

Variables d'environnement transmises aux commandes :
`POMO_EVENT` (`start`/`resume` au début, `end`/`pause`/`quit` à la fin), `POMO_PROFILE`,
`POMO_DONE` (pomodoros terminés), `POMO_CYCLES`, `POMO_WORK_MIN`.

Touches : `espace` pause/reprise · `n` phase suivante · `r` reset · `q` quitter.
Waybar : clic = pause/reprise, clic droit = phase suivante.
