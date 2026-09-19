"""
Better Outlast Presence - Discord Rich Presence for The Outlast Trials.

The game ships no presence API, so this reads the Unreal Engine log the game
writes to and reacts to the markers it contains. Run it in the background
while you play, or with --dry-run to see what it would publish.
"""

import argparse
import logging
import os
import sys
import time

import check
import config
import strings
from GameInfo import IN_TRIAL, GameInfo, parse_log_time
from presence import DryRunClient, PresenceClient
from stats import Stats, duration

log = logging.getLogger("outlast")

CLOSED_MARKER = "Log file closed"
TAIL_BYTES = 4096
MAX_ELAPSED = 24 * 3600  # longest believable "elapsed" reading


# --- console ---------------------------------------------------------------

_COLOURS = {"WARNING": "\033[33m", "ERROR": "\033[31m", "DEBUG": "\033[90m"}


class _Formatter(logging.Formatter):
    def __init__(self, colour):
        super().__init__("%(asctime)s  %(message)s", datefmt="%H:%M:%S")
        self.colour = colour

    def format(self, record):
        line = super().format(record)
        tint = _COLOURS.get(record.levelname) if self.colour else None
        return "%s%s\033[0m" % (tint, line) if tint else line


def setup_console():
    colour = config.USE_COLOR and sys.stdout.isatty()
    if colour and os.name == "nt":  # turn on ANSI escapes on the Windows console
        try:
            import ctypes
            kernel = ctypes.windll.kernel32
            kernel.SetConsoleMode(kernel.GetStdHandle(-11), 7)
        except Exception:
            colour = False
    try:  # trial names and the console code page do not always agree
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_Formatter(colour))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.DEBUG if config.VERBOSE else logging.INFO)


# --- log file helpers ------------------------------------------------------

def read_tail(path, size=TAIL_BYTES):
    """Last few KB of the log, or None if it is not readable.

    Reading the tail is O(1); loading the whole file just to look at its final
    line costs the same as replaying it.
    """
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - size))
            return f.read().decode("utf-8", "replace")
    except OSError:
        return None


def game_is_running(tail):
    """The game appends 'Log file closed' on exit, so a log ending with it is stale."""
    lines = [line for line in tail.splitlines() if line.strip()]
    return bool(lines) and CLOSED_MARKER not in lines[-1]


def clock_offset(path, tail):
    """Shift that maps the log's own clock onto real time.

    The log's newest line was written at the file's modification time, so
    anchoring the two turns every earlier timestamp into a real one. Only the
    distance between log lines is ever used, which means it does not matter
    whether Unreal stamps in local time or in UTC. Returns 0.0 if the log
    carries no usable timestamp; `clamp_start` catches that case.
    """
    stamps = [parse_log_time(line) for line in tail.splitlines()]
    stamps = [s for s in stamps if s is not None]
    if not stamps:
        return 0.0
    try:
        return os.path.getmtime(path) - stamps[-1]
    except OSError:
        return 0.0


def clamp_start(session):
    """Keep the elapsed counter believable if the log clock made no sense."""
    now = time.time()
    if not now - MAX_ELAPSED <= session.phase_started_at <= now:
        session.phase_started_at = now


def _rotated(f, path):
    """True once the game deletes or truncates the log for a new session."""
    try:
        return os.path.getsize(path) < f.tell()
    except OSError:
        return True


def tail_lines(f, path, on_idle):
    """Yield complete lines as the game writes them; return when the log rotates.

    The wait between reads grows while the log is silent and drops back to
    `LOG_POLL_INTERVAL` the moment anything is written. A running game writes
    constantly, so in practice the slow poll is only ever reached when the
    game is sitting still and nothing could be missed anyway.
    """
    buffer = ""
    idle = 0
    wait = config.LOG_POLL_INTERVAL
    while True:
        chunk = f.readline()
        if chunk:
            idle = 0
            wait = config.LOG_POLL_INTERVAL
            buffer += chunk
            if buffer.endswith("\n"):
                yield buffer
                buffer = ""
            continue
        if buffer and idle:  # the writer paused mid-line, take what we have
            yield buffer
            buffer = ""
        idle += 1
        on_idle()
        if _rotated(f, path):
            return
        time.sleep(wait)
        wait = min(wait * 1.5, config.LOG_POLL_MAX_INTERVAL)


# --- session ---------------------------------------------------------------

def announce(client, session):
    client.set(session.build_payload())
    log.info("%s", session)


