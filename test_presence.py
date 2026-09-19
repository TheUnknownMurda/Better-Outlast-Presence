"""Replays a scrubbed session through GameInfo and checks what Discord gets.

Run with `python -m unittest` (or `python test_presence.py`). Nothing here
touches Discord or the game; the lines below are real log lines with every
identifier swapped for a fake one.
"""

import json
import logging
import os
import re
import tempfile
import unittest

import check
import config
import strings
from GameInfo import (IN_TRIAL, INTRO, LOADING, LOBBY, MATCHMAKING, MENU,
                      GameInfo, parse_log_time)
from stats import Stats

# Every kind of secret the log carries. A payload must never contain one.
STEAM_ID = "76561190000000001"
PROFILE = "12345678-abcd-4ef0-9876-0123456789ab"
SESSION = "psess-0b88b4f4-d1c4-4a74-aa51-000000000000"
SERVER_IP = "203.0.113.42"
FRIEND = "OtherReagent"
SECRETS = (STEAM_ID, PROFILE, SESSION, SERVER_IP, FRIEND, "EncryptionToken")

T = "[2026.08.26-04.%s][%3d]"


def line(clock, frame, text):
    return "%s%s\n" % (T % (clock, frame), text)


STAGE_INFO = ("RB:  GameStageInfo changed. Program ID: programCorePS, Trial ID: PS_Trial, "
              "Program difficulty: Normal, Stage: PoliceStation, Mission: PS_Trial, "
              "Seed: 395395, EffectiveNumberOfPlayers: 3")

LOCAL_PLAYER = ("RB:  [local] Player Init Replicated. Player Id = 'Reagent One' [7APhO] "
                "[%s],  Player Slot = 0, IsLocallyControlled = Yes " % PROFILE)
REMOTE_PLAYER = ("RB:  [%s] Player Init Replicated. Player Id = %s [yy9NW] "
                 "[%s],  Player Slot = 9, IsLocallyControlled = No " % (FRIEND, FRIEND, PROFILE))

