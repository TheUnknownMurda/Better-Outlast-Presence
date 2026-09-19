"""
Tweakable settings for Better Outlast Presence.

Everything a user might reasonably want to change lives here, so the rest of
the code never has to be touched. Most of these also have a command line
flag, which wins over the value set here.
"""

import os

_HERE = os.path.dirname(os.path.abspath(__file__))

# --- Discord ---------------------------------------------------------------

APP_ID = "1453685678012366878"

# Asset key uploaded to the Discord application. Used for the menu, the lobby
# and any trial whose artwork has not been uploaded yet.
DEFAULT_IMAGE = "murkoff"

# What Discord writes next to your name in member lists and profiles:
#   "name"    -> The Outlast Trials
#   "details" -> the first line of the presence, e.g. "Kill The Snitch"
#   "state"   -> the second line, e.g. "Police Station - Standard"
STATUS_DISPLAY = "name"

# Up to two buttons under the presence. Set to None to show none.
BUTTONS = [
    {"label": "Get this presence",
     "url": "https://github.com/TheUnknownMurda/Better-Outlast-Presence"},
]

# --- What the presence shows -----------------------------------------------

SHOW_ELAPSED_TIME = True     # the "XX:XX elapsed" counter
SHOW_PARTY_SIZE = True       # "(2 of 4)" during a trial
MAX_PARTY_SIZE = 4

SHOW_REGION = True           # the server region and ping, e.g. "US East (26 ms)"
SHOW_SEASON = True           # "Season 7" in the image tooltip
SHOW_PROGRAM = True          # "Invasion" or "Trial Maker" after the difficulty
SHOW_MENU_ACTIVITY = True    # "Customising their character" instead of "In the menu"

# Off by default: this is your in-game name, and the presence is public to
# everyone who can see your Discord profile.
SHOW_PLAYER_NAME = False

# --- Wording ---------------------------------------------------------------

# "auto" follows the language the game is running in. Otherwise force a code
# listed in strings.py, for example "en" or "fr".
LANGUAGE = "auto"

# Reword any single line without editing strings.py, e.g.
#   TEXT_OVERRIDES = {"lobby": "Chilling in the Sleep Room"}
TEXT_OVERRIDES = {}

# --- Statistics ------------------------------------------------------------

TRACK_STATS = True
STATS_FILE = os.path.join(_HERE, "stats.json")

# Trial ids seen in the log that we could not name are appended here, so you
# can fill them in later instead of having to catch the console message.
UNKNOWN_TRIALS_FILE = os.path.join(_HERE, "unknown_trials.txt")

# --- Game log --------------------------------------------------------------

LOG_PATH = os.path.join(
    os.getenv("LOCALAPPDATA", ""), "OPP", "Saved", "Logs", "OPP.log"
)

# --- Timing, in seconds ----------------------------------------------------

LOG_POLL_INTERVAL = 1.0      # how often new log lines are read while playing
LOG_POLL_MAX_INTERVAL = 3.0  # slowest poll, reached only when the log is silent
CLIENT_POLL_INTERVAL = 5.0   # how often we check whether the game was launched
RPC_MIN_INTERVAL = 2.0       # Discord silently drops bursts faster than ~5 / 20 s
RECONNECT_DELAY = 15.0       # wait between two Discord reconnection attempts

# --- Console ---------------------------------------------------------------

USE_COLOR = True
VERBOSE = False              # True -> also print every log line we matched
