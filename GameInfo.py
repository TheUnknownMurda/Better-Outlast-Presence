"""Turns Outlast Trials log lines into the state shown on Discord."""

import logging
import re
import time
from datetime import datetime

import config
import strings
from game_constants import (STAGE_STARTED, difficulty, known_trial_ids, markers,
                            menu_pages, placeholder_pages, program_label,
                            regions, stage_name, stage_phases, stages,
                            trial_maps, trial_names, trial_results)

log = logging.getLogger(__name__)

MENU = "Menu"
LOBBY = "Lobby"
MATCHMAKING = "Matchmaking"
LOADING = "Loading trial"
INTRO = "Trial intro"       # in the trial world, but the doors are not open yet
IN_TRIAL = "In trial"

TRIAL_PHASES = (LOADING, INTRO, IN_TRIAL)
_OUT_OF_TRIAL = (MENU, LOBBY, MATCHMAKING)

# Tuple rather than a dict view: this is scanned once per log line.
_MARKERS = tuple(markers.items())

try:  # added in pypresence 4.6, older Discord clients ignore the field
    from pypresence import StatusDisplayType
    _STATUS_DISPLAY = getattr(StatusDisplayType,
                              str(config.STATUS_DISPLAY).upper(), StatusDisplayType.NAME)
except ImportError:  # pragma: no cover - depends on the installed version
    _STATUS_DISPLAY = None

# [2026.07.31-16.19.32:284][  0]LogLoad: ...
_LOG_TIME = re.compile(r"\[(\d{4})\.(\d{2})\.(\d{2})-(\d{2})\.(\d{2})\.(\d{2}):(\d{3})\]")
# "Selected matchmaking configuration name is: release-7-0-shipping-250521-hub"
_BUILD = re.compile(r"release-(\d+)-(\d+)")
# "Pushing menu page: CharacterSheet_C_2147478701"
_WIDGET_SUFFIX = re.compile(r"_C_\d+\s*$")
# "GamePhase changed to StageStarted from StageReady."
_GAME_PHASE = re.compile(r"GamePhase changed to (\w+)")
# "Player Id = 'Name' [7APhO] [<profile id>],  Player Slot = 0, IsLocallyControlled = Yes"
# Only the name is kept; the profile id after it never leaves this regex.
_PLAYER_INIT = re.compile(
    r"Player Id = (.+?) \[[^\]\s]+\] \[[0-9a-f-]{36}\],\s*"
    r"Player Slot = \d+, IsLocallyControlled = (Yes|No)")
# "...?Source=ExperimentFail?ProgramId=programCorePF?Stage=PrisonFarm..."
_TRIAL_RESULT = re.compile(r"Source=Experiment(\w+)")

_unknown_trials = set()
_unknown_phases = set()


def parse_log_time(line):
    """Epoch seconds for a log line's own timestamp, or None."""
    match = _LOG_TIME.match(line)
    if not match:
        return None
    year, month, day, hour, minute, second, ms = (int(g) for g in match.groups())
    try:
        stamp = datetime(year, month, day, hour, minute, second, ms * 1000)
    except ValueError:
        return None
    return stamp.timestamp()


def _field(line, key):
    """Read `key: value,` out of a log line without ever raising."""
    _, found, rest = line.partition(key)
    if not found:
        return None
    return rest.split(",", 1)[0].strip() or None


def _after(line, key):
    """Everything following `key`, trimmed of trailing punctuation."""
    _, found, rest = line.partition(key)
    if not found:
        return None
    return rest.strip().rstrip(".").strip() or None


def _page_key(widget):
    for fragment, key in menu_pages.items():
        if fragment in widget:
            return key
    return None