SESSION_LOG = [
    line("22.56:976", 0, "LogLoad: LoadMap: /Game/Maps/Global/MainMenu?Name=Player"),
    line("23.04:000", 0, "LogOnline: Steam ID %s logged in" % STEAM_ID),
    line("23.29:634", 0, "RB:  Pushing menu page: SplashScreen_C_2147482250"),
    line("23.29:700", 0, "RB: Display: New Audio Language : English"),
    line("24.43:181", 681, "RB:  Popping menu page: SplashScreen_C_2147482250"),
    line("24.43:186", 681, "RB:  Pushing menu page: MainMenu_C_2147482250"),
    line("24.46:302", 9, "RB:  Popping menu page: MainMenu_C_2147482250"),
    line("24.46:450", 25, "OnlineCoreLogs: Display: Selected matchmaking configuration name is: release-7-0-shipping-250521-hub"),
    line("24.46:500", 25, "OnlineCoreLogs: Keeping us-east-1 - 31"),
    line("24.49:028", 316, "OnlineCoreLogs: Find match request is searching."),
    line("24.51:049", 516, "LogNet: Browse: %s:7782/Game/Maps/Global/MainMenu?PlayerSessionId=%s?EncryptionToken=abc?Source=MainMenu" % (SERVER_IP, SESSION)),
    line("24.52:794", 682, "LogNet: Welcomed by server (Level: /Game/Maps/Lobby/Lobby_Persistent, Game: /Game/Systems/Global/RBLobbyGameMode_BP.RBLobbyGameMode_BP_C)"),
    line("24.52:794", 682, "LogLoad: LoadMap: %s:7782/Game/Maps/Lobby/Lobby_Persistent?PlayerSessionId=%s?Source=MainMenu" % (SERVER_IP, SESSION)),
    line("25.03:000", 145, "RB:  Updating room reflection capture for '%s'." % FRIEND),
    line("25.03:100", 145, REMOTE_PLAYER),
    line("25.03:200", 145, LOCAL_PLAYER),
    line("25.04:481", 145, "RB:  Loading screen : hiding."),
    line("27.41:748", 574, "RB:  Pushing menu page: CharacterSheet_C_2147478701"),
    line("28.09:296", 628, "RB:  Pushing menu page: InvasionTutorialVideoMenuWidget_C_2147478000"),
    line("28.17:773", 69, "RB:  Popping menu page: InvasionTutorialVideoMenuWidget_C_2147478000"),
    line("29.13:151", 492, "RB:  Popping menu page: CharacterSheet_C_2147478701"),
    line("29.20:410", 987, "OnlineCoreLogs: Find match request is searching."),
    line("29.28:789", 638, "LogNet: Welcomed by server (Level: /Game/Maps/Global/OPP_Persistent, Game: /Game/Systems/Global/RBDefaultGameMode_BP.RBDefaultGameMode_BP_C)"),
    line("29.30:204", 669, "RB:  GamePhase changed to WaitingForPlayers from None."),
    line("29.30:204", 669, STAGE_INFO),
    line("29.32:852", 757, "RB:  Loading screen : hiding."),
    line("29.43:815", 461, "RB:  GamePhase changed to WaitingForPlayersSitting from WaitingForPlayers."),
    line("29.47:469", 658, "RB:  Pushing menu page: Client_InGameMenu_C_2147472662"),
    line("29.54:325", 248, "RB:  GamePhase changed to LoadingStage from WaitingForPlayersSitting."),
    line("30.11:176", 439, "RB:  GamePhase changed to Populating from LoadingStage."),
    line("30.46:188", 728, "RB:  GamePhase changed to WaitingForClientsPopulate from Populating."),
    line("30.58:214", 453, "RB:  GamePhase changed to StageReady from WaitingForClientsPopulate."),
    line("31.07:074", 61, "RB:  GamePhase changed to StageStarted from StageReady."),
    line("45.50:997", 814, "OnlineCoreLogs: Find match request is searching."),
    line("45.53:247", 909, "LogNet: Browse: %s:7781/Game/Maps/Global/MainMenu?PlayerSessionId=%s?EncryptionToken=abc?Source=ExperimentFail?ProgramId=programCorePS?Stage=PoliceStation?Trial=PS_Trial" % (SERVER_IP, SESSION)),
    line("45.54:924", 977, "LogNet: Welcomed by server (Level: /Game/Maps/Lobby/Lobby_Persistent, Game: /Game/Systems/Global/RBLobbyGameMode_BP.RBLobbyGameMode_BP_C)"),
    line("45.54:933", 977, "LogLoad: LoadMap: %s:7781/Game/Maps/Lobby/Lobby_Persistent?PlayerSessionId=%s?Source=ExperimentFail?ProgramId=programCorePS?Stage=PoliceStation?Trial=PS_Trial" % (SERVER_IP, SESSION)),
    line("46.06:720", 463, "RB:  Loading screen : hiding."),
    line("46.14:996", 686, "LogLoad: LoadMap: /Game/Maps/Global/MainMenu"),
]


def replay(lines, session=None):
    """Feed lines and return (session, [(phase, payload) at each change])."""
    session = session or GameInfo()
    changes = []
    for text in lines:
        if session.consume(text):
            changes.append((session.game_phase, session.build_payload()))
    return session, changes


def flatten(payload):
    return json.dumps(payload, default=str)


class Quiet(unittest.TestCase):
    """Fixed settings, whatever config.py says on this machine."""

    def setUp(self):
        self._saved = {k: getattr(config, k) for k in (
            "SHOW_PLAYER_NAME", "SHOW_MENU_ACTIVITY", "SHOW_REGION", "SHOW_SEASON",
            "SHOW_PROGRAM", "SHOW_PARTY_SIZE", "SHOW_ELAPSED_TIME", "LANGUAGE",
            "TEXT_OVERRIDES", "UNKNOWN_TRIALS_FILE", "TRACK_STATS")}
        config.SHOW_PLAYER_NAME = True
        config.SHOW_MENU_ACTIVITY = True
        config.SHOW_REGION = True
        config.SHOW_SEASON = True
        config.SHOW_PROGRAM = True
        config.SHOW_PARTY_SIZE = True
        config.SHOW_ELAPSED_TIME = True
        config.LANGUAGE = "auto"
        config.TEXT_OVERRIDES = {}
        config.UNKNOWN_TRIALS_FILE = os.devnull
        config.TRACK_STATS = True
        strings.set_language("en")
        logging.disable(logging.CRITICAL)   # the parser's own warnings are expected

    def tearDown(self):
        logging.disable(logging.NOTSET)
        for key, value in self._saved.items():
            setattr(config, key, value)
        strings.set_language("en")


