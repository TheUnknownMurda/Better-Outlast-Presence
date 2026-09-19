"""Static game data: what the log strings mean, and how trial ids read out.

Everything here was read out of a captured OPP.log, the profile save or the
game's own session file; the README says what was checked against what.
"""

import re

# Substring found in a log line -> the event it announces. The first match on
# a line wins, so the specific markers come before the loose ones.
#
# Plain substring tests are used rather than one big alternation regex: over a
# 10 MB log the substring pass is roughly twenty times faster.
markers = {
    # phase changes
    "GameStageInfo changed": "stage_info",
    "GamePhase changed to ": "game_phase",
    "Level: /Game/Maps/Global/OPP_Persistent": "trial_world",
    "Level: /Game/Maps/Lobby/Lobby_Persistent": "lobby",
    "LoadMap: /Game/Maps/Global/MainMenu": "menu",
    "Find match request is searching": "matchmaking",
    "Loading screen : hiding": "loaded",
    "Source=Experiment": "trial_result",
    # context picked up along the way
    "Pushing menu page: ": "menu_push",
    "Popping menu page: ": "menu_pop",
    "matchmaking configuration name is: ": "build",
    "New Audio Language : ": "audio_language",
    "Player Init Replicated. Player Id = ": "player_init",
    "Keeping ": "region",
}

# The trial server's own state machine, as logged by
# "GamePhase changed to StageStarted from StageReady.", in the order it was
# seen. Everything before StageStarted is the intro: players load in and sit
# down in the wagon, and the stage is generated during the ride. The value is
# the strings.py key wording that stretch, None once the trial proper is on.
STAGE_STARTED = "StageStarted"
stage_phases = {
    "WaitingForPlayers": "waiting_players",
    "WaitingForPlayersSitting": "waiting_players",
    "LoadingStage": "wagon",
    "Populating": "wagon",
    "WaitingForClientsPopulate": "wagon",
    "StageReady": "wagon",
    STAGE_STARTED: None,
}

# "?Source=ExperimentFail" in the travel URL back to the sleep room, keyed by
# the word after "Experiment". Only the failure has been captured so far; the
# success spellings are guesses, which is why anything unlisted is kept as the
# game wrote it rather than being dropped.
trial_results = {
    "Fail": "failed",
    "Failed": "failed",
    "Success": "completed",
    "Succeeded": "completed",
    "Complete": "completed",
    "Completed": "completed",
}

# Menu widget name fragment -> the strings.py key describing what it is.
# Matched against the widget in "Pushing menu page: <Widget>_C_2147478701".
# Anything not listed here simply leaves the presence alone.
#
# The names are the widgets' own, not what is on screen, each checked by
# opening the screen with the tool running: "CharacterSheet" is the Terminal
# (trial, loadout, tasks, catalogs, store), "CustomizationMenu" the cell
# decoration, and "NPCMenu" every staff station alike (the Director,
# Prescriptions, Rigs, Amps) - the log never says which. Only the Director
# gives himself away, through the "EastermanDetailedMenu" sub page his
# records, badges, evidence and newspapers open.
menu_pages = {
    "SplashScreen": "page_splash",
    "CharacterSheet": "page_terminal",
    "CustomizationMenu": "page_customization",
    "EastermanDetailedMenu": "page_director",
    "NPCMenu": "page_staff",
    "Invasion": "page_invasion",
    "RewardMenu": "page_rewards",
    "LobbyNewsMenu": "page_news",
    "MenuTutorials": "page_tutorials",
    "SeasonalVideo": "page_season",
    "TwitchAccountLinking": "page_twitch",
}

# Pages whose wording is only a stand-in until a sub page says which station
# it is; the sub page's wording then sticks to them until they close.
placeholder_pages = {"NPCMenu"}

# The regions the game pings on startup, as they appear in
# "OnlineCoreLogs: Keeping us-east-1 - 26".
regions = {
    "us-east-1": "US East",
    "us-west-2": "US West",
    "eu-central-1": "Europe",
    "sa-east-1": "South America",
    "me-south-1": "Middle East",
    "ap-northeast-2": "Asia Northeast",
    "ap-southeast-1": "Asia Southeast",
    "ap-southeast-2": "Oceania",
}

# "Program ID: programCorePF" -> what to add to the presence. The Core
# programs are the ordinary trials and add nothing; the map already says which
# one. Ids without an entry are shown by their suffix, so a new program is
# visible without being mis-named.
#
# Ids present in the profile save but not yet worded, for whoever can check
# them against the game: programCHAIN, programPrime2, programStamps3,
# programWMirror, programWMirror2, programWMystery, programWMystery2,
# programWQuiet.
programs = {
    "programINVASION": "Invasion",
    "programCREATOR": "Trial Maker",
    "programChristmas2": "Christmas",
    "programChemical2": "Chemical Leak (Part II)",  # read off the screen, 2026-09-19
}

_PROGRAM_PREFIX = "program"
_CORE_PROGRAM = "programCore"


def program_label(program_id):
    """Wording for a program id, or None when there is nothing worth adding."""
    if not program_id or program_id.startswith(_CORE_PROGRAM):
        return None
    if program_id in programs:
        return programs[program_id]
    if program_id.startswith(_PROGRAM_PREFIX):
        return program_id[len(_PROGRAM_PREFIX):]
    return program_id


