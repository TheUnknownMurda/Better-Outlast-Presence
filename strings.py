"""Presence wording, per language.

The game logs which language it runs in, so the presence can follow it. Any
language that is missing falls back to English, and `config.TEXT_OVERRIDES`
wins over everything so a user can reword any single line.
"""

import config

# Language code as it appears in the game log -> the table to use.
STRINGS = {
    "en": {
        "menu": "In the main menu",
        "lobby": "In the Sleep Room",
        "matchmaking": "Looking for a trial",
        "loading": "Loading trial...",
        "waiting_players": "Waiting for players",
        "wagon": "Heading to the trial",
        "in_trial": "In a trial",
        "unknown_trial": "Unknown trial",
        "brand": "Murkoff Corporation",
        "game": "The Outlast Trials",
        "season": "Season {number}",
        "ping": "{region} ({ping} ms)",
        "page_splash": "At the title screen",
        "page_terminal": "At the Terminal",
        "page_customization": "In the customisation menu",
        "page_staff": "With the Murkoff staff",
        "page_director": "With the Director",
        "page_invasion": "Browsing Invasion",
        "page_rewards": "Claiming rewards",
        "page_news": "Reading the news",
        "page_tutorials": "In the tutorials",
        "page_season": "Watching the season trailer",
        "page_twitch": "Linking their Twitch account",
        "stat_trials": "Trials played",
        "stat_time": "Time in trials",
        "stat_longest": "Longest trial",
        "stat_session": "This session",
        "stat_total": "All time",
        "stat_favourite": "Most played map",
        "stat_favourite_trial": "Most played trial",
        "stat_outcomes": "Outcomes",
        "outcome_completed": "completed",
        "outcome_failed": "failed",
        "outcome_unfinished": "left early",
    },
    "fr": {
        "menu": "Dans le menu principal",
        "lobby": "Dans la Salle de Repos",
        "matchmaking": "Recherche d'une epreuve",
        "loading": "Chargement de l'epreuve...",
        "waiting_players": "En attente des joueurs",
        "wagon": "En route vers l'epreuve",
        "in_trial": "En epreuve",
        "unknown_trial": "Epreuve inconnue",
        "brand": "Murkoff Corporation",
        "game": "The Outlast Trials",
        "season": "Saison {number}",
        "ping": "{region} ({ping} ms)",
        "page_splash": "Sur l'ecran titre",
        "page_terminal": "Au Terminal",
        "page_customization": "Dans le menu de personnalisation",
        "page_staff": "Avec le personnel Murkoff",
        "page_director": "Avec le Directeur",
        "page_invasion": "Consulte Invasion",
        "page_rewards": "Recupere ses recompenses",
        "page_news": "Lit les actualites",
        "page_tutorials": "Dans les tutoriels",
        "page_season": "Regarde la bande-annonce",
        "page_twitch": "Lie son compte Twitch",
        "stat_trials": "Epreuves jouees",
        "stat_time": "Temps en epreuve",
        "stat_longest": "Plus longue epreuve",
        "stat_session": "Cette session",
        "stat_total": "Depuis toujours",
        "stat_favourite": "Carte la plus jouee",
        "stat_favourite_trial": "Epreuve la plus jouee",
        "stat_outcomes": "Resultats",
        "outcome_completed": "reussie(s)",
        "outcome_failed": "echouee(s)",
        "outcome_unfinished": "abandonnee(s)",
    },
}

FALLBACK = "en"

# The game writes its audio language in full; map it back to a code.
AUDIO_LANGUAGES = {
    "english": "en",
    "francais": "fr",
    "french": "fr",
}

_active = FALLBACK


def available():
    return sorted(STRINGS)


def set_language(code):
    """Select a language. Unknown codes keep the current one."""
    global _active
    if not code:
        return _active
    code = code.strip().lower()
    code = AUDIO_LANGUAGES.get(code, code)
    code = code.split("-")[0]          # "en-US" -> "en"
    if code in STRINGS:
        _active = code
    return _active


def language():
    return _active


def has(key):
    return key in STRINGS[FALLBACK] or key in config.TEXT_OVERRIDES


def text(key, **fields):
    """Look up a string, honouring config overrides, and format it."""
    value = config.TEXT_OVERRIDES.get(key)
    if value is None:
        value = STRINGS.get(_active, {}).get(key)
    if value is None:
        value = STRINGS[FALLBACK].get(key, key)
    return value.format(**fields) if fields else value