class GameInfo:
    def __init__(self):
        # where the player is
        self.game_phase = None
        self.stage_phase = None       # the trial server's own phase, see stage_phases
        self.activity = None          # strings.py key for a menu sub page
        self._pages = []              # open menu pages as [widget, key], innermost last
        self.phase_started_at = time.time()
        # While an existing log is replayed, the shift from its clock to real
        # time, so phase starts are taken from the lines themselves. None
        # means lines arrive as the game writes them.
        self.clock_offset = None
        # what they are playing
        self.trial_id = None
        self.trial_name = None
        self.trial_map = None
        self.difficulty = None
        self.program = None           # wording for a non-standard program
        self.player_count = None
        self.trial_result = None      # "failed" / "completed", set as it ends
        self.large_image = config.DEFAULT_IMAGE
        # picked up along the way
        self.region = None
        self.ping = None
        self.season = None
        self.player_name = None

    def __str__(self):
        if self.game_phase in TRIAL_PHASES:
            parts = [self.trial_name or self.trial_id,
                     self.trial_map, self.difficulty, self.program]
            if self.game_phase == INTRO:
                parts.append(self._stage_text() or self.stage_phase)
            if self.player_count:
                parts.append("%d player(s)" % self.player_count)
            detail = " | ".join(p for p in parts if p)
            return "%s%s" % (self.game_phase, ": %s" % detail if detail else "")
        detail = strings.text(self.activity) if self.activity else None
        return "%s%s" % (self.game_phase or "Unknown",
                         ": %s" % detail if detail else "")

    # -- log parsing --------------------------------------------------------

    def consume(self, line):
        """Feed one log line. Returns True when the presence has to change."""
        for marker, event in _MARKERS:
            if marker in line:
                return self._HANDLERS[event](self, line)
        return False

    def _read_stage_info(self, line):
        # RB:  GameStageInfo changed. Program ID: programCorePF, Trial ID: PF_Trial,
        #      Program difficulty: Insane, Stage: PrisonFarm, Mission: PF_Trial,
        #      Seed: 594594, EffectiveNumberOfPlayers: 1
        trial_id = _field(line, "Mission:") or _field(line, "Trial ID:")
        raw_difficulty = _field(line, "difficulty:")
        players = (_field(line, "EffectiveNumberOfPlayers:")
                   or _field(line, "Players:"))
        stage = _field(line, "Stage:")
        program = _field(line, "Program ID:")

        changed = False
        if stage:
            # The log's own map name beats the id prefix, which is a fallback
            # for logs that do not carry it.
            map_name = stages.get(stage) or trial_maps.get((trial_id or "")[:2]) \
                or stage_name(stage)
        else:
            map_name = trial_maps.get(trial_id[:2]) if trial_id else self.trial_map
        if map_name != self.trial_map:
            self.trial_map = map_name
            changed = True

        if trial_id and trial_id != self.trial_id:
            self.trial_id = trial_id
            self.trial_name = trial_names.get(trial_id)
            self.trial_result = None
            # Only claim artwork we can actually name, otherwise the previous
            # trial image would stay on screen.
            self.large_image = trial_id.lower() if self.trial_name else config.DEFAULT_IMAGE
            if not self.trial_name:
                self._note_unnamed(trial_id)
            changed = True

        if raw_difficulty:
            level = difficulty.get(raw_difficulty, raw_difficulty)
            changed |= level != self.difficulty
            self.difficulty = level
        if program:
            label = program_label(program)
            changed |= label != self.program
            self.program = label
        if players and players.isdigit():
            count = int(players)
            changed |= count != self.player_count
            self.player_count = count

        if self.game_phase not in TRIAL_PHASES:
            self._set_phase(LOADING, line)
            return True
        return changed

    def _note_unnamed(self, trial_id):
        """Remember a trial we could not name, once per run, and on disk.

        You are usually mid-trial when this happens and will never see the
        console, so it is also appended to a file you can read afterwards.
        """
        if trial_id in _unknown_trials:
            return
        _unknown_trials.add(trial_id)
        if trial_id in known_trial_ids:
            log.info("Trial %s has no name yet - showing the map instead", trial_id)
        else:
            log.warning("Unknown trial id %r - please add it to game_constants.py",
                        trial_id)
        try:
            with open(config.UNKNOWN_TRIALS_FILE, "a", encoding="utf-8") as f:
                f.write("%s\t%s\t%s\n" % (
                    time.strftime("%Y-%m-%d %H:%M"), trial_id,
                    self.trial_map or "unknown map"))
        except OSError:
            pass

    def _read_game_phase(self, line):
        match = _GAME_PHASE.search(line)
        if not match:
            return False
        phase = match.group(1)
        if phase not in stage_phases and phase not in _unknown_phases:
            _unknown_phases.add(phase)
            log.info("Unknown game phase %r - the presence keeps its current "
                     "wording", phase)
        before = self._stage_text()
        self.stage_phase = phase
        if phase == STAGE_STARTED:
            return self._set_phase(IN_TRIAL, line)
        if self.game_phase not in TRIAL_PHASES:
            # The trial server is up whether or not its welcome line was seen.
            return self._set_phase(LOADING, line)
        if self.game_phase == INTRO:
            return self._stage_text() != before
        return False

    def _enter_trial_world(self, line):
        if self.game_phase in TRIAL_PHASES:
            return False
        return self._set_phase(LOADING, line)

    def _read_loaded(self, line):
        # The loading screen dropping is the moment the player actually sees
        # the trial world. Whether that is the intro or the trial itself
        # depends on how far the server has got; with no phase logged at all
        # the trial is assumed to be on, as older builds behaved.
        if self.game_phase != LOADING:
            return False
        if self.stage_phase is None or self.stage_phase == STAGE_STARTED:
            return self._set_phase(IN_TRIAL, line)
        return self._set_phase(INTRO, line)

    def _read_lobby(self, line):
        return self._set_phase(LOBBY, line)

    def _read_menu(self, line):
        return self._set_phase(MENU, line)

    def _read_matchmaking(self, line):
        if self.game_phase in TRIAL_PHASES:
            return False           # stale line, we are already playing
        return self._set_phase(MATCHMAKING, line)

    def _read_trial_result(self, line):
        match = _TRIAL_RESULT.search(line)
        if not match:
            return False
        raw = match.group(1)
        result = trial_results.get(raw, raw.lower())
        if result == self.trial_result:
            return False           # the travel URL is logged twice
        self.trial_result = result
        log.info("Trial %s: %s", self.trial_name or self.trial_id or "", result)
        return False               # the phase change that follows redraws

    def _read_menu_push(self, line):
        widget = _after(line, "Pushing menu page: ")
        if not widget:
            return False
        widget = _WIDGET_SUFFIX.sub("", widget)
        key = _page_key(widget)
        # A sub page can say which station a generic one is: the wording then
        # outlives the sub page, so closing the Director's records does not
        # demote him back to "staff".
        if key and self._pages and self._pages[-1][0] in placeholder_pages:
            self._pages[-1][1] = key
        self._pages.append([widget, key])
        return self._refresh_activity()

    def _read_menu_pop(self, line):
        widget = _after(line, "Popping menu page: ")
        if not widget:
            return False
        widget = _WIDGET_SUFFIX.sub("", widget)
        for index in range(len(self._pages) - 1, -1, -1):
            if self._pages[index][0] == widget:
                del self._pages[index]
                break
        return self._refresh_activity()

    def _refresh_activity(self):
        """The activity is the innermost open page we have wording for."""
        key = None
        for _, page_key in reversed(self._pages):
            if page_key:
                key = page_key
                break
        if key == self.activity:
            return False
        self.activity = key
        return config.SHOW_MENU_ACTIVITY and self.game_phase in (MENU, LOBBY)

    def _read_region(self, line):
        value = _after(line, "Keeping ")
        if not value or " - " not in value:
            return False
        name, _, ping = value.partition(" - ")
        name = name.strip()
        if name not in regions:
            return False
        region = regions[name]
        latency = int(ping) if ping.strip().isdigit() else None
        if (region, latency) == (self.region, self.ping):
            return False        # the game re-pings; do not redraw for nothing
        self.region = region
        self.ping = latency
        return config.SHOW_REGION and self.game_phase is not None

    def _read_build(self, line):
        value = _after(line, "matchmaking configuration name is: ")
        match = _BUILD.search(value or "")
        if not match:
            return False
        season = int(match.group(1))
        if season == self.season:
            return False
        self.season = season
        return config.SHOW_SEASON and self.game_phase is not None

    def _read_language(self, line):
        value = _after(line, "New Audio Language : ")
        if not value or config.LANGUAGE != "auto":
            return False
        before = strings.language()
        return strings.set_language(value) != before

    def _read_player_init(self, line):
        # Every player in the room is logged this way; only the local one is
        # ours. The sleep room's "reflection capture" lines name the other
        # players' rooms as well, which is why they are not used.
        match = _PLAYER_INIT.search(line)
        if not match or match.group(2) != "Yes":
            return False
        name = match.group(1).strip().strip("'").strip()
        if not name or name == "[NULL]" or name == self.player_name:
            return False
        self.player_name = name
        return config.SHOW_PLAYER_NAME and self.game_phase is not None

    _HANDLERS = {
        "stage_info": _read_stage_info,
        "game_phase": _read_game_phase,
        "trial_world": _enter_trial_world,
        "loaded": _read_loaded,
        "lobby": _read_lobby,
        "menu": _read_menu,
        "matchmaking": _read_matchmaking,
        "trial_result": _read_trial_result,
        "menu_push": _read_menu_push,
        "menu_pop": _read_menu_pop,
        "region": _read_region,
        "build": _read_build,
        "audio_language": _read_language,
        "player_init": _read_player_init,
    }

    def _now(self, line):
        """When this line happened: its own clock while replaying, else now."""
        if self.clock_offset is not None:
            stamp = parse_log_time(line)
            if stamp is not None:
                return stamp + self.clock_offset
        return time.time()

    def _set_phase(self, phase, line):
        if phase == self.game_phase:
            return False
        self.game_phase = phase
        self.phase_started_at = self._now(line)
        # Every phase change is a new world, and its menu pages go with it.
        self._pages = []
        self.activity = None
        if phase in _OUT_OF_TRIAL:
            self._forget_trial()
        return True

    def _forget_trial(self):
        # trial_result is kept on purpose: the statistics read it once the
        # lobby is back, which is after this has run.
        self.stage_phase = None
        self.trial_id = None
        self.trial_name = None
        self.trial_map = None
        self.difficulty = None
        self.program = None
        self.player_count = None
        self.large_image = config.DEFAULT_IMAGE

    # -- Discord payload ----------------------------------------------------

    def _party(self):
        if not (config.SHOW_PARTY_SIZE and self.player_count):
            return None
        return [self.player_count, max(self.player_count, config.MAX_PARTY_SIZE)]

    def _server(self):
        if not (config.SHOW_REGION and self.region):
            return None
        if self.ping is None:
            return self.region
        return strings.text("ping", region=self.region, ping=self.ping)

    def _trial_lines(self):
        """(details, state, leftover): the trial's facts, each written once.

        Line 1 is the trial. Line 2 takes the two most telling of program,
        difficulty and map, in that order of preference, written in reading
        order; the map is the one to drop since the artwork already shows it.
        Whatever is left over goes into the artwork tooltip.
        """
        program = self.program if config.SHOW_PROGRAM else None
        facts = [f for f in (program, self.difficulty, self.trial_map) if f]
        if self.trial_name:
            details = self.trial_name
        elif self.trial_map:
            details = self.trial_map
            facts.remove(self.trial_map)
        else:
            details = strings.text("in_trial")
        shown, leftover = facts[:2], facts[2:]
        state = " - ".join(f for f in (program, self.trial_map, self.difficulty)
                           if f in shown) or None
        return details, state, leftover

    def _stage_text(self):
        key = stage_phases.get(self.stage_phase)
        return strings.text(key) if key else None

    def _hover(self, leftover=()):
        """Tooltip of the large image: what the two lines could not fit."""
        parts = list(leftover) or [strings.text("game")]
        if config.SHOW_SEASON and self.season:
            parts.append(strings.text("season", number=self.season))
        if config.SHOW_PLAYER_NAME and self.player_name:
            parts.append(self.player_name)
        return " - ".join(parts)

    def build_payload(self):
        """The kwargs for Presence.update(), or None when nothing is known yet."""
        if self.game_phase is None:
            return None

        payload = {
            "large_image": self.large_image,
            "large_text": self._hover(),
            "status_display_type": _STATUS_DISPLAY,
        }
        if config.SHOW_ELAPSED_TIME:
            payload["start"] = int(self.phase_started_at)
        if config.BUTTONS:
            payload["buttons"] = config.BUTTONS

        if self.game_phase in (MENU, LOBBY):
            default = "menu" if self.game_phase == MENU else "lobby"
            payload["details"] = strings.text(self.activity or default)
            payload["state"] = self._server()

        elif self.game_phase == MATCHMAKING:
            payload["details"] = strings.text("matchmaking")
            payload["state"] = self._server()
            payload["small_image"] = config.DEFAULT_IMAGE
            payload["small_text"] = strings.text("brand")

        elif self.game_phase == LOADING:
            details, state, _ = self._trial_lines()
            payload["details"] = strings.text("loading")
            # Nothing is known until the server says what it is running, and
            # "Unknown trial" would only flash for a second before it does.
            if not self.trial_id:
                payload["state"] = None
            elif self.trial_name or self.trial_map:
                payload["state"] = details
            else:
                payload["state"] = strings.text("unknown_trial")
            payload["small_image"] = config.DEFAULT_IMAGE
            payload["small_text"] = state or strings.text("brand")
            payload.pop("start", None)  # a loading screen stopwatch is just noise

        elif self.game_phase == INTRO:
            # Line 2 says what the wagon is doing, so the trial facts move to
            # the small image until the doors open.
            details, state, leftover = self._trial_lines()
            payload["details"] = details
            payload["state"] = self._stage_text()
            payload["large_text"] = self._hover(leftover)
            payload["small_image"] = config.DEFAULT_IMAGE
            payload["small_text"] = state or self._server() or strings.text("brand")
            self._add_party(payload)

        elif self.game_phase == IN_TRIAL:
            details, state, leftover = self._trial_lines()
            payload["details"] = details
            payload["state"] = state
            payload["large_text"] = self._hover(leftover)
            payload["small_image"] = config.DEFAULT_IMAGE
            payload["small_text"] = self._server() or strings.text("brand")
            self._add_party(payload)

        return payload

    def _add_party(self, payload):
        party = self._party()
        if party:
            payload["party_id"] = "otp-trial"
            payload["party_size"] = party
