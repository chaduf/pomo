"""Localization: translations of the user-facing text and choice of the language.

`lang` is set once at startup (pomo.main); `_()` reads it at each call, so other modules
can import `_` directly."""
import os

# English strings are the keys; add a language by adding a dict here.
TRANSLATIONS = {
    "fr": {
        "Work": "Travail",
        "Short break": "Pause courte",
        "Long break": "Pause longue",
        " (paused)": " (en pause)",
        "Next phase": "Phase suivante",
        "{phase}: +{minutes} min": "{phase} : +{minutes} min",
        "{phase}: -{minutes} min": "{phase} : -{minutes} min",
        "Cycle: {n} work session(s) before the long break": "Cycle : {n} session(s) de travail avant la pause longue",
        "Cannot remove: this cycle needs at least {n} work session(s)":
            "Impossible de retirer : ce cycle compte au moins {n} session(s) de travail",
        "add a work session to the cycle (the long break comes later)":
            "ajouter une session de travail au cycle (la pause longue arrive plus tard)",
        "remove a work session from the cycle (never below the current one)":
            "retirer une session de travail du cycle (jamais sous la session en cours)",
        "Reset": "Réinitialiser",
        "Start": "Démarrer",
        "Pause": "Pause",
        "Resume": "Reprendre",
        "Pomodoro": "Pomodoro",
        "Lap": "Tour",
        "Stopwatch": "Chronomètre",
        "Lap time": "Temps du tour",
        "Total": "Total",
        "Laps: {n}": "Tours : {n}",
        "Stopwatch mode": "Mode chronomètre",
        "Pomodoro mode": "Mode pomodoro",
        "start in stopwatch mode": "démarrer en mode chronomètre",
        "Quit": "Quitter",
        "Help": "Aide",
        "Keys": "Raccourcis",
        "Timer": "Minuteur",
        "App": "Application",
        "start / pause / resume": "démarrer / mettre en pause / reprendre",
        "next phase (ends the current one)": "phase suivante (termine la phase en cours)",
        "add {minutes} min to the current phase": "ajouter {minutes} min à la phase en cours",
        "remove {minutes} min (ends the phase when {minutes} min or less remain)":
            "retirer {minutes} min (termine la phase s'il reste {minutes} min ou moins)",
        "full reset: back to work, counters at zero": "réinitialisation complète : retour au travail, compteurs à zéro",
        "record a lap": "enregistrer un tour",
        "reset the time and laps": "remettre le temps et les tours à zéro",
        "switch profile": "changer de profil",
        "switch to the stopwatch": "passer au chronomètre",
        "switch to the pomodoro": "passer au pomodoro",
        "disable the hooks (currently on)": "désactiver les commandes (actuellement actives)",
        "enable the hooks (currently off)": "activer les commandes (actuellement désactivées)",
        "this help": "cette aide",
        "quit": "quitter",
        "Work time is recorded at the end of each cycle (title asked in a form).":
            "Le temps de travail est enregistré à la fin de chaque cycle (titre demandé dans un formulaire).",
        "Esc, q or ?: close": "Échap, q ou ? : fermer",
        "Back to work!": "Au travail !",
        "Session {n}/{total} — {minutes} min": "Session {n}/{total} — {minutes} min",
        "{minutes} min break — {done} pomodoro(s) done": "{minutes} min de pause — {done} pomodoro(s) fait(s)",
        "Profile: {name}  ·  ": "Profil : {name}  ·  ",
        "Pomodoros: {done}  ·  cycle {n}/{total}": "Pomodoros : {done}  ·  cycle {n}/{total}",
        "error in {file}: {error}": "erreur dans {file} : {error}",
        "unknown key '{key}' in {where} (expected: {keys})": "clé inconnue « {key} » dans {where} (attendu : {keys})",
        "'{key}' must be an integer > 0 ({where})": "« {key} » doit être un entier > 0 ({where})",
        "'{key}' must be a string ({where})": "« {key} » doit être une chaîne ({where})",
        "profile '{name}'": "le profil « {name} »",
        "profile '{name}' not found (available: {names})": "profil « {name} » introuvable (disponibles : {names})",
        "none": "aucun",
        "must be an integer > 0": "doit être un entier > 0",
        "{file} uses the old French keys (profils, defaut, commandes...): "
        "update it, see config.toml in the project":
            "{file} utilise les anciennes clés françaises (profils, defaut, commandes...) : "
            "mets-le à jour, voir config.toml dans le projet",
        "No profiles ({file})": "Aucun profil ({file})",
        "work {work} min · break {short} min · long break {long} min · {cycles} cycles":
            "travail {work} min · pause {short} min · pause longue {long} min · {cycles} répétitions",
        "start: {start}  ·  end: {end}": "début : {start}  ·  fin : {end}",
        "(nothing)": "(rien)",
        "Pomodoro TUI: runs commands when work starts/ends (pauses/resumes media by default)":
            "Pomodoro TUI : lance des commandes au début/à la fin du travail (pause/reprise de la musique par défaut)",
        "Config: {file}. Precedence: defaults < [hooks] < profile < CLI options. "
        "Hooks receive POMO_EVENT (start|resume|end|pause|quit|switch|reset), POMO_PROFILE, "
        "POMO_DONE, POMO_CYCLES, POMO_WORK_MIN.":
            "Config : {file}. Priorité : défauts < [hooks] < profil < options CLI. "
            "Les commandes reçoivent POMO_EVENT (start|resume|end|pause|quit|switch|reset), POMO_PROFILE, "
            "POMO_DONE, POMO_CYCLES, POMO_WORK_MIN.",
        "profile to use (default: default_profile from the config file)":
            "profil à utiliser (défaut : default_profile du fichier de config)",
        "list profiles and exit": "lister les profils et quitter",
        "work minutes ({default})": "minutes de travail ({default})",
        "short break minutes ({default})": "minutes de pause courte ({default})",
        "long break minutes ({default})": "minutes de pause longue ({default})",
        "work sessions before the long break ({default})": "répétitions avant la pause longue ({default})",
        "command run when work starts (\"{default}\")": "commande au début du travail (« {default} »)",
        "command run when work ends (\"{default}\")": "commande à la fin du travail (« {default} »)",
        "start with the hooks disabled (c toggles them in the app)":
            "démarrer avec les commandes désactivées (c les réactive dans l'application)",
        "Hooks disabled": "Commandes désactivées",
        "Hooks enabled": "Commandes activées",
        "  ·  hooks off": "  ·  commandes désactivées",
        "UI language: {langs} (default: auto)": "langue de l'interface : {langs} (défaut : auto)",
        "Cycle complete: record your work": "Cycle terminé : enregistre ton travail",
        "Unfinished cycle: record your work": "Cycle inachevé : enregistre ton travail",
        "Unrecorded work from a previous session": "Travail non enregistré d'une session précédente",
        "Title (required)": "Titre (obligatoire)",
        "Description (optional)": "Description (facultative)",
        "The title is required": "Le titre est obligatoire",
        "Save": "Enregistrer",
        "Discard": "Abandonner",
        "Enter: next field · Ctrl+S: save": "Entrée : champ suivant · Ctrl+S : enregistrer",
        "{n} time entry(ies) recorded in {file}": "{n} entrée(s) enregistrée(s) dans {file}",
        "Time entries kept in the log, but {file} could not be written: {error}":
            "Entrées conservées dans le journal, mais impossible d'écrire {file} : {error}",
        "Calendar file: {file}": "Fichier agenda : {file}",
        "ics files: {dir}": "fichiers ics : {dir}",
        "directory for the .ics file written at the end of each cycle ({default})":
            "dossier du fichier .ics écrit à la fin de chaque cycle ({default})",
        "Work discarded": "Travail abandonné",
        "No work to record (entries under {minutes} min are ignored)":
            "Rien à enregistrer (les entrées de moins de {minutes} min sont ignorées)",
        "{n} time entry(ies) exported to {file}": "{n} entrée(s) exportée(s) dans {file}",
        "no time entry to export ({file})": "aucune entrée à exporter ({file})",
        "export the recorded time entries as an iCalendar (.ics) file (default: {file}, - for stdout)":
            "exporter les entrées enregistrées en fichier iCalendar (.ics) (défaut : {file}, - pour la sortie standard)",
        "with --export-ics: only entries on or after DATE (YYYY-MM-DD)":
            "avec --export-ics : seulement les entrées à partir de DATE (AAAA-MM-JJ)",
        "with --export-ics: only entries on or before DATE (YYYY-MM-DD)":
            "avec --export-ics : seulement les entrées jusqu'à DATE (AAAA-MM-JJ)",
        "invalid date: {value} (expected YYYY-MM-DD)": "date invalide : {value} (attendu AAAA-MM-JJ)",
        "Choose a profile": "Choisir un profil",
        "↑↓ / j k: move · Enter: select · Esc: cancel": "↑↓ / j k : naviguer · Entrée : valider · Échap : annuler",
        "No profiles in {file}": "Aucun profil dans {file}",
        "Profile '{name}' loaded": "Profil « {name} » chargé",
    },
}
LANGUAGES = ("en", *TRANSLATIONS)
lang = "en"


def _(text: str, **kwargs) -> str:
    text = TRANSLATIONS.get(lang, {}).get(text, text)
    return text.format(**kwargs) if kwargs else text


def resolve_language(*candidates: str | None) -> str:
    """First explicit candidate wins; 'auto' or None falls through to the locale."""
    for c in candidates:
        if c and c != "auto":
            return c if c in LANGUAGES else "en"
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        code = os.environ.get(var, "")[:2]
        if code:
            return code if code in LANGUAGES else "en"
    return "en"