# "Stage: PrisonFarm" -> the map as the game names it. The stage ids are
# CamelCase versions of the display name, so anything not listed is split on
# its capitals, which is exact for every map name known so far.
stages = {
    "PrisonFarm": "Prison Farm",
    "PoliceStation": "Police Station",
    "TelevisionStudio": "Television Studio",
}

_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def stage_name(stage):
    if not stage:
        return None
    return stages.get(stage) or _CAMEL.sub(" ", stage)


# Trial id -> display name.
# Can be found from fmodel: OPP/Content/Text/Program_Trials.json
trial_names = {
    "FPB_MT01": "Punish the Miscreants",
    "CH_Trial": "Vindicate the Guilty",
    "PS_Trial": "Kill The Snitch",
    "OR_Trial": "Cleanse the Orphans",
    "FPB_MT02": "Open the Gates",
    "FP_Trial": "Grind the Bad Apples",
    "PSB_MT01": "Cancel the Autopsy",
    "PSB_MT02": "Sabotage the Lockdown",
    "TrialMansion": "WELCOME",
    "TrialRelease01": "FAREWELL",
    "ORS_MT01": "Feed the Children",
    "ORS_MT02": "Foster the Orphans",
    "PSO_MT01": "Release the prisoners",
    "FPC_MT01": "Drill the Futterman",
    "ORI_MT01": "Gather the Children of God",
    "CHA_MT01": "Escape the Courthouse",
    "CHA_MT02": "Destroy the Evidence",
    "TF_Trial": "Pervert the Futterman",
    "TFS_MT01": "Crush the Sex Toys",
    "TFS_MT02": "Incinerate the Sex Toys",
    "PSA_MT01": "Teach the Police Officer",
    "CHJ_MT01": "Tilt The Scales of Justice",
    "TFW_MT01": "Shutdown the Factory",
    "MH_Trial": "Poison the Medicine",
    "CHA_MT03": "Fuel the Release",
    "MHS_MT01": "Empty the Vault",
    "MHS_MT02": "Poison the Cattle",
    "PSB_MT03": "Eliminate the Past",
    "DT_Trial": "Pleasure the Prosecutor",
    "ORS_MT03": "Reunite the Family",
    "FPB_MT03": "Deface the Futtermans",
    "SR_Trial": "Liquidate the Union",
    "Escape_Amelia": "Unknown",
    "MHS_MT03": "Stash the Contraband",
    "MHS_MT04": "Cook the Informant",
    "DTS_MT01": "Kidnap the Mistress",
    "DTS_MT02": "Spread the Disease",
    "TrialRelease_AE": "ESCAPE",
    "TFS_MT03": "Fumigate the Factory",
    "FPC_MT02": "Redeem Your Freedom",
    "Trial_ComingSoon": "MORE COMING SOON...",
    "SRR_MT01": "Get Out the Vote",
    "SM_Trial": "Kill the politician",
    "CHJ_MT02": "Sentence the Prosecuted",
    "DTS_MT03": "Traffick the Product",
    "SRR_MT02": "Disrupt the neighborhood",
    "SMC_MT01": "Investigate the Minotaur",
    "FPI_MT01": "Beguile the Children",
    "RE_Trial": "Despoil the Auction",
    "TS_Trial": "Silence The Idol",  # read off the screen, 2026-09-19
    "PSO_MT02": "Seize the narcotics",
    "SMC_MT02": "Fabricate the Scandal",
    "ToyFactory": "Pervert the Futterman",  # the 45 min Toy Factory id
}

# Trial ids that the game definitely ships but whose display name we do not
# have. Found in Saved/SaveGames/Profile-*.sav, which stores the ids you have
# progression on but not their wording; PF_Trial was also seen live in the
# log, as the Prison Farm's own trial.
#
# The presence still works for these: the map comes from the log, so it
# reads "Prison Farm - Psychosurgery" instead of the trial name. Move an id up
# into trial_names as soon as you can read its real name, and `--check` will
# stop listing it.
known_trial_ids = {
    "AET_MT01",
    "FPI_MT02",
    "PF_Trial",
    "RES_MT01",
    "RES_MT02",
    "SRR_MT03",
    "TFW_MT02",
}

# First two characters of a trial id -> map name, for the trials whose
# "Stage:" was not logged (an older build, or a tool started mid-trial on a
# truncated log). Ids with no entry here simply show no map.
trial_maps = {
    "PS": "Police Station",
    "OR": "Orphanage",
    "FP": "Fun Park",
    "CH": "Courthouse",
    "TF": "Toy Factory",
    "MH": "Docks",
    "DT": "Downtown",
    "SR": "Suburbs",
    "SM": "Shopping Mall",
    "RE": "Resort",
    "TS": "Television Studio",
    "PF": "Prison Farm",
    "To": "Toy Factory",
}

# "Program difficulty: Insane" -> how the game names it on screen. The keys
# are the EProgramDifficulty enum values, also present in the save.
difficulty = {
    "Easy": "Introductory",
    "Normal": "Standard",
    "Hard": "Intensive",
    "Insane": "Psychosurgery",
}