class PhaseFlow(Quiet):
    def test_phases_follow_the_session(self):
        _, changes = replay(SESSION_LOG)
        phases = [phase for phase, _ in changes]
        # Collapse repeats: only the order of phases matters here.
        order = [p for i, p in enumerate(phases) if i == 0 or phases[i - 1] != p]
        self.assertEqual(order, [MENU, MATCHMAKING, LOBBY, MATCHMAKING, LOADING,
                                 INTRO, IN_TRIAL, LOBBY, MENU])

    def test_trial_details(self):
        session, changes = replay(SESSION_LOG)
        in_trial = [p for phase, p in changes if phase == IN_TRIAL][0]
        self.assertEqual(in_trial["details"], "Kill The Snitch")
        self.assertEqual(in_trial["state"], "Police Station - Standard")
        self.assertEqual(in_trial["party_size"], [3, 4])
        self.assertEqual(in_trial["large_image"], "ps_trial")
        self.assertEqual(in_trial["small_text"], "US East (31 ms)")
        self.assertIn("Season 7", in_trial["large_text"])
        self.assertIn("Reagent One", in_trial["large_text"])

    def test_intro_is_worded_before_the_trial_starts(self):
        _, changes = replay(SESSION_LOG)
        intro = [p["state"] for phase, p in changes if phase == INTRO]
        self.assertEqual(intro, ["Waiting for players", "Heading to the trial"])
        loading = [p for phase, p in changes if phase == LOADING]
        self.assertIsNone(loading[0]["state"])       # nothing known yet
        self.assertEqual(loading[-1]["state"], "Kill The Snitch")
        self.assertNotIn("start", loading[-1])

    def test_trial_result_is_read_from_the_travel_url(self):
        session, _ = replay(SESSION_LOG)
        self.assertEqual(session.trial_result, "failed")

    def test_stage_named_by_the_log_wins_over_the_prefix(self):
        session, _ = replay([
            line("00.00:000", 0, "RB:  GameStageInfo changed. Program ID: programCorePF, "
                 "Trial ID: PF_Trial, Program difficulty: Insane, Stage: PrisonFarm, "
                 "Mission: PF_Trial, Seed: 1, EffectiveNumberOfPlayers: 1")])
        self.assertEqual(session.trial_map, "Prison Farm")
        self.assertEqual(session.difficulty, "Psychosurgery")
        self.assertIsNone(session.trial_name)
        self.assertEqual(session.large_image, config.DEFAULT_IMAGE)
        session.consume(line("00.01:000", 0, "RB:  GamePhase changed to StageStarted from StageReady."))
        payload = session.build_payload()
        self.assertEqual(payload["details"], "Prison Farm")   # the map stands in for the name
        self.assertEqual(payload["state"], "Psychosurgery")

    def test_unknown_stage_is_split_on_capitals(self):
        session, _ = replay([
            line("00.00:000", 0, "RB:  GameStageInfo changed. Program ID: programINVASION, "
                 "Trial ID: XX_MT09, Program difficulty: Hard, Stage: TelevisionStudio, "
                 "Mission: XX_MT09, Seed: 1, EffectiveNumberOfPlayers: 4")])
        self.assertEqual(session.trial_map, "Television Studio")
        self.assertEqual(session.program, "Invasion")
        session.consume(line("00.01:000", 0, "RB:  GamePhase changed to StageStarted from StageReady."))
        payload = session.build_payload()
        self.assertEqual(payload["details"], "Television Studio")
        self.assertEqual(payload["state"], "Invasion - Intensive")

    def test_special_program_pushes_the_map_into_the_tooltip(self):
        session, _ = replay([
            line("00.00:000", 0, "RB:  GameStageInfo changed. Program ID: programChemical2, "
                 "Trial ID: TS_Trial, Program difficulty: Insane, Stage: TelevisionStudio, "
                 "Mission: TS_Trial, Seed: 1, EffectiveNumberOfPlayers: 1"),
            line("00.01:000", 0, "RB:  GamePhase changed to StageStarted from StageReady."),
        ])
        payload = session.build_payload()
        self.assertEqual(payload["details"], "Silence The Idol")
        self.assertEqual(payload["state"], "Chemical Leak (Part II) - Psychosurgery")
        self.assertTrue(payload["large_text"].startswith("Television Studio"))

    def test_no_fact_is_written_twice(self):
        for program, trial, stage in (("programChemical2", "TS_Trial", "TelevisionStudio"),
                                      ("programCorePS", "PS_Trial", "PoliceStation"),
                                      ("programCorePF", "PF_Trial", "PrisonFarm"),
                                      ("programINVASION", "XX_MT09", "Docks")):
            session, _ = replay([
                line("00.00:000", 0, "RB:  GameStageInfo changed. Program ID: %s, Trial ID: %s, "
                     "Program difficulty: Insane, Stage: %s, Mission: %s, Seed: 1, "
                     "EffectiveNumberOfPlayers: 2" % (program, trial, stage, trial)),
                line("00.01:000", 0, "RB:  GamePhase changed to WaitingForPlayers from None."),
                line("00.02:000", 0, "RB:  Loading screen : hiding."),
            ])
            for _ in range(2):        # once in the intro, once in the trial
                payload = session.build_payload()
                fields = [payload[k] for k in ("details", "state", "large_text", "small_text")
                          if payload.get(k)]
                for fact in (session.trial_name, session.trial_map, session.difficulty,
                             session.program):
                    if fact:
                        hits = sum(fact in field for field in fields)
                        self.assertEqual(hits, 1, "%r appears %d times in %r" % (fact, hits, fields))
                session.consume(line("00.03:000", 0, "RB:  GamePhase changed to StageStarted from StageReady."))

    def test_stage_started_without_a_loading_screen_line(self):
        session, _ = replay([
            line("00.00:000", 0, "OnlineCoreLogs: Find match request is searching."),
            line("00.01:000", 0, "RB:  GamePhase changed to StageStarted from StageReady."),
        ])
        self.assertEqual(session.game_phase, IN_TRIAL)

    def test_loading_screen_alone_still_means_in_trial(self):
        # An older build that never logs GamePhase behaves like before.
        session, _ = replay([
            line("00.00:000", 0, STAGE_INFO),
            line("00.01:000", 0, "RB:  Loading screen : hiding."),
        ])
        self.assertEqual(session.game_phase, IN_TRIAL)

    def test_stale_matchmaking_line_does_not_leave_the_trial(self):
        session, _ = replay(SESSION_LOG[:33])
        self.assertEqual(session.game_phase, IN_TRIAL)
        session.consume(line("40.00:000", 0, "OnlineCoreLogs: Find match request is searching."))
        self.assertEqual(session.game_phase, IN_TRIAL)


