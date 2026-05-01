#!/usr/bin/env python3
"""
SportPulse — Live Sports CLI Dashboard
=======================================
Real-time NBA, NHL, and AFL scores and player stats, right in your terminal.

Usage:
    python sportpulse.py

Controls:
    ↑ / ↓      Navigate
    ↵  Enter   Select / Open
    q  ESC     Back / Quit
    r          Force refresh
    TAB        Cycle team filter (game detail)
"""

import curses
import time
import threading
import requests
import sys
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

REFRESH_INTERVAL = 30  # seconds between auto-refreshes

SPORT_URLS: Dict[str, Dict[str, str]] = {
    "nba": {
        "scoreboard": "http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
        "summary":    "http://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary",
    },
    "nhl": {
        "scoreboard": "http://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard",
        "summary":    "http://site.api.espn.com/apis/site/v2/sports/hockey/nhl/summary",
    },
    "afl": {
        "scoreboard": "http://site.api.espn.com/apis/site/v2/sports/australian-football/afl/scoreboard",
        "summary":    "http://site.api.espn.com/apis/site/v2/sports/australian-football/afl/summary",
    },
}

SPORTS = [
    {"id": "nba", "label": "NBA",  "available": True},
    {"id": "nhl", "label": "NHL",  "available": True},
    {"id": "afl", "label": "AFL",  "available": True},
]

LOGO = [
    " ____                   _   ____        _           ",
    "/ ___| _ __   ___  _ __| |_|  _ \\ _   _| |___  ___ ",
    "\\___ \\| '_ \\ / _ \\| '__| __| |_) | | | | / __|/ _ \\",
    " ___) | |_) | (_) | |  | |_|  __/| |_| | \\__ \\  __/",
    "|____/| .__/ \\___/|_|   \\__|_|    \\__,_|_|___/\\___|",
    "      |_|                                           ",
]

TAGLINE = "Real-time Sports Stats  ·  Powered by ESPN"

# ─────────────────────────────────────────────────────────────────────────────
# SPORT-SPECIFIC TABLE COLUMNS  (header, width, alignment)
# ─────────────────────────────────────────────────────────────────────────────

NBA_TABLE_COLS: List[Tuple[str, int, str]] = [
    ("RK",      3,  "right"),
    ("",        1,  "left"),    # rank-change arrow
    ("PLAYER",  22, "left"),
    ("TEAM",    4,  "left"),
    ("POS",     3,  "center"),
    ("MIN",     5,  "right"),
    ("PTS",     4,  "right"),
    ("REB",     4,  "right"),
    ("AST",     4,  "right"),
    ("STL",     3,  "right"),
    ("BLK",     3,  "right"),
    ("FG",      7,  "center"),
    ("3PT",     7,  "center"),
    ("FT",      6,  "center"),
    ("+/-",     4,  "right"),
]

NHL_TABLE_COLS: List[Tuple[str, int, str]] = [
    ("RK",      3,  "right"),
    ("",        1,  "left"),
    ("PLAYER",  22, "left"),
    ("TEAM",    4,  "left"),
    ("POS",     3,  "center"),
    ("TOI",     5,  "right"),
    ("G",       3,  "right"),
    ("A",       3,  "right"),
    ("PTS",     3,  "right"),
    ("+/-",     4,  "right"),
    ("SOG",     4,  "right"),
    ("BS",      4,  "right"),
    ("HITS",    4,  "right"),
    ("PIM",     4,  "right"),
    ("FO%",     5,  "right"),
]

AFL_TABLE_COLS: List[Tuple[str, int, str]] = [
    ("RK",      3,  "right"),
    ("",        1,  "left"),
    ("PLAYER",  20, "left"),
    ("TEAM",    4,  "left"),
    ("POS",     3,  "center"),
    ("FPTS",    4,  "right"),
    ("D",       4,  "right"),
    ("K",       3,  "right"),
    ("HB",      3,  "right"),
    ("M",       3,  "right"),
    ("T",       3,  "right"),
    ("G",       3,  "right"),
    ("B",       3,  "right"),
    ("HO",      3,  "right"),
    ("I50",     4,  "right"),
    ("R50",     4,  "right"),
    ("FF",      3,  "right"),
    ("FA",      3,  "right"),
]

SPORT_TABLE_COLS: Dict[str, List[Tuple[str, int, str]]] = {
    "nba": NBA_TABLE_COLS,
    "nhl": NHL_TABLE_COLS,
    "afl": AFL_TABLE_COLS,
}

# ─────────────────────────────────────────────────────────────────────────────
# COLOR PAIRS
# ─────────────────────────────────────────────────────────────────────────────

CP: Dict[str, int] = {}

_COLOR_DEFS = [
    ("header",       curses.COLOR_WHITE,  curses.COLOR_BLUE),
    ("selected",     curses.COLOR_BLACK,  curses.COLOR_YELLOW),
    ("live_badge",   curses.COLOR_WHITE,  curses.COLOR_RED),
    ("upcoming_b",   curses.COLOR_BLACK,  curses.COLOR_GREEN),
    ("logo",         curses.COLOR_CYAN,   -1),
    ("col_hdr",      curses.COLOR_BLACK,  curses.COLOR_WHITE),
    ("positive",     curses.COLOR_GREEN,  -1),
    ("negative",     curses.COLOR_RED,    -1),
    ("score_away",   curses.COLOR_CYAN,   -1),
    ("score_home",   curses.COLOR_GREEN,  -1),
    ("status_bar",   curses.COLOR_BLACK,  curses.COLOR_WHITE),
    ("section",      curses.COLOR_YELLOW, curses.COLOR_BLUE),
    ("final_badge",  curses.COLOR_WHITE,  curses.COLOR_BLACK),
    ("accent",       curses.COLOR_YELLOW, -1),
    ("score_box",    curses.COLOR_WHITE,  curses.COLOR_BLUE),
    ("dim",          curses.COLOR_WHITE,  -1),
]