def watch_session(client, path, tail, stats=None):
    """Follow one game session from launch to exit."""
    session = GameInfo()
    try:
        f = open(path, "r", encoding="utf-8", errors="replace")
    except OSError as exc:
        log.warning("Cannot read the log (%s)", exc)
        return

    with f:
        # Replay the history without touching Discord: only the final state
        # is worth publishing, and one RPC call per matching line would go
        # straight through Discord's rate limit and leave a stale phase up.
        # Nothing is recorded in the stats here either, or restarting the
        # tool would count trials that were already counted. Phase starts
        # are read from the lines' own clock, so the elapsed counter is
        # right even when the tool is launched mid-trial.
        session.clock_offset = clock_offset(path, tail)
        for line in f:
            session.consume(line)
        session.clock_offset = None
        if session.game_phase:
            clamp_start(session)
            announce(client, session)
        else:
            log.info("Game running, waiting for a phase change")

        for line in tail_lines(f, path, client.flush):
            if CLOSED_MARKER in line:
                log.info("Game closed")
                break
            if config.VERBOSE:
                log.debug("%s", line.rstrip())
            previous = session.game_phase
            if session.consume(line):
                if stats:
                    stats.observe(previous, session, IN_TRIAL)
                announce(client, session)

    if stats:
        stats.trial_ended()  # close a trial that was still running


def run(client, stats):
    waiting = False
    last_mtime = None
    while True:
        # While the game is shut the log never changes, so a single stat call
        # replaces re-reading and re-parsing its tail every few seconds.
        try:
            mtime = os.path.getmtime(config.LOG_PATH)
        except OSError:
            mtime = None
        if mtime is not None and mtime == last_mtime:
            client.flush()
            time.sleep(config.CLIENT_POLL_INTERVAL)
            continue
        last_mtime = mtime

        tail = read_tail(config.LOG_PATH) if mtime is not None else None
        if tail is None or not game_is_running(tail):
            client.clear()
            if not waiting:
                log.info("Waiting for The Outlast Trials to start")
                waiting = True
            client.flush()
            time.sleep(config.CLIENT_POLL_INTERVAL)
            continue

        waiting = False
        log.info("Game detected")
        watch_session(client, config.LOG_PATH, tail, stats)
        client.clear()


# --- entry point -----------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="Better Outlast Presence",
        description="Discord Rich Presence for The Outlast Trials.")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would be published, contact nobody")
    parser.add_argument("--stats", action="store_true",
                        help="print the play statistics and exit")
    parser.add_argument("--check", action="store_true",
                        help="audit the trial and language tables, then exit")
    parser.add_argument("--no-stats", action="store_true",
                        help="do not record play statistics this run")
    parser.add_argument("--language", metavar="CODE",
                        choices=["auto"] + strings.available(),
                        help="presence language (default: follow the game)")
    parser.add_argument("--log-path", metavar="PATH",
                        help="override where the game log is read from")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="also print every log line that was matched")
    return parser.parse_args(argv)


def apply_args(args):
    if args.verbose:
        config.VERBOSE = True
    if args.no_stats:
        config.TRACK_STATS = False
    if args.log_path:
        config.LOG_PATH = args.log_path
    if args.language:
        config.LANGUAGE = args.language
        if args.language != "auto":
            strings.set_language(args.language)


def report(stats):
    rows = stats.summary()
    if not rows:
        return
    log.info("")
    for row in rows:
        log.info("%s", row)


def main(argv=None):
    args = parse_args(argv)
    apply_args(args)
    setup_console()

    if args.check:
        return 1 if check.report(log) else 0

    stats = Stats()
    if args.stats:
        report(stats)
        if not stats.summary():
            log.info("No trials recorded yet")
        return 0

    log.info("Better Outlast Presence")
    log.info("Log: %s", config.LOG_PATH)
    if not os.getenv("LOCALAPPDATA") and not args.log_path:
        log.warning("LOCALAPPDATA is not set - edit LOG_PATH in config.py")
    if config.TRACK_STATS and stats.total["trials"]:
        log.info("Played %d trials so far, %s in trials",
                 stats.total["trials"], duration(stats.total["seconds"]))

    client = DryRunClient() if args.dry_run else PresenceClient()
    try:
        run(client, stats if config.TRACK_STATS else None)
    except KeyboardInterrupt:
        log.info("Stopping")
    finally:
        client.close()
        if config.TRACK_STATS:
            stats.trial_ended()
            report(stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