class MenuPages(Quiet):
    def test_nested_pages_restore_the_outer_one(self):
        session, changes = replay(SESSION_LOG[:21])
        details = [p["details"] for phase, p in changes if phase == LOBBY]
        self.assertEqual(details[-4:], [
            "At the Terminal", "Browsing Invasion",
            "At the Terminal", "In the Sleep Room"])

    def test_title_screen_then_main_menu(self):
        _, changes = replay(SESSION_LOG[:7])
        details = [p["details"] for _, p in changes]
        self.assertEqual(details, ["In the main menu", "At the title screen",
                                   "In the main menu"])

    def test_staff_and_customisation_pages(self):
        session, _ = replay(SESSION_LOG[:17])
        session.consume(line("26.00:000", 0, "RB:  Pushing menu page: NPCMenu_C_2147478477"))
        self.assertEqual(session.build_payload()["details"], "With the Murkoff staff")
        session.consume(line("26.05:000", 0, "RB:  Popping menu page: NPCMenu_C_2147478477"))
        session.consume(line("26.10:000", 0, "RB:  Pushing menu page: CustomizationMenu_C_2147478000"))
        self.assertEqual(session.build_payload()["details"], "In the customisation menu")

    def test_the_director_is_recognised_and_remembered(self):
        session, _ = replay(SESSION_LOG[:17])
        steps = [
            ("Pushing menu page: NPCMenu_C_2147426211", "With the Murkoff staff"),
            ("Pushing menu page: EastermanDetailedMenu_C_2147425979", "With the Director"),
            ("Popping menu page: EastermanDetailedMenu_C_2147425979", "With the Director"),
            ("Popping menu page: NPCMenu_C_2147426211", "In the Sleep Room"),
            ("Pushing menu page: NPCMenu_C_2147424588", "With the Murkoff staff"),
        ]
        for i, (text, expected) in enumerate(steps):
            session.consume(line("27.%02d:000" % i, 0, "RB:  " + text))
            self.assertEqual(session.build_payload()["details"], expected, text)

    def test_menu_activity_can_be_switched_off(self):
        config.SHOW_MENU_ACTIVITY = False
        _, changes = replay(SESSION_LOG[:21])
        self.assertTrue(all(p["details"] in ("In the main menu", "In the Sleep Room",
                                             "Looking for a trial")
                            for _, p in changes))