def init_colors() -> None:
    curses.start_color()
    curses.use_default_colors()
    for i, (name, fg, bg) in enumerate(_COLOR_DEFS, start=1):
        curses.init_pair(i, fg, bg)
        CP[name] = i


def cp(name: str, bold: bool = False, dim: bool = False) -> int:
    attr = curses.color_pair(CP.get(name, 0))
    if bold:
        attr |= curses.A_BOLD
    if dim:
        attr |= curses.A_DIM
    return attr


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _int(s) -> int:
    try:
        return int(str(s).replace("+", "").strip())
    except (ValueError, TypeError):
        return 0


def _float(s) -> float:
    try:
        return float(str(s).strip())
    except (ValueError, TypeError):
        return 0.0


def _period_str_nba(period: int) -> str:
    if period == 0:    return ""
    if period <= 4:    return f"Q{period}"
    if period == 5:    return "OT"
    return f"OT{period - 4}"


def _period_str_nhl(period: int) -> str:
    if period == 0:    return ""
    if period <= 3:    return f"P{period}"
    if period == 4:    return "OT"
    return "SO"


def _period_str_afl(period: int) -> str:
    if period == 0:    return ""
    if period <= 4:    return f"Q{period}"
    return f"OT"


_PERIOD_FN: Dict[str, Callable[[int], str]] = {
    "nba": _period_str_nba,
    "nhl": _period_str_nhl,
    "afl": _period_str_afl,
}


def _afl_fpts(k: int, hb: int, m: int, t: int, g: int, b: int,
              ho: int, ff: int, fa: int, i50: int, r50: int) -> int:
    """AFL Fantasy points formula (standard AFL Fantasy/Dream Team scoring)."""
    return (k * 3 + hb * 2 + m * 3 + t * 4 + g * 8 + b * 1
            + ho * 1 + ff * 1 + fa * -1 + i50 * 1 + r50 * 1)


# ─────────────────────────────────────────────────────────────────────────────
# ESPN DATA LAYER
# ─────────────────────────────────────────────────────────────────────────────

