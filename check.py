"""Audit of the data tables, run with `python main.py --check`.

Nothing here talks to the game or to Discord. It only looks for the kinds of
mistake that are easy to make by hand and impossible to notice at runtime: a
trial whose map cannot be resolved, a name typed two different ways, a
language missing half its strings.

Findings are split into problems, which will visibly affect the presence, and
notes, which are things worth double checking against the game itself.
"""

import os

import config
import game_constants as gc
import strings

# Keys GameInfo asks strings.py for. Kept here so a missing one is caught by
# --check rather than by a user seeing a raw key in their presence.
REQUIRED_KEYS = [
    "menu", "lobby", "matchmaking", "loading", "in_trial", "unknown_trial",
    "brand", "game", "season", "ping",
    "stat_trials", "stat_time", "stat_longest", "stat_session", "stat_total",
    "stat_favourite", "stat_favourite_trial", "stat_outcomes",
    "outcome_completed", "outcome_failed", "outcome_unfinished",
]


def _map_for(trial_id):
    return gc.trial_maps.get(trial_id[:2])


def problems():
    found = []

    for key in REQUIRED_KEYS:
        if key not in strings.STRINGS[strings.FALLBACK]:
            found.append("strings.py is missing the %r key" % key)

    for fragment, key in gc.menu_pages.items():
        if key not in strings.STRINGS[strings.FALLBACK]:
            found.append("menu page %r points at unknown string %r" % (fragment, key))

    for phase, key in gc.stage_phases.items():
        if key is not None and key not in strings.STRINGS[strings.FALLBACK]:
            found.append("game phase %r points at unknown string %r" % (phase, key))
    if gc.STAGE_STARTED not in gc.stage_phases:
        found.append("stage_phases does not list %r" % gc.STAGE_STARTED)

    for table, what in ((gc.programs, "program"), (gc.stages, "stage"),
                        (gc.regions, "region"), (gc.trial_results, "trial result")):
        for key, value in table.items():
            if not value or not value.strip():
                found.append("%s %s has an empty label" % (what, key))

    for code, table in strings.STRINGS.items():
        if code == strings.FALLBACK:
            continue
        missing = [k for k in strings.STRINGS[strings.FALLBACK] if k not in table]
        if missing:
            found.append("language %r is missing %d strings: %s"
                         % (code, len(missing), ", ".join(sorted(missing)[:6])))

    for trial_id, name in gc.trial_names.items():
        if not name or not name.strip():
            found.append("trial %s has an empty name" % trial_id)

    overlap = sorted(set(gc.trial_names) & gc.known_trial_ids)
    for trial_id in overlap:
        found.append("%s is in both trial_names and known_trial_ids" % trial_id)

    if config.BUTTONS:
        if not isinstance(config.BUTTONS, list) or len(config.BUTTONS) > 2:
            found.append("BUTTONS must be a list of at most two entries")
        else:
            for button in config.BUTTONS:
                if not isinstance(button, dict) or "label" not in button or "url" not in button:
                    found.append("each BUTTONS entry needs a label and a url")

    if str(config.STATUS_DISPLAY).lower() not in ("name", "details", "state"):
        found.append("STATUS_DISPLAY is %r, expected name, details or state"
                     % (config.STATUS_DISPLAY,))

    if config.LANGUAGE != "auto" and config.LANGUAGE not in strings.STRINGS:
        found.append("LANGUAGE is %r, which strings.py does not define"
                     % config.LANGUAGE)

    return found


def notes():
    found = []

    no_map = sorted(t for t in gc.trial_names if not _map_for(t))
    if no_map:
        found.append("%d trials show no map, their id prefix is not in "
                     "trial_maps: %s" % (len(no_map), ", ".join(no_map)))

    unnamed = sorted(gc.known_trial_ids)
    if unnamed:
        found.append("%d trials exist in the game but have no name yet: %s"
                     % (len(unnamed), ", ".join(unnamed)))

    # A map named two ways is confusing in the statistics, where both
    # spellings would be counted apart.
    by_stage = {gc.stage_name(stage) for stage in gc.stages}
    by_prefix = set(gc.trial_maps.values())
    for name in sorted(by_stage - by_prefix):
        found.append("stage %r has no matching trial_maps prefix" % name)

    if "Success" not in gc.trial_results and "Complete" not in gc.trial_results:
        found.append("trial_results has no wording for a completed trial")

    # The same wording typed two ways, which means at least one is a copy error.
    by_lower = {}
    for trial_id, name in gc.trial_names.items():
        by_lower.setdefault(name.lower(), set()).add(name)
    for spellings in by_lower.values():
        if len(spellings) > 1:
            found.append("same name spelled several ways: %s"
                         % " / ".join(sorted(spellings)))

    # Most names write "the" in lower case. The ones that do not are usually
    # hand-typed rather than extracted, so they are worth re-checking.
    caps = sorted(n for n in gc.trial_names.values() if " The " in n)
    if caps:
        found.append("%d names capitalise \"The\" mid-sentence, unlike the "
                     "rest: %s" % (len(caps), " / ".join(caps)))

    # ... and the mirror case: a final word left in lower case.
    lower_tail = sorted(n for n in gc.trial_names.values()
                        if len(n.split()) > 1 and n.split()[-1].islower()
                        and not n.isupper())
    if lower_tail:
        found.append("%d names end on a lower case word, unlike the rest: %s"
                     % (len(lower_tail), " / ".join(lower_tail)))

    # A trial "named" after its own map reads twice on Discord, and is most
    # likely a placeholder from the first transcription.
    same_as_map = sorted(t for t, n in gc.trial_names.items()
                         if _map_for(t) and n.lower() == _map_for(t).lower())
    if same_as_map:
        found.append("%d trial(s) carry their map's name instead of a title: %s"
                     % (len(same_as_map), ", ".join(same_as_map)))

    duplicates = {}
    for trial_id, name in gc.trial_names.items():
        duplicates.setdefault(name, []).append(trial_id)
    shared = {n: ids for n, ids in duplicates.items() if len(ids) > 1}
    for name, ids in sorted(shared.items()):
        found.append("%r is used by %s" % (name, " and ".join(sorted(ids))))

    if os.path.exists(config.UNKNOWN_TRIALS_FILE):
        try:
            with open(config.UNKNOWN_TRIALS_FILE, encoding="utf-8") as f:
                seen = {line.split("\t")[1] for line in f if "\t" in line}
            pending = sorted(seen - set(gc.trial_names) - gc.known_trial_ids)
            if pending:
                found.append("%s lists %d id(s) still unnamed: %s"
                             % (os.path.basename(config.UNKNOWN_TRIALS_FILE),
                                len(pending), ", ".join(pending)))
        except (OSError, IndexError):
            pass

    return found


def report(log):
    """Print the audit. Returns the number of real problems found."""
    log.info("Data check")
    log.info("  %d trials named, %d known but unnamed, %d maps, %d game phases, "
             "%d languages", len(gc.trial_names), len(gc.known_trial_ids),
             len(gc.trial_maps), len(gc.stage_phases), len(strings.STRINGS))

    issues = problems()
    if issues:
        log.info("")
        log.warning("  %d problem(s):", len(issues))
        for item in issues:
            log.warning("    - %s", item)
    else:
        log.info("  No problems found")

    remarks = notes()
    if remarks:
        log.info("")
        log.info("  %d thing(s) worth verifying against the game:", len(remarks))
        for item in remarks:
            log.info("    - %s", item)

    return len(issues)