class Identity(Quiet):
    def test_only_the_local_player_is_named(self):
        session, _ = replay(SESSION_LOG)
        self.assertEqual(session.player_name, "Reagent One")

    def test_player_name_is_off_by_default(self):
        config.SHOW_PLAYER_NAME = False
        _, changes = replay(SESSION_LOG)
        for _, payload in changes:
            self.assertNotIn("Reagent One", flatten(payload))

    def test_no_secret_ever_reaches_a_payload(self):
        _, changes = replay(SESSION_LOG)
        self.assertTrue(changes)
        for _, payload in changes:
            text = flatten(payload)
            for secret in SECRETS:
                self.assertNotIn(secret, text)
            self.assertIsNone(re.search(r"\d+\.\d+\.\d+\.\d+", text), text)


class Wording(Quiet):
    def test_language_follows_the_game(self):
        session, _ = replay(SESSION_LOG[:5])
        self.assertEqual(strings.language(), "en")
        session.consume(line("00.00:000", 0, "RB: Display: New Audio Language : Francais"))
        self.assertEqual(strings.language(), "fr")
        self.assertEqual(session.build_payload()["details"], "Dans le menu principal")

    def test_overrides_win(self):
        config.TEXT_OVERRIDES = {"lobby": "Chilling"}
        _, changes = replay(SESSION_LOG[:17])
        self.assertEqual(changes[-1][1]["details"], "Chilling")

    def test_every_language_is_complete(self):
        for code, table in strings.STRINGS.items():
            self.assertEqual(set(table), set(strings.STRINGS[strings.FALLBACK]), code)


class ReplayClock(Quiet):
    def test_phase_start_comes_from_the_log_while_replaying(self):
        session = GameInfo()
        session.clock_offset = 100.0
        session.consume(SESSION_LOG[0])
        self.assertEqual(session.phase_started_at,
                         parse_log_time(SESSION_LOG[0]) + 100.0)

    def test_live_lines_use_the_wall_clock(self):
        session = GameInfo()
        session.consume(SESSION_LOG[0])
        self.assertGreater(session.phase_started_at, parse_log_time(SESSION_LOG[0]) + 3600)


class Statistics(Quiet):
    def test_outcome_and_favourites_are_recorded(self):
        with tempfile.TemporaryDirectory() as folder:
            stats = Stats(os.path.join(folder, "stats.json"))
            session = GameInfo()
            for text in SESSION_LOG:
                previous = session.game_phase
                if session.consume(text):
                    if stats._started_at is not None:
                        stats._started_at -= 600   # pretend ten minutes went by
                    stats.observe(previous, session, IN_TRIAL)
            self.assertEqual(stats.total["trials"], 1)
            self.assertEqual(stats.total["outcomes"], {"failed": 1})
            self.assertEqual(stats.total["maps"], {"Police Station": 1})
            self.assertEqual(stats.total["names"], {"Kill The Snitch": 1})
            self.assertGreaterEqual(stats.total["longest"], 600)
            rows = "\n".join(stats.summary())
            self.assertIn("1 failed", rows)
            self.assertIn("Kill The Snitch", rows)
            reloaded = Stats(stats.path)
            self.assertEqual(reloaded.total["outcomes"], {"failed": 1})

    def test_intro_time_is_not_counted(self):
        with tempfile.TemporaryDirectory() as folder:
            stats = Stats(os.path.join(folder, "stats.json"))
            session = GameInfo()
            for text in SESSION_LOG[:31]:     # stops before StageStarted
                previous = session.game_phase
                if session.consume(text):
                    stats.observe(previous, session, IN_TRIAL)
            self.assertEqual(session.game_phase, INTRO)
            self.assertIsNone(stats._started_at)


class DataTables(Quiet):
    def test_check_finds_no_problem(self):
        self.assertEqual(check.problems(), [])


if __name__ == "__main__":
    unittest.main()