def fetch_scoreboard(sport: str) -> Optional[Dict]:
    try:
        url = SPORT_URLS[sport]["scoreboard"]
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def fetch_game_detail(event_id: str, sport: str) -> Optional[Dict]:
    try:
        url = SPORT_URLS[sport]["summary"]
        r = requests.get(url, params={"event": event_id}, timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def parse_games(data: Dict, sport: str = "nba") -> List[Dict]:
    period_fn = _PERIOD_FN.get(sport, _period_str_nba)
    games: List[Dict] = []
    for event in (data or {}).get("events", []):
        comp  = (event.get("competitions") or [{}])[0]
        stat  = comp.get("status", {})
        stype = stat.get("type", {})
        state = stype.get("state", "pre")

        if   state == "in":   g_status = "live"
        elif state == "post": g_status = "final"
        else:                 g_status = "upcoming"

        comps  = comp.get("competitors", [])
        home   = next((c for c in comps if c.get("homeAway") == "home"), {})
        away   = next((c for c in comps if c.get("homeAway") == "away"), {})
        home_t = home.get("team", {})
        away_t = away.get("team", {})

        # For AFL: build goals.behinds.total string from linescores if available
        h_score_str = home.get("score", "0")
        a_score_str = away.get("score", "0")
        if sport == "afl":
            h_score_str = _afl_score_from_linescores(
                home.get("linescores", []), h_score_str)
            a_score_str = _afl_score_from_linescores(
                away.get("linescores", []), a_score_str)

        games.append({
            "id":          event.get("id", ""),
            "status":      g_status,
            "home_name":   home_t.get("displayName", "Home"),
            "home_abbrev": home_t.get("abbreviation", "HOM"),
            "home_score":  h_score_str,
            "away_name":   away_t.get("displayName", "Away"),
            "away_abbrev": away_t.get("abbreviation", "AWY"),
            "away_score":  a_score_str,
            "period":      period_fn(stat.get("period", 0)),
            "clock":       stat.get("displayClock", ""),
            "detail":      stype.get("shortDetail", stype.get("detail", "")),
            "date":        event.get("date", ""),
        })
    return games


def _afl_score_from_linescores(linescores: list, fallback: str) -> str:
    """Return 'G.B.Total' string from linescores, or fallback total."""
    if not linescores:
        return fallback
    last = linescores[-1]
    goals   = last.get("cumulativeGoalsDisplayValue", "")
    behinds = last.get("cumulativeBehindsDisplayValue", "")
    total   = fallback
    if goals and behinds:
        return f"{goals}.{behinds}.{total}"
    return fallback


def _parse_header_scores(data: Dict, sport: str) -> Dict:
    """Extract the game header from ESPN summary data."""
    hcomp  = (data.get("header", {}).get("competitions") or [{}])[0]
    hstat  = hcomp.get("status", {})
    htype  = hstat.get("type", {})
    hcomps = hcomp.get("competitors", [])
    home   = next((c for c in hcomps if c.get("homeAway") == "home"), {})
    away   = next((c for c in hcomps if c.get("homeAway") == "away"), {})

    period_fn = _PERIOD_FN.get(sport, _period_str_nba)

    # Base scores
    home_score = home.get("score", "0")
    away_score = away.get("score", "0")

    # AFL: enhance with goals.behinds.total from linescores
    home_goals = home_behinds = away_goals = away_behinds = None
    if sport == "afl":
        h_ls = home.get("linescores", [])
        a_ls = away.get("linescores", [])
        if h_ls:
            last = h_ls[-1]
            home_goals   = last.get("cumulativeGoalsDisplayValue")
            home_behinds = last.get("cumulativeBehindsDisplayValue")
        if a_ls:
            last = a_ls[-1]
            away_goals   = last.get("cumulativeGoalsDisplayValue")
            away_behinds = last.get("cumulativeBehindsDisplayValue")

    return {
        "home_name":    home.get("team", {}).get("displayName", "Home"),
        "home_abbrev":  home.get("team", {}).get("abbreviation", "HOM"),
        "home_score":   home_score,
        "home_goals":   home_goals,
        "home_behinds": home_behinds,
        "away_name":    away.get("team", {}).get("displayName", "Away"),
        "away_abbrev":  away.get("team", {}).get("abbreviation", "AWY"),
        "away_score":   away_score,
        "away_goals":   away_goals,
        "away_behinds": away_behinds,
        "period":       period_fn(hstat.get("period", 0)),
        "clock":        hstat.get("displayClock", ""),
        "detail":       htype.get("shortDetail", htype.get("detail", "")),
        "state":        htype.get("state", "pre"),
    }


# ── NBA ───────────────────────────────────────────────────────────────────────

def parse_nba_boxscore(data: Dict) -> Tuple[Dict, List[Dict]]:
    if not data:
        return {}, []

    game_header = _parse_header_scores(data, "nba")
    players: List[Dict] = []

    for team_block in data.get("boxscore", {}).get("players", []):
        abbrev = team_block.get("team", {}).get("abbreviation", "")
        for stats_block in team_block.get("statistics", []):
            names = [n.upper() for n in (stats_block.get("names") or [])]
            for ab in stats_block.get("athletes", []):
                raw = ab.get("stats", [])
                sm  = dict(zip(names, raw)) if raw else {}
                ath = ab.get("athlete", {})

                raw_min = sm.get("MIN", "0")
                did_not_play = (
                    not raw_min
                    or raw_min in ("0", "0:00")
                    or (not raw and ab.get("didNotPlay", False))
                )
                status_label = _dnp_label(ab, did_not_play)

                players.append({
                    "name":         ath.get("displayName", "Unknown"),
                    "pos":          ath.get("position", {}).get("abbreviation", ""),
                    "team":         abbrev,
                    "starter":      ab.get("starter", False),
                    "did_not_play": did_not_play,
                    "status_label": status_label,
                    "min":          raw_min if not did_not_play else "0:00",
                    "pts":          _int(sm.get("PTS", "0")),
                    "reb":          _int(sm.get("REB", "0")),
                    "ast":          _int(sm.get("AST", "0")),
                    "stl":          _int(sm.get("STL", "0")),
                    "blk":          _int(sm.get("BLK", "0")),
                    "fg":           sm.get("FG",  "0-0"),
                    "fg3":          sm.get("3PT", "0-0"),
                    "ft":           sm.get("FT",  "0-0"),
                    "pm":           sm.get("+/-", "0"),
                })

    active   = [p for p in players if not p["did_not_play"]]
    inactive = [p for p in players if p["did_not_play"]]
    active.sort(key=lambda p: (p["pts"], p["ast"], p["reb"]), reverse=True)
    return game_header, active + inactive


# ── NHL ───────────────────────────────────────────────────────────────────────

def parse_nhl_boxscore(data: Dict) -> Tuple[Dict, List[Dict]]:
    if not data:
        return {}, []

    game_header = _parse_header_scores(data, "nhl")
    players: List[Dict] = []

    for team_block in data.get("boxscore", {}).get("players", []):
        abbrev = team_block.get("team", {}).get("abbreviation", "")
        for stats_block in team_block.get("statistics", []):
            # NHL uses 'labels' (not 'names')
            labels = [l.upper() for l in (stats_block.get("labels") or [])]
            for ab in stats_block.get("athletes", []):
                raw = ab.get("stats", [])
                sm  = dict(zip(labels, raw)) if raw else {}
                ath = ab.get("athlete", {})

                toi = sm.get("TOI", "")
                did_not_play = not toi or toi in ("0:00", "00:00", "0")
                status_label = _dnp_label(ab, did_not_play)

                g   = _int(sm.get("G",   "0"))
                a   = _int(sm.get("A",   "0"))
                pts = g + a

                players.append({
                    "name":         ath.get("displayName", "Unknown"),
                    "pos":          ath.get("position", {}).get("abbreviation", ""),
                    "team":         abbrev,
                    "starter":      ab.get("starter", False),
                    "did_not_play": did_not_play,
                    "status_label": status_label,
                    "toi":          toi if not did_not_play else "0:00",
                    "g":            g,
                    "a":            a,
                    "pts":          pts,
                    "pm":           sm.get("+/-", "0"),
                    "sog":          _int(sm.get("S",    "0")),   # shots total
                    "bs":           _int(sm.get("BS",   "0")),   # blocked shots
                    "ht":           _int(sm.get("HT",   "0")),   # hits
                    "pim":          _int(sm.get("PIM",  "0")),
                    "fopct":        sm.get("FO%", "-"),
                    "gv":           _int(sm.get("GV",   "0")),
                    "tk":           _int(sm.get("TK",   "0")),
                })

    active   = [p for p in players if not p["did_not_play"]]
    inactive = [p for p in players if p["did_not_play"]]
    active.sort(key=lambda p: (p["pts"], p["g"], p["sog"]), reverse=True)
    return game_header, active + inactive


# ── AFL ───────────────────────────────────────────────────────────────────────

def parse_afl_boxscore(data: Dict) -> Tuple[Dict, List[Dict]]:
    if not data:
        return {}, []

    game_header = _parse_header_scores(data, "afl")
    players: List[Dict] = []

    for team_block in data.get("boxscore", {}).get("players", []):
        abbrev = team_block.get("team", {}).get("abbreviation", "")
        for stats_block in team_block.get("statistics", []):
            labels = [l.upper() for l in (stats_block.get("labels") or [])]
            for ab in stats_block.get("athletes", []):
                raw = ab.get("stats", [])
                sm  = dict(zip(labels, raw)) if raw else {}
                ath = ab.get("athlete", {})

                k   = _int(sm.get("K",   "0"))
                hb  = _int(sm.get("H",   "0"))
                m   = _int(sm.get("M",   "0"))
                t   = _int(sm.get("T",   "0"))
                g   = _int(sm.get("G",   "0"))
                b   = _int(sm.get("B",   "0"))
                ho  = _int(sm.get("HO",  "0"))
                ff  = _int(sm.get("FF",  "0"))
                fa  = _int(sm.get("FA",  "0"))
                i50 = _int(sm.get("I50", "0"))
                r50 = _int(sm.get("R50", "0"))
                d   = _int(sm.get("D",   "0"))  # disposals (k+hb)
                fpts = _afl_fpts(k, hb, m, t, g, b, ho, ff, fa, i50, r50)

                # AFL: consider a player DNP if all primary stats are zero and
                # ESPN marks them inactive
                did_not_play = (
                    ab.get("active") is False
                    or (not raw)
                    or (d == 0 and g == 0 and t == 0 and m == 0 and ab.get("didNotPlay", False))
                )
                status_label = _dnp_label(ab, did_not_play)

                players.append({
                    "name":         ath.get("displayName", "Unknown"),
                    "pos":          ath.get("position", {}).get("abbreviation", ""),
                    "team":         abbrev,
                    "starter":      ab.get("starter", False),
                    "did_not_play": did_not_play,
                    "status_label": status_label,
                    "fpts":         fpts,
                    "d":            d,
                    "k":            k,
                    "hb":           hb,
                    "m":            m,
                    "t":            t,
                    "g":            g,
                    "b":            b,
                    "ho":           ho,
                    "i50":          i50,
                    "r50":          r50,
                    "ff":           ff,
                    "fa":           fa,
                    "cp":           _int(sm.get("CP", "0")),
                })

    active   = [p for p in players if not p["did_not_play"]]
    inactive = [p for p in players if p["did_not_play"]]
    active.sort(key=lambda p: (p["fpts"], p["d"]), reverse=True)
    return game_header, active + inactive


# ── Shared helpers ────────────────────────────────────────────────────────────

def _dnp_label(ab: Dict, did_not_play: bool) -> str:
    reason = ab.get("reason", "")
    if reason:
        ru = reason.upper()
        if "INJURY" in ru or "INJURED" in ru:  return "INJ"
        if "SUSPENSION" in ru or "SUSPENDED" in ru: return "SUSP"
        if "ILLNESS" in ru:                    return "ILL"
        if "REST" in ru:                       return "REST"
        if "NOT WITH TEAM" in ru or "PERSONAL" in ru: return "AWAY"
        if did_not_play:                       return "DNP"
        return ""
    return "DNP" if did_not_play else ""


_PARSE_BOXSCORE = {
    "nba": parse_nba_boxscore,
    "nhl": parse_nhl_boxscore,
    "afl": parse_afl_boxscore,
}


def _flatten_games(games: List[Dict]) -> List[Dict]:
    """Return games in display order: live → upcoming → final."""
    live     = [g for g in games if g["status"] == "live"]
    upcoming = [g for g in games if g["status"] == "upcoming"]
    final    = [g for g in games if g["status"] == "final"]
    return live + upcoming + final


# ─────────────────────────────────────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────────────────────────────────────

class App:
    def __init__(self, stdscr: "curses._CursesWindow") -> None:
        self.scr = stdscr

        # State
        self.state = "sport_select"  # sport_select | game_list | game_detail
        self.current_sport = "nba"

        # Navigation indices
        self.sport_idx     = 0
        self.game_idx      = 0
        self.game_scroll   = 0
        self.player_scroll = 0
        self.team_filter   = 0   # 0=All, 1=Away team, 2=Home team

        # Data
        self.games:        List[Dict]      = []
        self.game_header:  Dict            = {}
        self.players:      List[Dict]      = []
        self.rank_changes: Dict[str, int]  = {}
        self._prev_ranks:  Dict[str, int]  = {}
        self.last_refresh: Optional[float] = None
        self.fetch_error:  Optional[str]   = None
        self.loading                       = False
        self.current_game_id: Optional[str] = None

        self._fetch_token: Tuple[str, Optional[str], str] = ("", None, "nba")
        self._lock    = threading.Lock()
        self._running = True
        self._wake    = threading.Event()
        self._bg      = threading.Thread(target=self._bg_loop, daemon=True)
        self._bg.start()

    # ── Entry point ───────────────────────────────────────────────────────────

    def run(self) -> None:
        init_colors()
        curses.curs_set(0)
        self.scr.timeout(500)

        while True:
            try:
                h, w = self.scr.getmaxyx()
                if h < 18 or w < 60:
                    self.scr.erase()
                    msg = "Terminal too small — please resize (min 60 × 18)"
                    self.scr.addstr(0, 0, msg[:w])
                    self.scr.refresh()
                    key = self.scr.getch()
                    if key == ord("q"):
                        break
                    continue

                self._draw()
                key = self.scr.getch()
            except curses.error:
                continue

            if key in (ord("q"), 27):
                if   self.state == "game_detail":
                    self.state = "game_list"
                    self.player_scroll = 0
                elif self.state == "game_list":
                    self.state = "sport_select"
                    with self._lock:
                        self.games = []
                else:
                    break
            elif key == curses.KEY_UP:
                self._on_up()
            elif key == curses.KEY_DOWN:
                self._on_down()
            elif key in (curses.KEY_ENTER, 10, 13):
                self._on_enter()
            elif key == ord("r"):
                self._wake.set()
            elif key == ord("\t"):
                if self.state == "game_detail":
                    self.team_filter   = (self.team_filter + 1) % 3
                    self.player_scroll = 0

        self._running = False
        self._wake.set()

    # ── Input handlers ────────────────────────────────────────────────────────

    def _on_up(self) -> None:
        if   self.state == "sport_select":
            self.sport_idx = max(0, self.sport_idx - 1)
        elif self.state == "game_list":
            self.game_idx = max(0, self.game_idx - 1)
        elif self.state == "game_detail":
            self.player_scroll = max(0, self.player_scroll - 1)

    def _on_down(self) -> None:
        if self.state == "sport_select":
            self.sport_idx = min(len(SPORTS) - 1, self.sport_idx + 1)
        elif self.state == "game_list":
            with self._lock:
                games = list(self.games)
            flat = _flatten_games(games)
            self.game_idx = min(max(0, len(flat) - 1), self.game_idx + 1)
        elif self.state == "game_detail":
            with self._lock:
                n = len(self.players)
            self.player_scroll = min(max(0, n - 1), self.player_scroll + 1)

    def _on_enter(self) -> None:
        if self.state == "sport_select":
            sport = SPORTS[self.sport_idx]
            if sport["available"]:
                self.current_sport = sport["id"]
                self.state = "game_list"
                self.game_idx    = 0
                self.game_scroll = 0
                with self._lock:
                    self.games = []
                self._wake.set()
        elif self.state == "game_list":
            with self._lock:
                games = list(self.games)
            flat = _flatten_games(games)
            if flat and self.game_idx < len(flat):
                self.current_game_id = flat[self.game_idx]["id"]
                with self._lock:
                    self.game_header  = {}
                    self.players      = []
                    self.rank_changes = {}
                    self._prev_ranks  = {}
                self.player_scroll = 0
                self.team_filter   = 0
                self.state = "game_detail"
                self._wake.set()

    # ── Background refresh ────────────────────────────────────────────────────

    def _bg_loop(self) -> None:
        while self._running:
            self._fetch()
            self._wake.wait(timeout=REFRESH_INTERVAL)
            self._wake.clear()

    def _fetch(self) -> None:
        sport = self.current_sport
        token = (self.state, self.current_game_id, sport)
        self._fetch_token = token
        self.loading = True
        try:
            state = token[0]
            if state == "game_list":
                data = fetch_scoreboard(sport)
                with self._lock:
                    if self._fetch_token != token:
                        return
                    if data is not None:
                        self.games        = parse_games(data, sport)
                        self.last_refresh = time.time()
                        self.fetch_error  = None
                    else:
                        self.fetch_error = "Network error — press r to retry"

            elif state == "game_detail" and token[1]:
                data = fetch_game_detail(token[1], sport)
                if data is not None:
                    parse_fn = _PARSE_BOXSCORE.get(sport, parse_nba_boxscore)
                    header, players = parse_fn(data)
                    new_ranks = {p["name"]: i for i, p in enumerate(players)}
                    changes: Dict[str, int] = {}
                    with self._lock:
                        prev = dict(self._prev_ranks)
                    for name, nr in new_ranks.items():
                        if name in prev and prev[name] != nr:
                            changes[name] = prev[name] - nr
                    with self._lock:
                        if self._fetch_token != token:
                            return
                        self.game_header  = header
                        self.players      = players
                        self.rank_changes = changes
                        self._prev_ranks  = new_ranks
                        self.last_refresh = time.time()
                        self.fetch_error  = None
                else:
                    with self._lock:
                        if self._fetch_token == token:
                            self.fetch_error = "Network error — press r to retry"
        finally:
            self.loading = False

    # ── Low-level draw helpers ────────────────────────────────────────────────

    def _add(self, y: int, x: int, s: str, attr: int = 0) -> None:
        h, w = self.scr.getmaxyx()
        if y < 0 or y >= h - 1 or x >= w or x < 0:
            return
        s = s[: max(0, w - x)]
        if s:
            try:
                self.scr.addstr(y, x, s, attr)
            except curses.error:
                pass

    def _add_center(self, y: int, s: str, attr: int = 0) -> None:
        _, w = self.scr.getmaxyx()
        x = max(0, (w - len(s)) // 2)
        self._add(y, x, s, attr)

    def _fill_row(self, y: int, attr: int = 0) -> None:
        _, w = self.scr.getmaxyx()
        try:
            self.scr.addstr(y, 0, " " * (w - 1), attr)
        except curses.error:
            pass

    def _hline(self, y: int, x: int, ch: int, n: int, attr: int = 0) -> None:
        h, w = self.scr.getmaxyx()
        if y < 0 or y >= h:
            return
        n = min(n, w - x)
        if n > 0:
            try:
                self.scr.hline(y, x, ch, n, attr)
            except curses.error:
                pass

    def _bar(self, y: int, text: str = "", attr: Optional[int] = None) -> None:
        _, w = self.scr.getmaxyx()
        if attr is None:
            attr = cp("header")
        self._fill_row(y, attr)
        self._add(y, 1, text, attr)

    def _status_bar(self) -> None:
        h, w = self.scr.getmaxyx()
        y    = h - 1
        attr = cp("status_bar")
        try:
            self.scr.addstr(y, 0, " " * (w - 1), attr)
        except curses.error:
            pass

        parts = []
        if self.loading:
            parts.append("⟳ Refreshing...")
        elif self.last_refresh:
            ago = int(time.time() - self.last_refresh)
            parts.append(f"Updated {ago}s ago")
        if self.fetch_error:
            parts.append(self.fetch_error)

        left  = "  ".join(parts)
        right = " ↑↓ Navigate  ↵ Select  ⇥ Filter  q Back  r Refresh "
        try:
            self.scr.addstr(y, 1, left[: max(1, w - len(right) - 2)], attr)
            self.scr.addstr(y, max(1, w - len(right)), right[: w - 1], attr)
        except curses.error:
            pass

    # ── Master draw dispatcher ────────────────────────────────────────────────

    def _draw(self) -> None:
        self.scr.erase()
        if   self.state == "sport_select": self._sport_select()
        elif self.state == "game_list":    self._game_list()
        elif self.state == "game_detail":  self._game_detail()
        self._status_bar()
        self.scr.refresh()

    # ── Screen: Sport Select ──────────────────────────────────────────────────

    def _sport_select(self) -> None:
        h, w = self.scr.getmaxyx()

        logo_w  = max(len(line) for line in LOGO)
        block_h = len(LOGO) + 2 + 2 + len(SPORTS) * 2 + 2
        sy      = max(1, (h - block_h) // 2)
        lx      = max(0, (w - logo_w) // 2)

        for i, line in enumerate(LOGO):
            self._add(sy + i, lx, line, cp("logo", bold=True))

        ty = sy + len(LOGO) + 1
        self._add_center(ty, TAGLINE, curses.A_DIM)

        div_y = ty + 2
        div   = "─" * min(50, w - 4)
        self._add_center(div_y, div, curses.A_DIM)

        list_y = div_y + 2
        list_w = 38
        list_x = max(0, (w - list_w) // 2)

        for i, sport in enumerate(SPORTS):
            y   = list_y + i * 2
            sel = (i == self.sport_idx)

            if sel:
                row_attr = cp("selected", bold=True)
                self._hline(y, list_x - 1, ord(" "), list_w + 2, cp("selected"))
                arrow = "►"
            else:
                row_attr = curses.A_NORMAL
                arrow    = " "

            self._add(y, list_x, f" {arrow} {sport['label']}", row_attr)

        hint = "  ↑↓ Navigate   ↵ Select   q Quit  "
        self._add_center(h - 3, hint, curses.A_DIM)

    # ── Screen: Game List ─────────────────────────────────────────────────────

    def _game_list(self) -> None:
        h, w = self.scr.getmaxyx()

        sport_label = self.current_sport.upper()
        self._bar(0, f"{sport_label}  ·  Today's Games", cp("header", bold=True))

        with self._lock:
            games = list(self.games)

        flat = _flatten_games(games)
        live     = [g for g in games if g["status"] == "live"]
        upcoming = [g for g in games if g["status"] == "upcoming"]
        final    = [g for g in games if g["status"] == "final"]

        sections = [
            (live,     "● LIVE",     "live_badge"),
            (upcoming, "  UPCOMING", "upcoming_b"),
            (final,    "  FINAL",    "final_badge"),
        ]

        if not flat:
            if self.loading:
                self._add_center(h // 2, "⟳  Fetching games...", curses.A_DIM)
            else:
                self._add_center(h // 2 - 1,
                    f"No {sport_label} games scheduled today.", curses.A_DIM)
                self._add_center(h // 2 + 1, "Press  r  to refresh.", curses.A_DIM)
            return

        self.game_idx = max(0, min(self.game_idx, len(flat) - 1))
        visible_rows  = h - 3
        if self.game_idx < self.game_scroll:
            self.game_scroll = self.game_idx
        elif self.game_idx >= self.game_scroll + visible_rows:
            self.game_scroll = self.game_idx - visible_rows + 1

        y       = 1
        flat_i  = 0
        row_abs = 0

        for glist, label, badge_key in sections:
            if not glist:
                continue

            if row_abs >= self.game_scroll and y < h - 2:
                self._bar(y, label, cp(badge_key, bold=True))
                y += 1
            elif row_abs < self.game_scroll:
                pass
            row_abs += 1

            for g in glist:
                if y >= h - 2:
                    break
                if row_abs >= self.game_scroll:
                    sel      = (flat_i == self.game_idx)
                    row_attr = cp("selected", bold=True) if sel else curses.A_NORMAL
                    if sel:
                        self._fill_row(y, cp("selected"))

                    pfx = " ► " if sel else "   "

                    # For AFL, score string already includes G.B.Total if available
                    a_sc = g["away_score"]
                    h_sc = g["home_score"]
                    # Numeric totals for width calculation
                    a_total = _int(a_sc.split(".")[-1] if "." in a_sc else a_sc)
                    h_total = _int(h_sc.split(".")[-1] if "." in h_sc else h_sc)

                    if g["status"] == "live":
                        line = (
                            f"{pfx}{g['away_abbrev']:>4}  "
                            f"{a_sc:>12} - {h_sc:<12}"
                            f"  {g['home_abbrev']:<4}   "
                            f"{g['period']} {g['clock']}"
                        )
                    elif g["status"] == "final":
                        line = (
                            f"{pfx}{g['away_abbrev']:>4}  "
                            f"{a_sc:>12} - {h_sc:<12}"
                            f"  {g['home_abbrev']:<4}   FINAL"
                        )
                    else:
                        line = (
                            f"{pfx}{g['away_abbrev']:>4}  vs  {g['home_abbrev']:<4}"
                            f"   {g['detail']}"
                        )

                    self._add(y, 0, line, row_attr)

                    if g["status"] == "live" and not sel:
                        self._add(y, 1, "●", cp("live_badge", bold=True))

                    y += 1

                row_abs += 1
                flat_i  += 1

            row_abs += 1

    # ── Screen: Game Detail ───────────────────────────────────────────────────

    def _game_detail(self) -> None:
        h, w = self.scr.getmaxyx()
        sport = self.current_sport
        table_cols = SPORT_TABLE_COLS.get(sport, NBA_TABLE_COLS)

        with self._lock:
            header  = dict(self.game_header)
            players = list(self.players)
            changes = dict(self.rank_changes)

        if players:
            self.player_scroll = max(0, min(self.player_scroll, len(players) - 1))
        else:
            self.player_scroll = 0

        if not header:
            if self.loading:
                self._add_center(h // 2, "⟳  Loading game data...", curses.A_DIM)
            else:
                self._add_center(h // 2, "No data available — press r to retry", curses.A_DIM)
            return

        # ── Top header bar ────────────────────────────────────────────────
        state = header.get("state", "pre")
        if state == "in":
            state_tag = f"  ● LIVE  {header['period']}  {header['clock']}"
            tag_attr  = cp("live_badge", bold=True)
        elif state == "post":
            state_tag = "  FINAL"
            tag_attr  = cp("final_badge", bold=True)
        else:
            state_tag = f"  {header.get('detail', 'Upcoming')}"
            tag_attr  = cp("upcoming_b", bold=True)

        title = f"  {header['away_abbrev']} @ {header['home_abbrev']}"
        self._bar(0, title, cp("header", bold=True))
        self._add(0, w - len(state_tag) - 2, state_tag, tag_attr)

        # ── Score box (rows 1–7) ──────────────────────────────────────────
        BOX_H    = 7
        box_attr = cp("score_box")

        for row in range(1, BOX_H + 1):
            self._fill_row(row, box_attr)

        mid = w // 2

        away_name = header.get("away_name", header.get("away_abbrev", "")).upper()
        home_name = header.get("home_name", header.get("home_abbrev", "")).upper()
        max_name  = min(26, (w - 8) // 2)
        away_name = away_name[:max_name]
        home_name = home_name[:max_name]

        # Score display — AFL shows G.B.Total if goals/behinds are available
        if sport == "afl":
            ag = header.get("away_goals")
            ab = header.get("away_behinds")
            hg = header.get("home_goals")
            hb_val = header.get("home_behinds")
            away_score = (f"{ag}.{ab}.{header['away_score']}"
                          if ag and ab else str(header.get("away_score", "0")))
            home_score = (f"{hg}.{hb_val}.{header['home_score']}"
                          if hg and hb_val else str(header.get("home_score", "0")))
        else:
            away_score = str(header.get("away_score", "0"))
            home_score = str(header.get("home_score", "0"))

        # Team names row (row 2)
        name_y = 2
        self._add(name_y, max(2, mid - len(away_name) - 4), away_name,
                  box_attr | curses.A_BOLD)
        self._add(name_y, mid - 1, "vs", box_attr | curses.A_BOLD)
        self._add(name_y, mid + 3, home_name, box_attr | curses.A_BOLD)

        # Scores row (row 4)
        score_y = 4
        self._add(score_y, max(2, mid - len(away_score) - 4), away_score,
                  cp("score_away", bold=True))
        self._add(score_y, mid - 1, "●", box_attr)
        self._add(score_y, mid + 3, home_score,
                  cp("score_home", bold=True))

        # Clock / status row (row 6)
        if state == "in":
            clk = f"  {header['period']}   {header['clock']} remaining  "
        elif state == "post":
            clk = "  F I N A L  "
        else:
            clk = f"  {header.get('detail', '')}  "
        self._add_center(6, clk, box_attr | curses.A_BOLD)

        # ── Team filter tabs + divider ────────────────────────────────────
        away_abbrev = header.get("away_abbrev", "AWY")
        home_abbrev = header.get("home_abbrev", "HOM")
        tab_labels  = ["All Players", away_abbrev, home_abbrev]

        div_y = BOX_H + 1
        self._add(div_y, 0, "─" * (w - 1), curses.A_DIM)

        tab_x = 2
        for i, label in enumerate(tab_labels):
            if i == self.team_filter:
                tab_str  = f"[ {label} ]"
                tab_attr = cp("selected", bold=True)
            else:
                tab_str  = f"  {label}  "
                tab_attr = curses.A_DIM
            self._add(div_y, tab_x, tab_str, tab_attr)
            tab_x += len(tab_str) + 1

        hint = "⇥ Tab to switch"
        self._add(div_y, w - len(hint) - 2, hint, curses.A_DIM)

        # ── Apply team filter ─────────────────────────────────────────────
        if self.team_filter == 1:
            visible_players = [p for p in players if p["team"] == away_abbrev]
        elif self.team_filter == 2:
            visible_players = [p for p in players if p["team"] == home_abbrev]
        else:
            visible_players = players

        if visible_players:
            self.player_scroll = max(0, min(self.player_scroll, len(visible_players) - 1))
        else:
            self.player_scroll = 0

        # ── Column headers ────────────────────────────────────────────────
        col_hdr_y = div_y + 1
        self._fill_row(col_hdr_y, cp("col_hdr"))

        col_x = 1
        col_positions: List[int] = []
        for cname, cw, align in table_cols:
            if align == "center":  s = cname.center(cw)
            elif align == "left":  s = cname.ljust(cw)
            else:                  s = cname.rjust(cw)
            self._add(col_hdr_y, col_x, s, cp("col_hdr", bold=True))
            col_positions.append(col_x)
            col_x += cw + 1

        # ── Player rows ───────────────────────────────────────────────────
        data_top   = col_hdr_y + 1
        table_rows = max(1, h - data_top - 2)
        start      = self.player_scroll

        for i, player in enumerate(visible_players[start: start + table_rows]):
            ry   = data_top + i
            rank = start + i + 1
            dnp  = player.get("did_not_play", False)

            row_attr = curses.A_DIM if dnp else curses.A_NORMAL

            chg = changes.get(player["name"], 0) if not dnp else 0
            if chg > 0:
                chg_str, chg_attr = "↑", cp("positive", bold=True)
            elif chg < 0:
                chg_str, chg_attr = "↓", cp("negative", bold=True)
            else:
                chg_str, chg_attr = " ", row_attr

            if dnp:
                status = player.get("status_label", "DNP") or "DNP"
                cells  = self._dnp_cells(rank, player, status, row_attr,
                                         len(table_cols))
            else:
                cells = self._player_cells(rank, player, chg_str, chg_attr,
                                           row_attr, sport)

            for (_, cw, _), (val, vattr), cx in zip(table_cols, cells, col_positions):
                self._add(ry, cx, val[:cw], vattr)

        # Scroll indicator
        total = len(visible_players)
        if total > table_rows:
            shown_end = min(start + table_rows, total)
            pct = int(100 * start / max(1, total - table_rows))
            scroll_msg = (
                f" ↑↓ Scroll  rows {start + 1}–{shown_end} of {total}"
                f"  ({pct}%) "
            )
            self._add(h - 2, 1, scroll_msg, curses.A_DIM)

    # ── Cell builders ─────────────────────────────────────────────────────────

    def _dnp_cells(self, rank: int, player: Dict, status: str,
                   row_attr: int, total_cols: int) -> list:
        """Build cells for a did-not-play row (works for all sports)."""
        name_w = 22 if self.current_sport != "afl" else 20
        cells = [
            (str(rank).rjust(3),                     row_attr),
            (" ",                                     row_attr),
            (player["name"][:name_w].ljust(name_w),  row_attr),
            (player["team"][:4].ljust(4),             row_attr),
            (player["pos"][:3].center(3),             row_attr),
            (status.center(4),                        cp("negative")),
        ]
        # Pad with blanks for the remaining stat columns
        while len(cells) < total_cols:
            cells.append(("", row_attr))
        return cells

    def _player_cells(self, rank: int, player: Dict, chg_str: str,
                      chg_attr: int, row_attr: int, sport: str) -> list:
        """Build stat cells for an active player (sport-dispatched)."""
        if sport == "nhl":
            return self._nhl_cells(rank, player, chg_str, chg_attr, row_attr)
        if sport == "afl":
            return self._afl_cells(rank, player, chg_str, chg_attr, row_attr)
        return self._nba_cells(rank, player, chg_str, chg_attr, row_attr)

    def _nba_cells(self, rank, player, chg_str, chg_attr, row_attr):
        try:
            pm_n = int(str(player["pm"]).replace("+", ""))
            if pm_n > 0:   pm_str, pm_attr = f"+{pm_n}", cp("positive")
            elif pm_n < 0: pm_str, pm_attr = str(pm_n), cp("negative")
            else:          pm_str, pm_attr = "0", row_attr
        except (ValueError, TypeError):
            pm_str, pm_attr = str(player["pm"]), row_attr

        pts_attr = (row_attr | curses.A_BOLD) if player["pts"] >= 20 else row_attr
        return [
            (str(rank).rjust(3),                    row_attr),
            (chg_str,                                chg_attr),
            (player["name"][:22].ljust(22),          row_attr | curses.A_BOLD),
            (player["team"][:4].ljust(4),            row_attr),
            (player["pos"][:3].center(3),            row_attr),
            (player["min"][:5].rjust(5),             row_attr),
            (str(player["pts"]).rjust(4),            pts_attr),
            (str(player["reb"]).rjust(4),            row_attr),
            (str(player["ast"]).rjust(4),            row_attr),
            (str(player["stl"]).rjust(3),            row_attr),
            (str(player["blk"]).rjust(3),            row_attr),
            (player["fg"][:7].center(7),             row_attr),
            (player["fg3"][:7].center(7),            row_attr),
            (player["ft"][:6].center(6),             row_attr),
            (pm_str[:4].rjust(4),                    pm_attr),
        ]

    def _nhl_cells(self, rank, player, chg_str, chg_attr, row_attr):
        try:
            pm_n = int(str(player["pm"]).replace("+", ""))
            if pm_n > 0:   pm_str, pm_attr = f"+{pm_n}", cp("positive")
            elif pm_n < 0: pm_str, pm_attr = str(pm_n), cp("negative")
            else:          pm_str, pm_attr = "0", row_attr
        except (ValueError, TypeError):
            pm_str, pm_attr = str(player["pm"]), row_attr

        pts_attr = (row_attr | curses.A_BOLD) if player["pts"] >= 2 else row_attr
        return [
            (str(rank).rjust(3),                    row_attr),
            (chg_str,                                chg_attr),
            (player["name"][:22].ljust(22),          row_attr | curses.A_BOLD),
            (player["team"][:4].ljust(4),            row_attr),
            (player["pos"][:3].center(3),            row_attr),
            (player["toi"][:5].rjust(5),             row_attr),
            (str(player["g"]).rjust(3),              pts_attr),
            (str(player["a"]).rjust(3),              row_attr),
            (str(player["pts"]).rjust(3),            pts_attr),
            (pm_str[:4].rjust(4),                    pm_attr),
            (str(player["sog"]).rjust(4),            row_attr),
            (str(player["bs"]).rjust(4),             row_attr),
            (str(player["ht"]).rjust(4),             row_attr),
            (str(player["pim"]).rjust(4),            row_attr),
            (str(player["fopct"])[:5].rjust(5),      row_attr),
        ]

    def _afl_cells(self, rank, player, chg_str, chg_attr, row_attr):
        fpts_attr = (row_attr | curses.A_BOLD) if player["fpts"] >= 100 else row_attr
        return [
            (str(rank).rjust(3),                    row_attr),
            (chg_str,                                chg_attr),
            (player["name"][:20].ljust(20),          row_attr | curses.A_BOLD),
            (player["team"][:4].ljust(4),            row_attr),
            (player["pos"][:3].center(3),            row_attr),
            (str(player["fpts"]).rjust(4),           fpts_attr),
            (str(player["d"]).rjust(4),              row_attr),
            (str(player["k"]).rjust(3),              row_attr),
            (str(player["hb"]).rjust(3),             row_attr),
            (str(player["m"]).rjust(3),              row_attr),
            (str(player["t"]).rjust(3),              row_attr),
            (str(player["g"]).rjust(3),              row_attr),
            (str(player["b"]).rjust(3),              row_attr),
            (str(player["ho"]).rjust(3),             row_attr),
            (str(player["i50"]).rjust(4),            row_attr),
            (str(player["r50"]).rjust(4),            row_attr),
            (str(player["ff"]).rjust(3),             row_attr),
            (str(player["fa"]).rjust(3),             row_attr),
        ]


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main(stdscr: "curses._CursesWindow") -> None:
    app = App(stdscr)
    app.run()


if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
