"""Play statistics, kept between runs in a small JSON file.

Only trials watched live are counted. Replaying the log at startup rebuilds
the presence but deliberately records nothing, otherwise restarting the tool
would count the same trial again.
"""

import json
import logging
import os
import time

import config
import strings

log = logging.getLogger(__name__)

FORMAT_VERSION = 1
MIN_TRIAL_SECONDS = 30       # shorter is a bounce back to the lobby, not a trial
UNFINISHED = "unfinished"    # left, disconnected or the game was closed


def duration(seconds):
    """3725 -> '1h 2m'. Short, and never shows a bare '0m' for a real trial."""
    seconds = int(max(0, seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return "%dh %02dm" % (hours, minutes)
    if minutes:
        return "%dm %02ds" % (minutes, secs)
    return "%ds" % secs


def _blank():
    return {"trials": 0, "seconds": 0.0, "maps": {}, "difficulties": {},
            "names": {}, "outcomes": {}, "longest": 0.0}


def _count(table, key):
    if key:
        table[key] = table.get(key, 0) + 1


def _top(table):
    return max(table.items(), key=lambda kv: kv[1]) if table else None


class Stats:
    def __init__(self, path=None):
        self.path = path or config.STATS_FILE
        self.total = _blank()
        self.session = _blank()
        self.first_seen = time.time()
        self._started_at = None
        self._current = None
        self.load()

    # -- persistence --------------------------------------------------------

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return                       # missing or corrupt, start clean
        if data.get("version") != FORMAT_VERSION:
            return
        stored = data.get("total")
        if isinstance(stored, dict):
            # Newer keys are simply absent from an older file.
            self.total = {**_blank(), **stored}
        self.first_seen = data.get("first_seen", self.first_seen)

    def save(self):
        if not config.TRACK_STATS:
            return
        payload = {"version": FORMAT_VERSION, "first_seen": self.first_seen,
                   "total": self.total}
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)   # atomic, never leaves a half file
        except OSError as exc:
            log.debug("Could not save stats: %s", exc)

    # -- recording ----------------------------------------------------------

    def _add(self, bucket, elapsed, result):
        bucket["trials"] += 1
        bucket["seconds"] += elapsed
        bucket["longest"] = max(bucket["longest"], elapsed)
        map_name, level, name = self._current
        _count(bucket["maps"], map_name)
        _count(bucket["difficulties"], level)
        _count(bucket["names"], name)
        _count(bucket["outcomes"], result or UNFINISHED)

    def trial_started(self, session):
        self._started_at = time.time()
        self._current = (session.trial_map, session.difficulty,
                         session.trial_name or session.trial_id)

    def trial_ended(self, result=None):
        if self._started_at is None:
            return
        elapsed = time.time() - self._started_at
        self._started_at = None
        if elapsed < MIN_TRIAL_SECONDS:
            self._current = None
            return
        self._add(self.total, elapsed, result)
        self._add(self.session, elapsed, result)
        self._current = None
        self.save()

    def observe(self, previous_phase, session, in_trial_phase):
        """Called after every state change while following the log live."""
        if not config.TRACK_STATS:
            return
        now_in_trial = session.game_phase == in_trial_phase
        was_in_trial = previous_phase == in_trial_phase
        if now_in_trial and not was_in_trial:
            self.trial_started(session)
        elif was_in_trial and not now_in_trial:
            self.trial_ended(session.trial_result)

    # -- reporting ----------------------------------------------------------

    @staticmethod
    def _outcomes(table):
        parts = []
        for key, count in sorted(table.items(), key=lambda kv: -kv[1]):
            label = strings.text("outcome_" + key) if strings.has("outcome_" + key) else key
            parts.append("%d %s" % (count, label))
        return ", ".join(parts)

    def _lines(self, bucket, title):
        if not bucket["trials"]:
            return []
        rows = ["  %s" % title,
                "    %-22s %s" % (strings.text("stat_trials"), bucket["trials"]),
                "    %-22s %s" % (strings.text("stat_time"),
                                  duration(bucket["seconds"]))]
        if bucket["longest"]:
            rows.append("    %-22s %s" % (strings.text("stat_longest"),
                                          duration(bucket["longest"])))
        if bucket["outcomes"]:
            rows.append("    %-22s %s" % (strings.text("stat_outcomes"),
                                          self._outcomes(bucket["outcomes"])))
        best = _top(bucket["maps"])
        if best:
            rows.append("    %-22s %s (%d)" % (strings.text("stat_favourite"),
                                               best[0], best[1]))
        best = _top(bucket["names"])
        if best:
            rows.append("    %-22s %s (%d)" % (strings.text("stat_favourite_trial"),
                                               best[0], best[1]))
        return rows

    def summary(self):
        rows = self._lines(self.session, strings.text("stat_session"))
        rows += self._lines(self.total, strings.text("stat_total"))
        return rows
