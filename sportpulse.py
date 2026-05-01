#!/usr/bin/env python3
"""
SportPulse — Live Sports CLI Dashboard
=======================================
Real-time NBA, NHL, AFL, and NFL scores and player stats.

Usage:
    python sportpulse.py

Controls:
    ↑ / ↓      Navigate / scroll
    ↵  Enter   Select / Open
    q  ESC     Back / Quit
    r          Force refresh
    TAB        Cycle team filter (game detail)
    P          Previous round / day
    F          Next round / day
    L          Toggle league ladder / standings
"""

import curses
import time
import threading
import webbrowser
import requests
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

REFRESH_INTERVAL = 20   # seconds between auto-refreshes
LIVE_REFRESH     = 12   # faster refresh when a live game is open

# Kayo Sports deep-link URLs per sport
KAYO_URLS: Dict[str, str] = {
    "nba": "https://kayosports.com.au/sport/nba",
    "nhl": "https://kayosports.com.au/sport/nhl",
    "afl": "https://kayosports.com.au/sport/afl",
    "nfl": "https://kayosports.com.au/sport/nfl",
}

TEAM_COLORS: Dict[str, Dict[str, int]] = {
    "nba": {
        "ATL": curses.COLOR_RED,    "BOS": curses.COLOR_GREEN,  "BKN": curses.COLOR_WHITE,
        "CHA": curses.COLOR_CYAN,   "CHI": curses.COLOR_RED,    "CLE": curses.COLOR_RED,
        "DAL": curses.COLOR_BLUE,   "DEN": curses.COLOR_YELLOW, "DET": curses.COLOR_RED,
        "GSW": curses.COLOR_YELLOW, "HOU": curses.COLOR_RED,    "IND": curses.COLOR_YELLOW,
        "LAC": curses.COLOR_RED,    "LAL": curses.COLOR_MAGENTA,"MEM": curses.COLOR_BLUE,
        "MIA": curses.COLOR_RED,    "MIL": curses.COLOR_GREEN,  "MIN": curses.COLOR_GREEN,
        "NOP": curses.COLOR_YELLOW, "NYK": curses.COLOR_BLUE,   "OKC": curses.COLOR_BLUE,
        "ORL": curses.COLOR_BLUE,   "PHI": curses.COLOR_BLUE,   "PHX": curses.COLOR_MAGENTA,
        "POR": curses.COLOR_RED,    "SAC": curses.COLOR_MAGENTA,"SAS": curses.COLOR_WHITE,
        "TOR": curses.COLOR_RED,    "UTA": curses.COLOR_YELLOW, "WAS": curses.COLOR_RED,
    },
    "nhl": {
        "ANA": curses.COLOR_YELLOW, "ARI": curses.COLOR_RED,    "BOS": curses.COLOR_YELLOW,
        "BUF": curses.COLOR_BLUE,   "CAR": curses.COLOR_RED,    "CBJ": curses.COLOR_BLUE,
        "CGY": curses.COLOR_RED,    "CHI": curses.COLOR_RED,    "COL": curses.COLOR_MAGENTA,
        "DAL": curses.COLOR_GREEN,  "DET": curses.COLOR_RED,    "EDM": curses.COLOR_YELLOW,
        "FLA": curses.COLOR_RED,    "LA":  curses.COLOR_YELLOW, "MIN": curses.COLOR_GREEN,
        "MTL": curses.COLOR_RED,    "NJ":  curses.COLOR_RED,    "NSH": curses.COLOR_YELLOW,
        "NYI": curses.COLOR_BLUE,   "NYR": curses.COLOR_BLUE,   "OTT": curses.COLOR_RED,
        "PHI": curses.COLOR_YELLOW, "PIT": curses.COLOR_YELLOW, "SEA": curses.COLOR_CYAN,
        "SJS": curses.COLOR_CYAN,   "STL": curses.COLOR_BLUE,   "TB":  curses.COLOR_BLUE,
        "TOR": curses.COLOR_BLUE,   "UTA": curses.COLOR_CYAN,   "VAN": curses.COLOR_BLUE,
        "VGK": curses.COLOR_YELLOW, "WSH": curses.COLOR_RED,    "WPG": curses.COLOR_BLUE,
    },
    "afl": {
        "ADE": curses.COLOR_RED,    "BL":  curses.COLOR_BLUE,   "CARL": curses.COLOR_BLUE,
        "COLL": curses.COLOR_WHITE, "ESS": curses.COLOR_RED,    "FRE": curses.COLOR_MAGENTA,
        "GC":  curses.COLOR_YELLOW, "GEE": curses.COLOR_BLUE,   "GWS": curses.COLOR_YELLOW,
        "HAW": curses.COLOR_YELLOW, "MELB": curses.COLOR_RED,   "NM":  curses.COLOR_BLUE,
        "PA":  curses.COLOR_CYAN,   "RICH": curses.COLOR_YELLOW,"STK": curses.COLOR_RED,
        "SYD": curses.COLOR_RED,    "WB":  curses.COLOR_RED,    "WCE": curses.COLOR_BLUE,
    },
    "nfl": {
        "ARI": curses.COLOR_RED,    "ATL": curses.COLOR_RED,    "BAL": curses.COLOR_MAGENTA,
        "BUF": curses.COLOR_BLUE,   "CAR": curses.COLOR_CYAN,   "CHI": curses.COLOR_BLUE,
        "CIN": curses.COLOR_YELLOW, "CLE": curses.COLOR_YELLOW, "DAL": curses.COLOR_BLUE,
        "DEN": curses.COLOR_YELLOW, "DET": curses.COLOR_BLUE,   "GB":  curses.COLOR_GREEN,
        "HOU": curses.COLOR_RED,    "IND": curses.COLOR_BLUE,   "JAX": curses.COLOR_CYAN,
        "KC":  curses.COLOR_RED,    "LA":  curses.COLOR_YELLOW, "LAC": curses.COLOR_YELLOW,
        "LV":  curses.COLOR_WHITE,  "MIA": curses.COLOR_CYAN,   "MIN": curses.COLOR_MAGENTA,
        "NE":  curses.COLOR_BLUE,   "NO":  curses.COLOR_YELLOW, "NYG": curses.COLOR_BLUE,
        "NYJ": curses.COLOR_GREEN,  "PHI": curses.COLOR_GREEN,  "PIT": curses.COLOR_YELLOW,
        "SEA": curses.COLOR_GREEN,  "SF":  curses.COLOR_RED,    "TB":  curses.COLOR_RED,
        "TEN": curses.COLOR_BLUE,   "WAS": curses.COLOR_RED,
    },
}

SPORT_PATHS: Dict[str, str] = {
    "nba": "basketball/nba",
    "nhl": "hockey/nhl",
    "afl": "australian-football/afl",
    "nfl": "football/nfl",
}

SPORT_URLS: Dict[str, Dict[str, str]] = {
    k: {
        "scoreboard": f"http://site.api.espn.com/apis/site/v2/sports/{v}/scoreboard",
        "summary":    f"http://site.api.espn.com/apis/site/v2/sports/{v}/summary",
        "standings":  f"http://site.api.espn.com/apis/v2/sports/{v}/standings",
    }
    for k, v in SPORT_PATHS.items()
}

# Round-based sports use ?week=N; date-based use ?dates=YYYYMMDD
ROUND_BASED_SPORTS = {"afl", "nfl"}

SPORTS = [
    {"id": "nba", "label": "NBA",  "available": True},
    {"id": "nhl", "label": "NHL",  "available": True},
    {"id": "afl", "label": "AFL",  "available": True},
    {"id": "nfl", "label": "NFL",  "available": True},
]

LOGO = [
    "   _____                  __  ____        __        ",
    "  / ___/____  ____  _____/ /_/ __ \\__  __/ /_______ ",
    "  \\__ \\/ __ \\/ __ \\/ ___/ __/ /_/ / / / / / ___/ _ \\",
    " ___/ / /_/ / /_/ / /  / /_/ ____/ /_/ / (__  )  __/",
    "/____/ .___/\\____/_/   \\__/_/    \\__,_/_/____/\\___/ ",
    "    /_/                                              ",
]

TAGLINE = "  ◈  Live Scores  ·  Player Stats  ·  Standings  ◈  "

# ─────────────────────────────────────────────────────────────────────────────
# PLAYER STATS TABLE COLUMNS  (header, width, alignment)
# ─────────────────────────────────────────────────────────────────────────────

NBA_TABLE_COLS: List[Tuple[str, int, str]] = [
    ("RK",     3,  "right"),
    ("",       1,  "left"),
    ("PLAYER", 22, "left"),
    ("TEAM",   4,  "left"),
    ("POS",    3,  "center"),
    ("MIN",    5,  "right"),
    ("PTS",    4,  "right"),
    ("REB",    4,  "right"),
    ("AST",    4,  "right"),
    ("STL",    3,  "right"),
    ("BLK",    3,  "right"),
    ("FG",     7,  "center"),
    ("3PT",    7,  "center"),
    ("FT",     6,  "center"),
    ("+/-",    4,  "right"),
]

NHL_TABLE_COLS: List[Tuple[str, int, str]] = [
    ("RK",     3,  "right"),
    ("",       1,  "left"),
    ("PLAYER", 22, "left"),
    ("TEAM",   4,  "left"),
    ("POS",    3,  "center"),
    ("TOI",    5,  "right"),
    ("G",      3,  "right"),
    ("A",      3,  "right"),
    ("PTS",    3,  "right"),
    ("+/-",    4,  "right"),
    ("SOG",    4,  "right"),
    ("BS",     4,  "right"),
    ("HITS",   4,  "right"),
    ("PIM",    4,  "right"),
    ("FO%",    5,  "right"),
]

AFL_TABLE_COLS: List[Tuple[str, int, str]] = [
    ("RK",     3,  "right"),
    ("",       1,  "left"),
    ("PLAYER", 20, "left"),
    ("TEAM",   4,  "left"),
    ("POS",    3,  "center"),
    ("FPTS",   4,  "right"),
    ("D",      4,  "right"),
    ("K",      3,  "right"),
    ("HB",     3,  "right"),
    ("M",      3,  "right"),
    ("T",      3,  "right"),
    ("G",      3,  "right"),
    ("B",      3,  "right"),
    ("HO",     3,  "right"),
    ("I50",    4,  "right"),
    ("R50",    4,  "right"),
    ("FF",     3,  "right"),
    ("FA",     3,  "right"),
]

NFL_TABLE_COLS: List[Tuple[str, int, str]] = [
    ("RK",     3,  "right"),
    ("",       1,  "left"),
    ("PLAYER", 18, "left"),
    ("TEAM",   4,  "left"),
    ("POS",    3,  "center"),
    ("C/ATT",  7,  "center"),
    ("YDS",    4,  "right"),
    ("TD",     3,  "right"),
    ("INT",    3,  "right"),
    ("CAR",    3,  "right"),
    ("RYDS",   4,  "right"),
    ("REC",    3,  "right"),
    ("WYDS",   4,  "right"),
    ("TKL",    3,  "right"),
    ("SKS",    3,  "right"),
]

SPORT_TABLE_COLS: Dict[str, List[Tuple[str, int, str]]] = {
    "nba": NBA_TABLE_COLS,
    "nhl": NHL_TABLE_COLS,
    "afl": AFL_TABLE_COLS,
    "nfl": NFL_TABLE_COLS,
}

# ─────────────────────────────────────────────────────────────────────────────
# LADDER COLUMNS  (header, width, alignment)
# ─────────────────────────────────────────────────────────────────────────────

NBA_LADDER_COLS: List[Tuple[str, int, str]] = [
    ("RK",      3,  "right"),
    ("TEAM",   22,  "left"),   # "DET  Detroit Pistons"
    ("W",       3,  "right"),
    ("L",       3,  "right"),
    ("PCT",     5,  "right"),
    ("DIFF",    5,  "right"),
    ("STK",     4,  "right"),
    ("LAST 10", 9,  "center"),
]

NHL_LADDER_COLS: List[Tuple[str, int, str]] = [
    ("RK",     3,  "right"),
    ("TEAM",  22,  "left"),
    ("W",      3,  "right"),
    ("L",      3,  "right"),
    ("OTL",    3,  "right"),
    ("PTS",    4,  "right"),
    ("DIFF",   5,  "right"),
    ("STK",    4,  "right"),
]

AFL_LADDER_COLS: List[Tuple[str, int, str]] = [
    ("RK",     3,  "right"),
    ("TEAM",  22,  "left"),
    ("W",      3,  "right"),
    ("L",      3,  "right"),
    ("D",      3,  "right"),
    ("PTS",    4,  "right"),
    ("%",      7,  "right"),
    ("DIFF",   5,  "right"),
    ("FORM",   7,  "center"),
]

NFL_LADDER_COLS: List[Tuple[str, int, str]] = [
    ("RK",     3,  "right"),
    ("TEAM",  22,  "left"),
    ("W",      3,  "right"),
    ("L",      3,  "right"),
    ("T",      3,  "right"),
    ("PCT",    5,  "right"),
    ("DIFF",   5,  "right"),
    ("STK",    4,  "right"),
]

SPORT_LADDER_COLS: Dict[str, List[Tuple[str, int, str]]] = {
    "nba": NBA_LADDER_COLS,
    "nhl": NHL_LADDER_COLS,
    "afl": AFL_LADDER_COLS,
    "nfl": NFL_LADDER_COLS,
}

# ─────────────────────────────────────────────────────────────────────────────
# COLOR PAIRS
# ─────────────────────────────────────────────────────────────────────────────

CP: Dict[str, int] = {}

_COLOR_DEFS = [
    ("header",      curses.COLOR_BLACK,  curses.COLOR_CYAN),    # top nav bars
    ("selected",    curses.COLOR_BLACK,  curses.COLOR_YELLOW),   # highlighted row
    ("live_badge",  curses.COLOR_WHITE,  curses.COLOR_RED),      # ● LIVE
    ("upcoming_b",  curses.COLOR_BLACK,  curses.COLOR_GREEN),    # UPCOMING
    ("logo",        curses.COLOR_CYAN,   -1),                    # ASCII art
    ("col_hdr",     curses.COLOR_BLACK,  curses.COLOR_WHITE),    # table headers
    ("positive",    curses.COLOR_GREEN,  -1),                    # rank-up / +diff
    ("negative",    curses.COLOR_RED,    -1),                    # rank-down / -diff
    ("away_col",    curses.COLOR_CYAN,   -1),                    # away team / score
    ("home_col",    curses.COLOR_GREEN,  -1),                    # home team / score
    ("status_bar",  curses.COLOR_BLACK,  curses.COLOR_WHITE),    # bottom status
    ("section",     curses.COLOR_YELLOW, -1),                    # ladder group hdr
    ("final_badge", curses.COLOR_WHITE,  -1),                    # FINAL (no bg)
    ("accent",      curses.COLOR_YELLOW, -1),                    # highlights
    ("box_border",  curses.COLOR_CYAN,   -1),                    # score box border
    ("dim",         curses.COLOR_WHITE,  -1),
    ("tc_red",     curses.COLOR_RED,     -1),
    ("tc_green",   curses.COLOR_GREEN,   -1),
    ("tc_yellow",  curses.COLOR_YELLOW,  -1),
    ("tc_blue",    curses.COLOR_BLUE,    -1),
    ("tc_magenta", curses.COLOR_MAGENTA, -1),
    ("tc_cyan",    curses.COLOR_CYAN,    -1),
    ("tc_white",   curses.COLOR_WHITE,   -1),
]


def init_colors() -> None:
    curses.start_color()
    curses.use_default_colors()
    for i, (name, fg, bg) in enumerate(_COLOR_DEFS, start=1):
        curses.init_pair(i, fg, bg)
        CP[name] = i


def cp(name: str, bold: bool = False, dim: bool = False) -> int:
    attr = curses.color_pair(CP.get(name, 0))
    if bold:  attr |= curses.A_BOLD
    if dim:   attr |= curses.A_DIM
    return attr


_TC_PAIR = {
    curses.COLOR_RED:     "tc_red",
    curses.COLOR_GREEN:   "tc_green",
    curses.COLOR_YELLOW:  "tc_yellow",
    curses.COLOR_BLUE:    "tc_blue",
    curses.COLOR_MAGENTA: "tc_magenta",
    curses.COLOR_CYAN:    "tc_cyan",
    curses.COLOR_WHITE:   "tc_white",
}

def cp_team(sport: str, abbrev: str, bold: bool = False) -> int:
    """Return a curses attribute for a team's brand colour."""
    color = TEAM_COLORS.get(sport, {}).get(abbrev, curses.COLOR_WHITE)
    return cp(_TC_PAIR.get(color, "dim"), bold=bold)


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

def _period_str_nba(p: int) -> str:
    if p == 0:   return ""
    if p <= 4:   return f"Q{p}"
    if p == 5:   return "OT"
    return f"OT{p - 4}"

def _period_str_nhl(p: int) -> str:
    if p == 0:   return ""
    if p <= 3:   return f"P{p}"
    if p == 4:   return "OT"
    return "SO"

def _period_str_afl(p: int) -> str:
    if p == 0:   return ""
    if p <= 4:   return f"Q{p}"
    return "OT"

_PERIOD_FN: Dict[str, Callable[[int], str]] = {
    "nba": _period_str_nba,
    "nhl": _period_str_nhl,
    "afl": _period_str_afl,
    "nfl": _period_str_nba,  # NFL uses quarters Q1-Q4 like NBA
}

def _afl_fpts(k: int, hb: int, m: int, t: int, g: int, b: int,
              ho: int, ff: int, fa: int, i50: int, r50: int) -> int:
    """AFL Fantasy points (standard AFL Fantasy / Dream Team scoring)."""
    return k*3 + hb*2 + m*3 + t*4 + g*8 + b + ho + ff + fa*-1 + i50 + r50

def _streak_str(val: float) -> Tuple[str, str]:
    """Return (display_str, color_key) for a streak value."""
    n = int(val)
    if n > 0:   return f"W{n}", "positive"
    if n < 0:   return f"L{abs(n)}", "negative"
    return "-", ""


# ─────────────────────────────────────────────────────────────────────────────
# ESPN DATA LAYER — FETCH
# ─────────────────────────────────────────────────────────────────────────────

def fetch_scoreboard(sport: str, params: Optional[Dict] = None) -> Optional[Dict]:
    try:
        r = requests.get(SPORT_URLS[sport]["scoreboard"], params=params or {}, timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def fetch_game_detail(event_id: str, sport: str) -> Optional[Dict]:
    try:
        r = requests.get(SPORT_URLS[sport]["summary"],
                         params={"event": event_id}, timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def fetch_standings(sport: str) -> Optional[Dict]:
    try:
        r = requests.get(SPORT_URLS[sport]["standings"], timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# ESPN DATA LAYER — PARSE GAMES
# ─────────────────────────────────────────────────────────────────────────────

def _afl_score_from_linescores(linescores: list, fallback: str) -> str:
    """Return 'G.B.Total' string from cumulative linescores, else fallback."""
    if not linescores:
        return fallback
    last = linescores[-1]
    g = last.get("cumulativeGoalsDisplayValue", "")
    b = last.get("cumulativeBehindsDisplayValue", "")
    return f"{g}.{b}.{fallback}" if g and b else fallback

def parse_games(data: Dict, sport: str = "nba") -> List[Dict]:
    period_fn = _PERIOD_FN.get(sport, _period_str_nba)
    games: List[Dict] = []
    for event in (data or {}).get("events", []):
        comp  = (event.get("competitions") or [{}])[0]
        stat  = comp.get("status", {})
        stype = stat.get("type", {})
        state = stype.get("state", "pre")

        g_status = "live" if state == "in" else "final" if state == "post" else "upcoming"

        comps  = comp.get("competitors", [])
        home   = next((c for c in comps if c.get("homeAway") == "home"), {})
        away   = next((c for c in comps if c.get("homeAway") == "away"), {})
        home_t = home.get("team", {})
        away_t = away.get("team", {})

        h_sc = str(home.get("score", "0") or "0")
        a_sc = str(away.get("score", "0") or "0")
        if sport == "afl":
            h_sc = _afl_score_from_linescores(home.get("linescores", []), h_sc)
            a_sc = _afl_score_from_linescores(away.get("linescores", []), a_sc)

        games.append({
            "id":          event.get("id", ""),
            "status":      g_status,
            "home_name":   home_t.get("displayName", "Home"),
            "home_abbrev": home_t.get("abbreviation", "HOM"),
            "home_score":  h_sc,
            "away_name":   away_t.get("displayName", "Away"),
            "away_abbrev": away_t.get("abbreviation", "AWY"),
            "away_score":  a_sc,
            "period":      period_fn(stat.get("period", 0)),
            "clock":       stat.get("displayClock", ""),
            "detail":      stype.get("shortDetail", stype.get("detail", "")),
            "date":        event.get("date", ""),
        })
    return games


# ─────────────────────────────────────────────────────────────────────────────
# ESPN DATA LAYER — BOXSCORE PARSERS
# ─────────────────────────────────────────────────────────────────────────────

def _parse_header_scores(data: Dict, sport: str) -> Dict:
    hcomp  = (data.get("header", {}).get("competitions") or [{}])[0]
    hstat  = hcomp.get("status", {})
    htype  = hstat.get("type", {})
    hcomps = hcomp.get("competitors", [])
    home   = next((c for c in hcomps if c.get("homeAway") == "home"), {})
    away   = next((c for c in hcomps if c.get("homeAway") == "away"), {})
    period_fn = _PERIOD_FN.get(sport, _period_str_nba)

    home_score = str(home.get("score", "0") or "0")
    away_score = str(away.get("score", "0") or "0")
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

def _dnp_label(ab: Dict, did_not_play: bool) -> str:
    reason = ab.get("reason", "")
    if reason:
        ru = reason.upper()
        if "INJURY" in ru or "INJURED" in ru:              return "INJ"
        if "SUSPENSION" in ru or "SUSPENDED" in ru:        return "SUSP"
        if "ILLNESS" in ru:                                return "ILL"
        if "REST" in ru:                                   return "REST"
        if "NOT WITH TEAM" in ru or "PERSONAL" in ru:     return "AWAY"
        if did_not_play:                                   return "DNP"
        return ""
    return "DNP" if did_not_play else ""

def parse_nba_boxscore(data: Dict) -> Tuple[Dict, List[Dict]]:
    if not data:
        return {}, []
    game_header = _parse_header_scores(data, "nba")
    players: List[Dict] = []
    for tb in data.get("boxscore", {}).get("players", []):
        abbrev = tb.get("team", {}).get("abbreviation", "")
        for sb in tb.get("statistics", []):
            names = [n.upper() for n in (sb.get("names") or [])]
            for ab in sb.get("athletes", []):
                raw = ab.get("stats", [])
                sm  = dict(zip(names, raw)) if raw else {}
                ath = ab.get("athlete", {})
                raw_min = sm.get("MIN", "0")
                dnp = (not raw_min or raw_min in ("0", "0:00")
                       or (not raw and ab.get("didNotPlay", False)))
                players.append({
                    "name":         ath.get("displayName", "Unknown"),
                    "pos":          ath.get("position", {}).get("abbreviation", ""),
                    "team":         abbrev,
                    "did_not_play": dnp,
                    "status_label": _dnp_label(ab, dnp),
                    "min":          raw_min if not dnp else "0:00",
                    "pts":          _int(sm.get("PTS", "0")),
                    "reb":          _int(sm.get("REB", "0")),
                    "ast":          _int(sm.get("AST", "0")),
                    "stl":          _int(sm.get("STL", "0")),
                    "blk":          _int(sm.get("BLK", "0")),
                    "fg":           sm.get("FG",  "0-0"),
                    "fg3":          sm.get("3PT", "0-0"),
                    "ft":           sm.get("FT",  "0-0"),
                    "pm":           sm.get("+/-", "0"),
                    "athlete_id":   ath.get("id", ""),
                })
    active   = [p for p in players if not p["did_not_play"]]
    inactive = [p for p in players if p["did_not_play"]]
    active.sort(key=lambda p: (p["pts"], p["ast"], p["reb"]), reverse=True)
    return game_header, active + inactive

def parse_nhl_boxscore(data: Dict) -> Tuple[Dict, List[Dict]]:
    if not data:
        return {}, []
    game_header = _parse_header_scores(data, "nhl")
    players: List[Dict] = []
    for tb in data.get("boxscore", {}).get("players", []):
        abbrev = tb.get("team", {}).get("abbreviation", "")
        for sb in tb.get("statistics", []):
            labels = [l.upper() for l in (sb.get("labels") or [])]
            for ab in sb.get("athletes", []):
                raw = ab.get("stats", [])
                sm  = dict(zip(labels, raw)) if raw else {}
                ath = ab.get("athlete", {})
                toi = sm.get("TOI", "")
                dnp = not toi or toi in ("0:00", "00:00", "0")
                g   = _int(sm.get("G", "0"))
                a   = _int(sm.get("A", "0"))
                players.append({
                    "name":         ath.get("displayName", "Unknown"),
                    "pos":          ath.get("position", {}).get("abbreviation", ""),
                    "team":         abbrev,
                    "did_not_play": dnp,
                    "status_label": _dnp_label(ab, dnp),
                    "toi":          toi if not dnp else "0:00",
                    "g":            g,
                    "a":            a,
                    "pts":          g + a,
                    "pm":           sm.get("+/-", "0"),
                    "sog":          _int(sm.get("S",   "0")),
                    "bs":           _int(sm.get("BS",  "0")),
                    "ht":           _int(sm.get("HT",  "0")),
                    "pim":          _int(sm.get("PIM", "0")),
                    "fopct":        sm.get("FO%", "-"),
                    "athlete_id":   ath.get("id", ""),
                })
    active   = [p for p in players if not p["did_not_play"]]
    inactive = [p for p in players if p["did_not_play"]]
    active.sort(key=lambda p: (p["pts"], p["g"], p["sog"]), reverse=True)
    return game_header, active + inactive

def parse_afl_boxscore(data: Dict) -> Tuple[Dict, List[Dict]]:
    if not data:
        return {}, []
    game_header = _parse_header_scores(data, "afl")
    players: List[Dict] = []
    for tb in data.get("boxscore", {}).get("players", []):
        abbrev = tb.get("team", {}).get("abbreviation", "")
        for sb in tb.get("statistics", []):
            labels = [l.upper() for l in (sb.get("labels") or [])]
            for ab in sb.get("athletes", []):
                raw = ab.get("stats", [])
                sm  = dict(zip(labels, raw)) if raw else {}
                ath = ab.get("athlete", {})
                k, hb, m, t  = _int(sm.get("K","0")), _int(sm.get("H","0")), _int(sm.get("M","0")), _int(sm.get("T","0"))
                g, b, ho     = _int(sm.get("G","0")), _int(sm.get("B","0")), _int(sm.get("HO","0"))
                ff, fa       = _int(sm.get("FF","0")), _int(sm.get("FA","0"))
                i50, r50     = _int(sm.get("I50","0")), _int(sm.get("R50","0"))
                d            = _int(sm.get("D", "0"))
                dnp = (ab.get("active") is False or not raw
                       or (d == 0 and g == 0 and t == 0 and m == 0
                           and ab.get("didNotPlay", False)))
                players.append({
                    "name":         ath.get("displayName", "Unknown"),
                    "pos":          ath.get("position", {}).get("abbreviation", ""),
                    "team":         abbrev,
                    "did_not_play": dnp,
                    "status_label": _dnp_label(ab, dnp),
                    "fpts":         _afl_fpts(k, hb, m, t, g, b, ho, ff, fa, i50, r50),
                    "d":  d, "k":  k, "hb": hb, "m":  m, "t":  t,
                    "g":  g, "b":  b, "ho": ho, "i50": i50, "r50": r50,
                    "ff": ff, "fa": fa,
                    "athlete_id":   ath.get("id", ""),
                })
    active   = [p for p in players if not p["did_not_play"]]
    inactive = [p for p in players if p["did_not_play"]]
    active.sort(key=lambda p: (p["fpts"], p["d"]), reverse=True)
    return game_header, active + inactive

def _nfl_empty_player(name: str, team: str, ath: Dict) -> Dict:
    return {
        "name":         name,
        "pos":          ath.get("position", {}).get("abbreviation", ""),
        "team":         team,
        "did_not_play": False,
        "status_label": "",
        "athlete_id":   ath.get("id", ""),
        "catt":  "0/0", "pyds": 0, "ptd":  0, "int_thrown": 0,
        "car":   0,     "ryds": 0, "rtd":  0,
        "rec":   0,     "wyds": 0, "wtd":  0,
        "tkl":   0,     "sacks": 0.0, "def_int": 0,
    }

def _nfl_merge_category(p: Dict, category: str, sm: Dict) -> None:
    if category == "passing":
        p["catt"]        = sm.get("C/ATT", "0/0")
        p["pyds"]        = _int(sm.get("YDS",  "0"))
        p["ptd"]         = _int(sm.get("TD",   "0"))
        p["int_thrown"]  = _int(sm.get("INT",  "0"))
    elif category == "rushing":
        p["car"]  = _int(sm.get("CAR", "0"))
        p["ryds"] = _int(sm.get("YDS", "0"))
        p["rtd"]  = _int(sm.get("TD",  "0"))
    elif category == "receiving":
        p["rec"]  = _int(sm.get("REC", "0"))
        p["wyds"] = _int(sm.get("YDS", "0"))
        p["wtd"]  = _int(sm.get("TD",  "0"))
    elif category in ("defensive", "defense"):
        p["tkl"]   = _int(sm.get("TOT", "0"))
        try:
            p["sacks"] = float(str(sm.get("SACKS", "0")).replace("-", ".") or "0")
        except (ValueError, TypeError):
            p["sacks"] = 0.0
    elif category == "interceptions":
        p["def_int"] = _int(sm.get("INT", "0"))

def parse_nfl_boxscore(data: Dict) -> Tuple[Dict, List[Dict]]:
    if not data:
        return {}, []
    game_header = _parse_header_scores(data, "nfl")
    player_map: Dict[Tuple[str, str], Dict] = {}

    for tb in data.get("boxscore", {}).get("players", []):
        abbrev = tb.get("team", {}).get("abbreviation", "")
        for sb in tb.get("statistics", []):
            category = sb.get("name", "")
            names = [n.upper() for n in (sb.get("names") or [])]
            for ab in sb.get("athletes", []):
                raw = ab.get("stats", [])
                sm  = dict(zip(names, raw)) if raw else {}
                ath = ab.get("athlete", {})
                player_name = ath.get("displayName", "Unknown")
                key = (player_name, abbrev)
                if key not in player_map:
                    player_map[key] = _nfl_empty_player(player_name, abbrev, ath)
                _nfl_merge_category(player_map[key], category, sm)

    players = list(player_map.values())
    players.sort(key=lambda p: (
        -p["pyds"],
        -(p["ryds"] + p["wyds"]),
        -p["tkl"],
    ))
    return game_header, players

_PARSE_BOXSCORE = {
    "nba": parse_nba_boxscore,
    "nhl": parse_nhl_boxscore,
    "afl": parse_afl_boxscore,
    "nfl": parse_nfl_boxscore,
}


_AFL_SCORE_TYPES = {"goal", "behind", "rushed"}

def parse_timeline(data: Dict) -> List[Dict]:
    """Extract scoring plays from ESPN summary data, most-recent first.
    NBA/NHL/NFL use scoringPlay=True; AFL uses type.type in goal/behind/rushed."""
    plays = data.get("plays", []) if data else []
    result = []
    for p in plays:
        type_obj  = p.get("type", {})
        type_name = type_obj.get("type", "") if isinstance(type_obj, dict) else ""
        is_scoring = p.get("scoringPlay") or type_name in _AFL_SCORE_TYPES
        if not is_scoring:
            continue
        period_val = p.get("period", {})
        # AFL periods are just numbers; NBA/NHL have displayValue
        if isinstance(period_val, dict):
            period_str = period_val.get("displayValue") or f"Q{period_val.get('number', '')}"
        else:
            period_str = str(period_val)
        clock_val = p.get("clock", {})
        clock_str = clock_val.get("displayValue", "") if isinstance(clock_val, dict) else str(clock_val)
        team_obj  = p.get("team", {})
        team_id   = team_obj.get("id", "") if isinstance(team_obj, dict) else ""
        # Use type text as label for AFL (Goal / Behind / Rushed)
        type_label = type_obj.get("text", "") if isinstance(type_obj, dict) else ""
        text = p.get("text", "")
        result.append({
            "text":       text,
            "short_text": p.get("shortDescription", text),
            "type_label": type_label,
            "period":     period_str,
            "clock":      clock_str,
            "away_score": str(p.get("awayScore", "")),
            "home_score": str(p.get("homeScore", "")),
            "team_id":    team_id,
            "score_val":  p.get("scoreValue", 0),
        })
    result.reverse()  # most recent first
    return result


def parse_h2h(data: Dict) -> Dict:
    """Extract head-to-head data from ESPN summary.
    NBA/NHL/NFL use seasonseries; AFL uses lastFiveGames."""
    if not data:
        return {}

    # Standard leagues: seasonseries
    series_list = data.get("seasonseries", [])
    if series_list:
        s = series_list[0]
        games = []
        for ev in s.get("events", []):
            comps = ev.get("competitors", [])
            home  = next((c for c in comps if c.get("homeAway") == "home"), {})
            away  = next((c for c in comps if c.get("homeAway") == "away"), {})
            date_str = ev.get("date", "")
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                date_fmt = dt.strftime("%b %-d")
            except Exception:
                date_fmt = date_str[:10]
            games.append({
                "date":        date_fmt,
                "away_abbrev": away.get("team", {}).get("abbreviation", "AWY"),
                "home_abbrev": home.get("team", {}).get("abbreviation", "HOM"),
                "away_score":  str(away.get("score", "?")),
                "home_score":  str(home.get("score", "?")),
                "away_winner": away.get("winner", False),
                "home_winner": home.get("winner", False),
            })
        return {
            "summary":      s.get("summary", s.get("shortSummary", "")),
            "description":  s.get("description", ""),
            "series_label": s.get("seriesLabel", "Season Series"),
            "games":        games,
        }

    # AFL: lastFiveGames — find meetings between the two teams by matching game IDs
    lfg = data.get("lastFiveGames", [])
    if len(lfg) < 2:
        return {}
    t0 = lfg[0]
    t1 = lfg[1]
    t0_evs = {ev["id"]: ev for ev in t0.get("events", [])}
    t1_evs = {ev["id"]: ev for ev in t1.get("events", [])}
    common_ids = sorted(set(t0_evs) & set(t1_evs))

    t0_abbrev = t0.get("team", {}).get("abbreviation", "T1")
    t1_abbrev = t1.get("team", {}).get("abbreviation", "T2")
    t0_id     = t0.get("team", {}).get("id", "")

    games = []
    for gid in common_ids:
        ev = t0_evs[gid]
        date_str = ev.get("gameDate", "")
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            date_fmt = dt.strftime("%b %-d")
        except Exception:
            date_fmt = date_str[:10]
        home_id  = ev.get("homeTeamId", "")
        t0_home  = (home_id == t0_id)
        if t0_home:
            home_abbrev, away_abbrev = t0_abbrev, t1_abbrev
            home_score = ev.get("homeTeamScore", "?")
            away_score = ev.get("awayTeamScore", "?")
            home_winner = ev.get("gameResult") == "W"
            away_winner = not home_winner
        else:
            home_abbrev, away_abbrev = t1_abbrev, t0_abbrev
            home_score = ev.get("homeTeamScore", "?")
            away_score = ev.get("awayTeamScore", "?")
            away_winner = ev.get("gameResult") == "W"
            home_winner = not away_winner
        games.append({
            "date":        date_fmt,
            "away_abbrev": away_abbrev,
            "home_abbrev": home_abbrev,
            "away_score":  away_score,
            "home_score":  home_score,
            "away_winner": away_winner,
            "home_winner": home_winner,
        })

    if not games:
        # No H2H meetings in last 5 — show recent form for each team
        return {
            "summary":      f"No recent meetings (last 5 games shown per team)",
            "description":  "",
            "series_label": "Recent Form",
            "games":        [],
            "recent_form":  [
                {"team": t0_abbrev, "results": [ev.get("gameResult","?") for ev in t0.get("events",[])]},
                {"team": t1_abbrev, "results": [ev.get("gameResult","?") for ev in t1.get("events",[])]},
            ],
        }

    return {
        "summary":      f"{len(games)} recent meeting(s)",
        "description":  "",
        "series_label": "Recent Meetings",
        "games":        games,
    }


# Season stats web API paths (different from scoreboard paths)
_SEASON_STATS_BASE = "https://site.web.api.espn.com/apis/common/v3/sports"
_SEASON_STATS_PATHS: Dict[str, str] = {
    "nba": "basketball/nba",
    "nhl": "hockey/nhl",
    "afl": "australian-football/afl",
    "nfl": "football/nfl",
}

def fetch_season_stats(sport: str, athlete_id: str) -> Optional[Dict]:
    """Fetch a player's season averages. Returns parsed dict or None."""
    if sport == "afl":
        return None   # ESPN doesn't provide AFL season stats via web API
    path = _SEASON_STATS_PATHS.get(sport, "basketball/nba")
    url  = f"{_SEASON_STATS_BASE}/{path}/athletes/{athlete_id}/stats"
    try:
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        data = r.json()
        # Prefer "averages" category; fall back to first category with data
        cats = data.get("categories", [])
        chosen = next((c for c in cats if c.get("name") == "averages"), None)
        if chosen is None:
            chosen = next((c for c in cats if c.get("labels") and c.get("totals")), None)
        if chosen is None:
            return None
        labels = chosen.get("labels", [])
        totals = chosen.get("totals", [])
        if labels and totals:
            return {
                "labels":       labels,
                "values":       totals,
                "display_name": chosen.get("displayName", "Season Averages"),
            }
        return None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# ESPN DATA LAYER — STANDINGS PARSER
# ─────────────────────────────────────────────────────────────────────────────

def _sv(stats_by_name: Dict, key: str, default=0):
    return stats_by_name.get(key, {}).get("value", default) or default

def _sdv(stats_by_name: Dict, key: str, default: str = "") -> str:
    return stats_by_name.get(key, {}).get("displayValue", default) or default

def _parse_standing_entry(raw: Dict, sport: str) -> Dict:
    team  = raw.get("team", {})
    stats = {s["name"]: s for s in raw.get("stats", [])}
    streak_val = _sv(stats, "streak", 0)
    stk_str, stk_color = _streak_str(streak_val)
    return {
        "seed":     int(_sv(stats, "playoffSeed", 99)),
        "rank":     int(_sv(stats, "playoffSeed", 0)) or int(_sv(stats, "rank", 0)),
        "abbrev":   team.get("abbreviation", ""),
        "name":     team.get("displayName", ""),
        "wins":     int(_sv(stats, "wins", 0)),
        "losses":   int(_sv(stats, "losses", 0)),
        "ties":     int(_sv(stats, "ties", 0)),
        "otlosses": int(_sv(stats, "otLosses", 0) or _sv(stats, "overtimeLosses", 0)),
        "pct":      float(_sv(stats, "winPercent", 0) or _sv(stats, "leagueWinPercent", 0)),
        "pts":      int(_sv(stats, "points", 0)),          # NHL points or AFL ladder pts
        "diff":     int(_sv(stats, "pointDifferential", 0)),
        "pts_for":  int(_sv(stats, "pointsFor", 0)),
        "pct_afl":  float(_sv(stats, "percentage", 0)),    # AFL scoring % (for/against)
        "stk_str":  stk_str,
        "stk_color": stk_color,
        "form":     _sdv(stats, "form", ""),
        "last10":   _sdv(stats, "Last Ten Games", ""),
        "overall":  _sdv(stats, "overall", ""),
    }

def parse_standings(data: Dict, sport: str) -> List[Dict]:
    """Return list of groups; each group = {name, entries}."""
    groups = []
    if sport == "afl":
        raw_entries = data.get("standings", {}).get("entries", [])
        entries = [_parse_standing_entry(e, sport) for e in raw_entries]
        entries.sort(key=lambda e: (-e["pts"], -e["wins"], e["losses"]))
        for i, e in enumerate(entries):
            e["rank"] = i + 1
        groups.append({"name": "AFL Ladder", "entries": entries})
    else:
        for conf in data.get("children", []):
            raw = conf.get("standings", {}).get("entries", [])
            if not raw:
                for div in conf.get("children", []):
                    raw += div.get("standings", {}).get("entries", [])
            entries = [_parse_standing_entry(e, sport) for e in raw]
            # Sort by playoff seed with original API order as tiebreaker
            for i, e in enumerate(entries):
                e["_api_order"] = i
            entries.sort(key=lambda e: (e["seed"] if e["seed"] < 99 else 999,
                                        e["_api_order"]))
            for i, e in enumerate(entries):
                e["rank"] = i + 1
            groups.append({"name": conf.get("name", ""), "entries": entries})
    return groups


# ─────────────────────────────────────────────────────────────────────────────
# UTILITY
# ─────────────────────────────────────────────────────────────────────────────

def _flatten_games(games: List[Dict]) -> List[Dict]:
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

        # State machine: sport_select | game_list | game_detail | ladder
        self.state         = "sport_select"
        self.current_sport = "nba"

        # Navigation indices
        self.sport_idx     = 0
        self.game_idx      = 0
        self.game_scroll   = 0
        self.player_scroll = 0   # viewport offset (first visible row)
        self.player_cursor = 0   # absolute index of selected player in visible list
        self.ladder_scroll = 0
        self.team_filter   = 0   # 0=All, 1=Away, 2=Home

        # Round / date navigation
        self.nav_offset  = 0    # offset from current round/date
        self.base_round  = 0    # current round/week (detected on first fetch)

        # Cached data
        self.games:        List[Dict]      = []
        self.game_header:  Dict            = {}
        self.players:      List[Dict]      = []
        self.rank_changes: Dict[str, int]  = {}
        self._prev_ranks:  Dict[str, int]  = {}
        self.ladder_data:  List[Dict]      = []   # list of groups
        self.last_refresh: Optional[float] = None
        self.fetch_error:  Optional[str]   = None
        self.loading                       = False
        self.current_game_id: Optional[str] = None

        # Game detail sub-modes: stats | timeline | h2h
        self.detail_mode      = "stats"
        self.timeline_plays:  List[Dict]      = []
        self.h2h_data:        Dict            = {}
        self.timeline_scroll  = 0
        self.h2h_scroll       = 0

        # Player season stats
        self.season_stats:         Optional[Dict] = None
        self.season_stats_loading  = False
        self.current_player_id:    Optional[str]  = None
        self.current_player_name:  str            = ""
        self._season_stats_cache:  Dict[str, Dict] = {}   # (sport,id) → stats

        self._fetch_token: Tuple = ("", None, "nba")
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
                    self.scr.addstr(0, 0,
                        "Terminal too small — please resize (min 60×18)"[:w])
                    self.scr.refresh()
                    if self.scr.getch() == ord("q"):
                        break
                    continue
                self._draw()
                key = self.scr.getch()
            except curses.error:
                continue

            if key in (ord("q"), 27):
                if self.state == "player_season":
                    self.state = "game_detail"
                elif self.state == "game_detail":
                    self.state = "game_list"
                    self.player_scroll = 0
                elif self.state == "ladder":
                    self.state = "game_list"
                    self._wake.set()
                elif self.state == "game_list":
                    self.state = "sport_select"
                    with self._lock:
                        self.games = []
                    self.nav_offset = 0
                    self.base_round = 0
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

            elif key in (ord("p"), ord("P")):
                if self.state == "game_list":
                    self.nav_offset -= 1
                    with self._lock:
                        self.games = []
                    self.game_idx = 0
                    self._wake.set()

            elif key in (ord("f"), ord("F")):
                if self.state == "game_list":
                    self.nav_offset += 1
                    with self._lock:
                        self.games = []
                    self.game_idx = 0
                    self._wake.set()

            elif key in (ord("l"), ord("L")):
                if self.state == "game_list":
                    self.state = "ladder"
                    with self._lock:
                        self.ladder_data = []
                    self.ladder_scroll = 0
                    self._wake.set()
                elif self.state == "ladder":
                    self.state = "game_list"
                    self._wake.set()

            elif key == ord("\t"):
                if self.state == "game_detail":
                    self.team_filter   = (self.team_filter + 1) % 3
                    self.player_scroll = 0
                    self.player_cursor = 0

            elif key in (ord("k"), ord("K")):
                if self.state == "game_detail":
                    url = KAYO_URLS.get(self.current_sport, "https://kayosports.com.au/")
                    webbrowser.open(url)

            elif key in (ord("t"), ord("T")):
                if self.state == "game_detail":
                    self.detail_mode     = "timeline"
                    self.timeline_scroll = 0

            elif key in (ord("h"), ord("H")):
                if self.state == "game_detail":
                    self.detail_mode  = "h2h"
                    self.h2h_scroll   = 0

            elif key in (ord("s"), ord("S")):
                if self.state == "game_detail":
                    self.detail_mode   = "stats"
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
            if self.detail_mode == "timeline":
                self.timeline_scroll = max(0, self.timeline_scroll - 1)
            elif self.detail_mode == "h2h":
                self.h2h_scroll = max(0, self.h2h_scroll - 1)
            else:
                self.player_cursor = max(0, self.player_cursor - 1)
        elif self.state == "player_season":
            pass
        elif self.state == "ladder":
            self.ladder_scroll = max(0, self.ladder_scroll - 1)

    def _on_down(self) -> None:
        if self.state == "sport_select":
            self.sport_idx = min(len(SPORTS) - 1, self.sport_idx + 1)
        elif self.state == "game_list":
            with self._lock:
                games = list(self.games)
            flat = _flatten_games(games)
            self.game_idx = min(max(0, len(flat) - 1), self.game_idx + 1)
        elif self.state == "game_detail":
            if self.detail_mode == "timeline":
                with self._lock:
                    n = len(self.timeline_plays)
                self.timeline_scroll = min(max(0, n - 1), self.timeline_scroll + 1)
            elif self.detail_mode == "h2h":
                with self._lock:
                    n = len(self.h2h_data.get("games", []))
                self.h2h_scroll = min(max(0, n - 1), self.h2h_scroll + 1)
            else:
                with self._lock:
                    n = len(self.players)
                self.player_cursor = min(max(0, n - 1), self.player_cursor + 1)
        elif self.state == "ladder":
            self.ladder_scroll += 1  # clamped in renderer

    def _on_enter(self) -> None:
        if self.state == "sport_select":
            sport = SPORTS[self.sport_idx]
            if sport["available"]:
                self.current_sport = sport["id"]
                self.nav_offset    = 0
                self.base_round    = 0
                self.state         = "game_list"
                self.game_idx      = 0
                self.game_scroll   = 0
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
                self.player_cursor = 0
                self.team_filter   = 0
                self.detail_mode    = "stats"
                self.timeline_plays = []
                self.h2h_data       = {}
                self.timeline_scroll= 0
                self.h2h_scroll     = 0
                self.state         = "game_detail"
                self._wake.set()

        elif self.state == "game_detail" and self.detail_mode == "stats":
            # Enter on a player → season stats
            with self._lock:
                players = list(self.players)
                away_abbrev = self.game_header.get("away_abbrev", "")
                home_abbrev = self.game_header.get("home_abbrev", "")
            # Reconstruct visible list same as _game_detail
            if self.team_filter == 1:
                visible = [p for p in players if p["team"] == away_abbrev]
            elif self.team_filter == 2:
                visible = [p for p in players if p["team"] == home_abbrev]
            else:
                visible = players
            if visible and self.player_cursor < len(visible):
                p = visible[self.player_cursor]
                aid = p.get("athlete_id", "")
                if aid:
                    self.current_player_id   = aid
                    self.current_player_name = p.get("name", "")
                    cache_key = f"{self.current_sport}:{aid}"
                    if cache_key in self._season_stats_cache:
                        self.season_stats = self._season_stats_cache[cache_key]
                        self.state = "player_season"
                    else:
                        self.season_stats = None
                        self.season_stats_loading = True
                        self.state = "player_season"
                        threading.Thread(
                            target=self._load_season_stats,
                            args=(cache_key, self.current_sport, aid),
                            daemon=True
                        ).start()

    # ── Background refresh ────────────────────────────────────────────────────

    def _bg_loop(self) -> None:
        while self._running:
            self._fetch()
            live = (self.state == "game_detail"
                    and self.game_header.get("state") == "in")
            self._wake.wait(timeout=LIVE_REFRESH if live else REFRESH_INTERVAL)
            self._wake.clear()

    def _load_season_stats(self, cache_key: str, sport: str, athlete_id: str) -> None:
        stats = fetch_season_stats(sport, athlete_id)
        with self._lock:
            if cache_key == f"{self.current_sport}:{self.current_player_id}":
                self.season_stats = stats
                self.season_stats_loading = False
                if stats:
                    self._season_stats_cache[cache_key] = stats

    def _scoreboard_params(self) -> Dict:
        """Build ESPN scoreboard URL params based on sport and nav_offset."""
        sport  = self.current_sport
        offset = self.nav_offset
        params: Dict = {}
        if sport in ROUND_BASED_SPORTS:
            base = self.base_round
            if base > 0:
                week = max(1, base + offset)
                params["week"] = str(week)
                if sport == "nfl":
                    params["seasontype"] = "2"   # regular season
        else:
            if offset != 0:
                target = (datetime.now(timezone.utc).date()
                          + timedelta(days=offset))
                params["dates"] = target.strftime("%Y%m%d")
        return params

    def _round_label(self) -> str:
        sport  = self.current_sport
        offset = self.nav_offset
        if sport == "afl":
            rn = (self.base_round or 0) + offset
            return f"Round {rn}" if rn > 0 else "Current Round"
        if sport == "nfl":
            wk = (self.base_round or 0) + offset
            return f"Week {wk}" if wk > 0 else "Current Week"
        # Date-based
        target = (datetime.now(timezone.utc).date() + timedelta(days=offset))
        if offset == 0:
            return f"Today  ({target.strftime('%b %-d')})"
        return target.strftime("%a  %b %-d")

    def _fetch(self) -> None:
        sport = self.current_sport
        token = (self.state, self.current_game_id, sport, self.nav_offset)
        self._fetch_token = token
        self.loading = True
        try:
            state = token[0]

            if state == "game_list":
                params = self._scoreboard_params()
                data   = fetch_scoreboard(sport, params)
                with self._lock:
                    if self._fetch_token != token:
                        return
                    if data is not None:
                        # Always update base_round from current-round fetches
                        if self.nav_offset == 0:
                            wk = data.get("week", {}).get("number", 0)
                            if wk:
                                self.base_round = int(wk)
                        self.games        = parse_games(data, sport)
                        self.last_refresh = time.time()
                        self.fetch_error  = None
                    else:
                        self.fetch_error = "Network error — press r to retry"

            elif state == "ladder":
                data = fetch_standings(sport)
                with self._lock:
                    if self._fetch_token != token:
                        return
                    if data is not None:
                        self.ladder_data  = parse_standings(data, sport)
                        self.last_refresh = time.time()
                        self.fetch_error  = None
                    else:
                        self.fetch_error = "Network error — press r to retry"

            elif state == "game_detail" and token[1]:
                data = fetch_game_detail(token[1], sport)
                if data is not None:
                    parse_fn = _PARSE_BOXSCORE.get(sport, parse_nba_boxscore)
                    header, players = parse_fn(data)
                    timeline = parse_timeline(data)
                    h2h      = parse_h2h(data)
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
                        self.timeline_plays = timeline
                        self.h2h_data       = h2h
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
        self._add(y, max(0, (w - len(s)) // 2), s, attr)

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
        right = " ↑↓ Navigate  ↵ Select  P/F Round  L Ladder  ⇥ Filter  q Back  r Refresh "
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
        elif self.state == "game_detail":
            if   self.detail_mode == "timeline": self._game_timeline()
            elif self.detail_mode == "h2h":      self._game_h2h()
            else:                                self._game_detail()
        elif self.state == "ladder":       self._ladder()
        elif self.state == "player_season": self._player_season()
        self._status_bar()
        self.scr.refresh()

    # ── Screen: Sport Select ──────────────────────────────────────────────────

    def _sport_select(self) -> None:
        h, w = self.scr.getmaxyx()
        logo_w  = max(len(line) for line in LOGO)
        block_h = len(LOGO) + 1 + 1 + 1 + len(SPORTS) + 2
        sy      = max(1, (h - block_h) // 2)
        lx      = max(0, (w - logo_w) // 2)
        for i, line in enumerate(LOGO):
            self._add(sy + i, lx, line, cp("logo", bold=True))

        ty = sy + len(LOGO)
        self._add_center(ty, TAGLINE, cp("accent"))

        div_y = ty + 2
        self._add_center(div_y,
            "─────────────  SELECT SPORT  ─────────────", cp("dim"))

        SPORT_ICONS = {"nba": "🏀", "nhl": "🏒", "afl": "🏉", "nfl": "🏈"}
        list_y  = div_y + 2
        list_w  = 32
        list_x  = max(0, (w - list_w) // 2)

        for i, sport in enumerate(SPORTS):
            y    = list_y + i
            sel  = (i == self.sport_idx)
            icon = SPORT_ICONS.get(sport["id"], "  ")
            if sel:
                self._hline(y, list_x - 2, ord(" "), list_w + 4, cp("selected"))
                label_attr = cp("selected", bold=True)
                pfx = " ▶  "
            else:
                label_attr = curses.A_NORMAL
                pfx = "    "
            self._add(y, list_x, f"{pfx}{icon}  {sport['label']}", label_attr)

        self._add_center(h - 3, "  ↑↓  Navigate    ↵  Select    q  Quit  ",
                         curses.A_DIM)

    # ── Screen: Game List ─────────────────────────────────────────────────────

    def _game_list(self) -> None:
        h, w = self.scr.getmaxyx()
        sport_label = self.current_sport.upper()
        round_label = self._round_label()
        nav_hint    = " ← P    F → "
        title       = f"  {sport_label}  ·  {round_label}"
        self._bar(0, title, cp("header", bold=True))
        self._add(0, w - len(nav_hint) - 1, nav_hint, cp("header", bold=True))

        with self._lock:
            games = list(self.games)

        flat     = _flatten_games(games)
        live     = [g for g in games if g["status"] == "live"]
        upcoming = [g for g in games if g["status"] == "upcoming"]
        final    = [g for g in games if g["status"] == "final"]
        sections = [
            (live,     "  ● LIVE",     "live_badge"),
            (upcoming, "  UPCOMING",   "upcoming_b"),
            (final,    "  FINAL",      "col_hdr"),
        ]

        if not flat:
            if self.loading:
                self._add_center(h // 2, "⟳  Fetching games...", curses.A_DIM)
            else:
                self._add_center(h // 2 - 1,
                    f"No {sport_label} games  ·  {round_label}", curses.A_DIM)
                self._add_center(h // 2,
                    "  P / F  navigate rounds    r  refresh  ", curses.A_DIM)
                self._add_center(h // 2 + 1, "  L  →  view standings  ", curses.A_DIM)
            return

        self.game_idx = max(0, min(self.game_idx, len(flat) - 1))
        visible_rows  = h - 3
        if self.game_idx < self.game_scroll:
            self.game_scroll = self.game_idx
        elif self.game_idx >= self.game_scroll + visible_rows:
            self.game_scroll = self.game_idx - visible_rows + 1

        y = 1; flat_i = 0; row_abs = 0
        for glist, label, badge_key in sections:
            if not glist:
                continue
            if row_abs >= self.game_scroll and y < h - 2:
                self._fill_row(y, cp(badge_key))
                self._add(y, 0, label, cp(badge_key, bold=True))
                y += 1
            row_abs += 1
            for g in glist:
                if y >= h - 2:
                    break
                if row_abs >= self.game_scroll:
                    sel = (flat_i == self.game_idx)
                    if sel:
                        self._fill_row(y, cp("selected"))
                        pfx      = " ▶ "
                        row_attr = cp("selected", bold=True)
                    else:
                        pfx      = "   "
                        row_attr = curses.A_NORMAL

                    a_sc = g["away_score"]
                    h_sc = g["home_score"]
                    if g["status"] == "live":
                        left  = f"{pfx}{g['away_abbrev']:>4}"
                        mid   = f"{a_sc:>10}  –  {h_sc:<10}"
                        right = f"{g['home_abbrev']:<4}   {g['period']} {g['clock']}"
                    elif g["status"] == "final":
                        left  = f"{pfx}{g['away_abbrev']:>4}"
                        mid   = f"{a_sc:>10}  –  {h_sc:<10}"
                        right = f"{g['home_abbrev']:<4}   FINAL"
                    else:
                        left  = f"{pfx}{g['away_abbrev']:>4}"
                        mid   = f"{'vs':^24}"
                        right = f"{g['home_abbrev']:<4}   {g['detail']}"

                    if sel:
                        self._add(y, 0, left,  row_attr)
                        self._add(y, len(left), mid,  row_attr)
                        self._add(y, len(left) + len(mid), right, row_attr)
                    else:
                        # Apply team colours to abbreviations/scores
                        sport = self.current_sport
                        away_abbrev = g["away_abbrev"]
                        home_abbrev = g["home_abbrev"]
                        away_tc = cp_team(sport, away_abbrev)
                        home_tc = cp_team(sport, home_abbrev)
                        if g["status"] in ("live", "final"):
                            self._add(y, 0, pfx, curses.A_NORMAL)
                            self._add(y, len(pfx), f"{away_abbrev:>4}", away_tc)
                            self._add(y, len(left), mid, curses.A_NORMAL)
                            right_start = len(left) + len(mid)
                            self._add(y, right_start, f"{home_abbrev:<4}", home_tc)
                            self._add(y, right_start + 4, right[4:], curses.A_NORMAL)
                        else:
                            self._add(y, 0, pfx, curses.A_NORMAL)
                            self._add(y, len(pfx), f"{away_abbrev:>4}", away_tc)
                            self._add(y, len(left), mid, curses.A_NORMAL)
                            right_start = len(left) + len(mid)
                            self._add(y, right_start, f"{home_abbrev:<4}", home_tc)
                            self._add(y, right_start + 4, right[4:], curses.A_NORMAL)

                    if g["status"] == "live" and not sel:
                        self._add(y, 1, "●", cp("live_badge", bold=True))
                    y += 1
                row_abs += 1
                flat_i  += 1
            row_abs += 1

    # ── Screen: Ladder ────────────────────────────────────────────────────────

    def _ladder(self) -> None:
        h, w = self.scr.getmaxyx()
        sport        = self.current_sport
        sport_label  = sport.upper()
        ladder_cols  = SPORT_LADDER_COLS.get(sport, NBA_LADDER_COLS)

        self._bar(0, f"{sport_label}  ·  Standings", cp("header", bold=True))
        back_hint = "  L / q  Back  "
        self._add(0, w - len(back_hint) - 1, back_hint, cp("header"))

        with self._lock:
            groups = list(self.ladder_data)

        if not groups:
            if self.loading:
                self._add_center(h // 2, "⟳  Loading standings...", curses.A_DIM)
            else:
                self._add_center(h // 2, "No standings data available", curses.A_DIM)
            return

        # Count total renderable rows for scroll clamping
        total_rows = sum(2 + len(g["entries"]) + 1 for g in groups)
        self.ladder_scroll = max(0, min(self.ladder_scroll,
                                        max(0, total_rows - (h - 3))))

        y = 1; row_abs = 0
        for group in groups:
            if y >= h - 2:
                break
            # Group header
            if row_abs >= self.ladder_scroll:
                self._add(y, 0, f"  ── {group['name'].upper()} ──",
                          cp("section", bold=True))
                y += 1
            row_abs += 1

            # Column header
            if row_abs >= self.ladder_scroll and y < h - 2:
                self._fill_row(y, cp("col_hdr"))
                col_x = 1
                for cname, cw, align in ladder_cols:
                    s = cname.rjust(cw) if align == "right" else (
                        cname.ljust(cw) if align == "left" else cname.center(cw))
                    self._add(y, col_x, s, cp("col_hdr", bold=True))
                    col_x += cw + 1
                y += 1
            row_abs += 1

            # Team rows
            for entry in group["entries"]:
                if y >= h - 2:
                    break
                if row_abs >= self.ladder_scroll:
                    self._render_ladder_row(y, entry, sport, ladder_cols)
                    y += 1
                row_abs += 1

            # Gap between groups
            y += 1
            row_abs += 1

    def _render_ladder_row(self, y: int, e: Dict, sport: str,
                            cols: List[Tuple[str, int, str]]) -> None:
        team_str = f"{e['abbrev']:<4}  {e['name']}"
        diff     = e["diff"]
        diff_s   = f"+{diff}" if diff > 0 else str(diff)
        diff_a   = cp("positive") if diff > 0 else (cp("negative") if diff < 0
                                                     else curses.A_NORMAL)
        pct_s    = f"{e['pct']:.3f}" if e.get("pct") else ".000"
        stk_s    = e.get("stk_str", "-")
        stk_a    = (cp("positive") if e.get("stk_color") == "positive" else
                    cp("negative") if e.get("stk_color") == "negative" else
                    curses.A_NORMAL)
        # Rank highlight: top playoff seeds
        playoff_cut = {"nba": 6, "nhl": 8, "nfl": 7, "afl": 8}.get(sport, 8)
        rank_a = curses.A_BOLD if e["rank"] <= playoff_cut else curses.A_NORMAL
        team_a = curses.A_BOLD

        if sport == "nba":
            cells = [
                (str(e["rank"]).rjust(3),         rank_a),
                (team_str[:22],                   team_a),
                (str(e["wins"]).rjust(3),         curses.A_NORMAL),
                (str(e["losses"]).rjust(3),       curses.A_NORMAL),
                (pct_s[:5].rjust(5),              curses.A_NORMAL),
                (diff_s[:5].rjust(5),             diff_a),
                (stk_s[:4].rjust(4),              stk_a),
                (e.get("last10", "")[:9].center(9), curses.A_NORMAL),
            ]
        elif sport == "nhl":
            cells = [
                (str(e["rank"]).rjust(3),         rank_a),
                (team_str[:22],                   team_a),
                (str(e["wins"]).rjust(3),         curses.A_NORMAL),
                (str(e["losses"]).rjust(3),       curses.A_NORMAL),
                (str(e["otlosses"]).rjust(3),     curses.A_NORMAL),
                (str(e["pts"]).rjust(4),          curses.A_BOLD),
                (diff_s[:5].rjust(5),             diff_a),
                (stk_s[:4].rjust(4),              stk_a),
            ]
        elif sport == "afl":
            pct_afl = e.get("pct_afl", 0)
            pct_str = f"{pct_afl:.1f}" if pct_afl else "0.0"
            form    = (e.get("form", "") or "")[-7:]
            cells = [
                (str(e["rank"]).rjust(3),         rank_a),
                (team_str[:22],                   team_a),
                (str(e["wins"]).rjust(3),         curses.A_NORMAL),
                (str(e["losses"]).rjust(3),       curses.A_NORMAL),
                (str(e["ties"]).rjust(3),         curses.A_NORMAL),
                (str(e["pts"]).rjust(4),          curses.A_BOLD),
                (pct_str[:7].rjust(7),            curses.A_NORMAL),
                (diff_s[:5].rjust(5),             diff_a),
                (form.center(7),                  curses.A_NORMAL),
            ]
        else:  # nfl
            cells = [
                (str(e["rank"]).rjust(3),         rank_a),
                (team_str[:22],                   team_a),
                (str(e["wins"]).rjust(3),         curses.A_NORMAL),
                (str(e["losses"]).rjust(3),       curses.A_NORMAL),
                (str(e["ties"]).rjust(3),         curses.A_NORMAL),
                (pct_s[:5].rjust(5),              curses.A_NORMAL),
                (diff_s[:5].rjust(5),             diff_a),
                (stk_s[:4].rjust(4),              stk_a),
            ]

        col_x = 1
        for (_, cw, _), (val, attr) in zip(cols, cells):
            self._add(y, col_x, val[:cw], attr)
            col_x += cw + 1

    # ── Shared score box helper ───────────────────────────────────────────────

    def _draw_score_box(self, header: Dict, sport: str) -> None:
        """Draw the score box in rows 1–5. Shared by detail/timeline/h2h views."""
        _, w = self.scr.getmaxyx()
        state       = header.get("state", "pre")
        away_abbrev = header.get("away_abbrev", "AWY")
        home_abbrev = header.get("home_abbrev", "HOM")
        away_name   = header.get("away_name", away_abbrev)
        home_name   = header.get("home_name", home_abbrev)

        if sport == "afl":
            ag, ab_v = header.get("away_goals"), header.get("away_behinds")
            hg, hb_v = header.get("home_goals"), header.get("home_behinds")
            away_score = (f"{ag}.{ab_v}.{header['away_score']}"
                          if ag and ab_v else str(header.get("away_score", "0")))
            home_score = (f"{hg}.{hb_v}.{header['home_score']}"
                          if hg and hb_v else str(header.get("home_score", "0")))
        else:
            away_score = str(header.get("away_score", "0"))
            home_score = str(header.get("home_score", "0"))

        if state == "in":
            status_line = f"  ●  {header['period']}   {header['clock']}  "
            status_attr = cp("live_badge", bold=True)
        elif state == "post":
            status_line = "  FULL TIME  "
            status_attr = curses.A_BOLD
        else:
            status_line = f"  {header.get('detail', 'Upcoming')}  "
            status_attr = curses.A_DIM

        max_name  = min(22, max(8, (w - 24) // 2))
        away_disp = away_name[:max_name].upper()
        home_disp = home_name[:max_name].upper()
        mid       = w // 2
        box_w     = min(w - 2, 80)
        bx        = max(0, (w - box_w) // 2)
        ba        = cp("box_border")

        self._add(1, bx, "┌" + "─" * (box_w - 2) + "┐", ba)
        self._add(5, bx, "└" + "─" * (box_w - 2) + "┘", ba)
        for row in (2, 3, 4):
            self._add(row, bx,            "│", ba)
            self._add(row, bx + box_w - 1, "│", ba)

        # Team names
        self._add(2, max(bx + 2, mid - len(away_disp) - 5),
                  away_disp, cp_team(sport, away_abbrev, bold=True))
        self._add_center(2, "vs", curses.A_DIM)
        self._add(2, min(bx + box_w - len(home_disp) - 2, mid + 4),
                  home_disp, cp_team(sport, home_abbrev, bold=True))

        # Scores
        self._add(3, max(bx + 2, mid - len(away_score) - 6),
                  away_score, cp_team(sport, away_abbrev, bold=True) | curses.A_BOLD)
        self._add_center(3, "─", curses.A_DIM)
        self._add(3, min(bx + box_w - len(home_score) - 2, mid + 4),
                  home_score, cp_team(sport, home_abbrev, bold=True) | curses.A_BOLD)

        # Status / clock
        self._add_center(4, status_line, status_attr)
        kayo_hint = " K  Watch on Kayo "
        kayo_x = bx + box_w - len(kayo_hint) - 1
        if kayo_x > mid + 10:
            self._add(4, kayo_x, kayo_hint, cp("accent"))

    # ── Screen: Game Detail ───────────────────────────────────────────────────

    def _game_detail(self) -> None:
        h, w = self.scr.getmaxyx()
        sport      = self.current_sport
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
                self._add_center(h // 2,
                    "No data available — press r to retry", curses.A_DIM)
            return

        state       = header.get("state", "pre")
        away_abbrev = header.get("away_abbrev", "AWY")
        home_abbrev = header.get("home_abbrev", "HOM")
        away_name   = header.get("away_name", away_abbrev)
        home_name   = header.get("home_name", home_abbrev)

        # ── Top header bar (just team nav, no duplicate clock) ────────────
        back_hint = "  q  Back  "
        title     = f"  {away_abbrev}  @  {home_abbrev}  ·  {sport.upper()}"
        self._bar(0, title, cp("header", bold=True))
        self._add(0, w - len(back_hint) - 1, back_hint, cp("header"))

        # ── Score box ─────────────────────────────────────────────────────
        self._draw_score_box(header, sport)

        # ── Team filter tabs ──────────────────────────────────────────────
        tab_labels = ["All Players", away_abbrev, home_abbrev]
        tab_y = 6
        self._add(tab_y, 0, "─" * max(0, w - 1), curses.A_DIM)

        tab_x = 2
        for i, label in enumerate(tab_labels):
            if i == self.team_filter:
                ts = f" {label} "
                self._add(tab_y, tab_x - 1, "│", curses.A_DIM)
                self._add(tab_y, tab_x, ts, cp("accent", bold=True))
                self._add(tab_y, tab_x + len(ts), "│", curses.A_DIM)
                tab_x += len(ts) + 2
            else:
                ts = f" {label} "
                self._add(tab_y, tab_x, ts, curses.A_DIM)
                tab_x += len(ts) + 1
        mode_hints = " S Stats  T Timeline  H Head-to-Head "
        self._add(tab_y, w - len(mode_hints) - 1, mode_hints, curses.A_DIM)

        # ── Apply team filter ─────────────────────────────────────────────
        if self.team_filter == 1:
            visible = [p for p in players if p["team"] == away_abbrev]
        elif self.team_filter == 2:
            visible = [p for p in players if p["team"] == home_abbrev]
        else:
            visible = players

        if visible:
            self.player_scroll = max(0, min(self.player_scroll, len(visible) - 1))
        else:
            self.player_scroll = 0

        # ── Column headers ────────────────────────────────────────────────
        col_hdr_y = tab_y + 1
        self._fill_row(col_hdr_y, cp("col_hdr"))
        col_x = 1; col_positions: List[int] = []
        for cname, cw, align in table_cols:
            s = (cname.rjust(cw) if align == "right" else
                 cname.ljust(cw) if align == "left" else cname.center(cw))
            self._add(col_hdr_y, col_x, s, cp("col_hdr", bold=True))
            col_positions.append(col_x)
            col_x += cw + 1

        # ── Player rows ───────────────────────────────────────────────────
        data_top   = col_hdr_y + 1
        table_rows = max(1, h - data_top - 2)

        # Clamp viewport so player_cursor is always visible
        cursor = self.player_cursor
        if cursor < self.player_scroll:
            self.player_scroll = cursor
        elif cursor >= self.player_scroll + table_rows:
            self.player_scroll = cursor - table_rows + 1
        start = self.player_scroll

        for i, player in enumerate(visible[start: start + table_rows]):
            ry      = data_top + i
            abs_idx = start + i
            rank    = abs_idx + 1
            is_sel  = (abs_idx == cursor)
            dnp     = player.get("did_not_play", False)

            if is_sel:
                self._fill_row(ry, cp("selected"))
                row_attr = cp("selected")
            else:
                row_attr = curses.A_DIM if dnp else curses.A_NORMAL

            chg  = changes.get(player["name"], 0) if not dnp else 0
            if chg > 0:   chg_str, chg_attr = "↑", (cp("selected") if is_sel else cp("positive", bold=True))
            elif chg < 0: chg_str, chg_attr = "↓", (cp("selected") if is_sel else cp("negative", bold=True))
            else:         chg_str, chg_attr = " ", row_attr

            if dnp:
                status = player.get("status_label", "DNP") or "DNP"
                cells  = self._dnp_cells(rank, player, status, row_attr,
                                         len(table_cols))
            else:
                cells  = self._player_cells(rank, player, chg_str, chg_attr,
                                            row_attr, sport)

            for (_, cw, _), (val, vattr), cx in zip(table_cols, cells, col_positions):
                self._add(ry, cx, val[:cw], row_attr if is_sel else vattr)

        # Selection indicator
        total = len(visible)
        indicator = f" ↑↓  Player {cursor + 1} of {total}  ·  Enter → Season Stats "
        self._add(h - 2, 1, indicator, curses.A_DIM)


    # ── Screen: Game Timeline ─────────────────────────────────────────────────

    def _game_timeline(self) -> None:
        h, w = self.scr.getmaxyx()
        sport = self.current_sport

        with self._lock:
            header = dict(self.game_header)
            plays  = list(self.timeline_plays)
            away_abbrev = header.get("away_abbrev", "AWY")
            home_abbrev = header.get("home_abbrev", "HOM")

        if not header:
            if self.loading:
                self._add_center(h // 2, "⟳  Loading game data...", curses.A_DIM)
            else:
                self._add_center(h // 2, "No data available — press r to retry", curses.A_DIM)
            return

        back_hint = "  q  Back  "
        title     = f"  {away_abbrev}  @  {home_abbrev}  ·  {sport.upper()}"
        self._bar(0, title, cp("header", bold=True))
        self._add(0, w - len(back_hint) - 1, back_hint, cp("header"))

        self._draw_score_box(header, sport)

        tab_y = 6
        self._add(tab_y, 0, "─" * max(0, w - 1), curses.A_DIM)
        self._add(tab_y, 2, " S Stats ", curses.A_DIM)
        self._add(tab_y, 12, "[ Timeline ]", cp("accent", bold=True))
        self._add(tab_y, 26, " H Head-to-Head ", curses.A_DIM)

        hdr_y = tab_y + 1
        self._fill_row(hdr_y, cp("col_hdr"))
        self._add(hdr_y, 1, "PERIOD", cp("col_hdr", bold=True))
        self._add(hdr_y, 9, "CLOCK", cp("col_hdr", bold=True))
        self._add(hdr_y, 16, "SCORE", cp("col_hdr", bold=True))
        self._add(hdr_y, 25, "PLAY", cp("col_hdr", bold=True))

        data_top  = hdr_y + 1
        row_count = max(1, h - data_top - 2)
        start     = self.timeline_scroll

        if not plays:
            self._add_center(data_top + 2, "No scoring plays yet", curses.A_DIM)
            return

        for i, play in enumerate(plays[start: start + row_count]):
            ry    = data_top + i
            score_str = f"{play['away_score']}-{play['home_score']}"
            period_s  = play["period"][:6].ljust(6)
            clock_s   = play["clock"][:5].ljust(5)
            text_s    = play.get("short_text", play["text"])
            text_s    = text_s[:max(1, w - 26)]
            self._add(ry, 1,  period_s,  curses.A_NORMAL)
            self._add(ry, 9,  clock_s,   curses.A_DIM)
            self._add(ry, 16, score_str, cp("accent", bold=True))
            self._add(ry, 25, text_s,    curses.A_NORMAL)

    # ── Screen: Game H2H ──────────────────────────────────────────────────────

    def _game_h2h(self) -> None:
        h, w = self.scr.getmaxyx()
        sport = self.current_sport

        with self._lock:
            header   = dict(self.game_header)
            h2h      = dict(self.h2h_data)

        if not header:
            if self.loading:
                self._add_center(h // 2, "⟳  Loading game data...", curses.A_DIM)
            else:
                self._add_center(h // 2, "No data available — press r to retry", curses.A_DIM)
            return

        away_abbrev = header.get("away_abbrev", "AWY")
        home_abbrev = header.get("home_abbrev", "HOM")

        back_hint = "  q  Back  "
        title     = f"  {away_abbrev}  @  {home_abbrev}  ·  {sport.upper()}"
        self._bar(0, title, cp("header", bold=True))
        self._add(0, w - len(back_hint) - 1, back_hint, cp("header"))

        self._draw_score_box(header, sport)

        tab_y = 6
        self._add(tab_y, 0, "─" * max(0, w - 1), curses.A_DIM)
        self._add(tab_y, 2, " S Stats ", curses.A_DIM)
        self._add(tab_y, 12, " T Timeline ", curses.A_DIM)
        self._add(tab_y, 26, "[ Head-to-Head ]", cp("accent", bold=True))

        if not h2h:
            self._add_center(h // 2, "No head-to-head data available", curses.A_DIM)
            return

        summary_y = tab_y + 1
        series_label = h2h.get("series_label", "Series")
        summary_text = f"  {series_label}:  {h2h.get('summary', '')}"
        self._add(summary_y, 1, summary_text[:w-2], cp("accent", bold=True))
        if h2h.get("description"):
            self._add(summary_y + 1, 1, f"  {h2h['description']}"[:w-2], curses.A_DIM)

        hdr_y = summary_y + 2
        self._fill_row(hdr_y, cp("col_hdr"))
        self._add(hdr_y, 1,  "DATE",   cp("col_hdr", bold=True))
        self._add(hdr_y, 10, "AWAY",   cp("col_hdr", bold=True))
        self._add(hdr_y, 20, "SCORE",  cp("col_hdr", bold=True))
        self._add(hdr_y, 30, "HOME",   cp("col_hdr", bold=True))
        self._add(hdr_y, 40, "RESULT", cp("col_hdr", bold=True))

        data_top  = hdr_y + 1
        row_count = max(1, h - data_top - 2)
        games     = h2h.get("games", [])
        start     = self.h2h_scroll

        if not games:
            self._add_center(data_top + 1, "No previous meetings found", curses.A_DIM)
            return

        for i, gm in enumerate(games[start: start + row_count]):
            ry = data_top + i
            away_win = gm.get("away_winner", False)
            home_win = gm.get("home_winner", False)
            away_attr = cp_team(sport, gm["away_abbrev"], bold=away_win)
            home_attr = cp_team(sport, gm["home_abbrev"], bold=home_win)
            result_s  = (f"{gm['away_abbrev']} win" if away_win
                         else f"{gm['home_abbrev']} win" if home_win
                         else "Draw")
            result_a  = (cp("positive") if away_win or home_win else curses.A_DIM)
            self._add(ry, 1,  gm["date"][:8],         curses.A_DIM)
            self._add(ry, 10, gm["away_abbrev"][:8],  away_attr)
            self._add(ry, 20, f"{gm['away_score']}-{gm['home_score']}", cp("accent"))
            self._add(ry, 30, gm["home_abbrev"][:8],  home_attr)
            self._add(ry, 40, result_s[:15],           result_a)

    # ── Screen: Player Season Stats ───────────────────────────────────────────

    def _player_season(self) -> None:
        h, w = self.scr.getmaxyx()
        sport = self.current_sport

        with self._lock:
            stats   = self.season_stats
            loading = self.season_stats_loading
            name    = self.current_player_name

        title = f"  Season Stats  ·  {name}"
        self._bar(0, title, cp("header", bold=True))
        back_hint = "  q  Back  "
        self._add(0, w - len(back_hint) - 1, back_hint, cp("header"))

        if loading or (stats is None and loading):
            self._add_center(h // 2, "⟳  Loading season stats...", curses.A_DIM)
            return

        if not stats:
            self._add_center(h // 2, "No season stats available for this player", curses.A_DIM)
            return

        self._add(2, 2, stats.get("display_name", "Season Averages"),
                  cp("accent", bold=True))

        labels = stats.get("labels", [])
        values = stats.get("values", [])

        col_w    = max(30, (w - 4) // 2)
        pairs    = list(zip(labels, values))
        mid_point = (len(pairs) + 1) // 2

        for i, (label, val) in enumerate(pairs):
            col   = 0 if i < mid_point else 1
            row_i = i if i < mid_point else i - mid_point
            ry    = 4 + row_i
            x     = 2 + col * col_w
            if ry >= h - 2:
                break
            self._add(ry, x,       f"{label:<8}", cp("col_hdr"))
            self._add(ry, x + 9,   str(val)[:col_w - 12], curses.A_BOLD)

        self._add(h - 2, 1, "  q  Back to game", curses.A_DIM)

    # ── Cell builders ─────────────────────────────────────────────────────────

    def _dnp_cells(self, rank: int, player: Dict, status: str,
                   row_attr: int, total_cols: int) -> list:
        name_w = 20 if self.current_sport == "afl" else 18 if self.current_sport == "nfl" else 22
        cells = [
            (str(rank).rjust(3),                     row_attr),
            (" ",                                     row_attr),
            (player["name"][:name_w].ljust(name_w),  row_attr),
            (player["team"][:4].ljust(4),             row_attr),
            (player["pos"][:3].center(3),             row_attr),
            (status.center(4),                        cp("negative")),
        ]
        while len(cells) < total_cols:
            cells.append(("", row_attr))
        return cells

    def _player_cells(self, rank, player, chg_str, chg_attr, row_attr, sport) -> list:
        if sport == "nhl": return self._nhl_cells(rank, player, chg_str, chg_attr, row_attr)
        if sport == "afl": return self._afl_cells(rank, player, chg_str, chg_attr, row_attr)
        if sport == "nfl": return self._nfl_cells(rank, player, chg_str, chg_attr, row_attr)
        return self._nba_cells(rank, player, chg_str, chg_attr, row_attr)

    def _pm_attrs(self, pm_raw, row_attr):
        try:
            n = int(str(pm_raw).replace("+", ""))
            if n > 0:   return f"+{n}", cp("positive")
            if n < 0:   return str(n), cp("negative")
            return "0", row_attr
        except (ValueError, TypeError):
            return str(pm_raw), row_attr

    def _nba_cells(self, rank, p, chg_str, chg_attr, row_attr):
        pm_s, pm_a = self._pm_attrs(p["pm"], row_attr)
        pts_a = (row_attr | curses.A_BOLD) if p["pts"] >= 20 else row_attr
        return [
            (str(rank).rjust(3),              row_attr),
            (chg_str,                          chg_attr),
            (p["name"][:22].ljust(22),         row_attr | curses.A_BOLD),
            (p["team"][:4].ljust(4),           row_attr),
            (p["pos"][:3].center(3),           row_attr),
            (p["min"][:5].rjust(5),            row_attr),
            (str(p["pts"]).rjust(4),           pts_a),
            (str(p["reb"]).rjust(4),           row_attr),
            (str(p["ast"]).rjust(4),           row_attr),
            (str(p["stl"]).rjust(3),           row_attr),
            (str(p["blk"]).rjust(3),           row_attr),
            (p["fg"][:7].center(7),            row_attr),
            (p["fg3"][:7].center(7),           row_attr),
            (p["ft"][:6].center(6),            row_attr),
            (pm_s[:4].rjust(4),                pm_a),
        ]

    def _nhl_cells(self, rank, p, chg_str, chg_attr, row_attr):
        pm_s, pm_a = self._pm_attrs(p["pm"], row_attr)
        pts_a = (row_attr | curses.A_BOLD) if p["pts"] >= 2 else row_attr
        return [
            (str(rank).rjust(3),              row_attr),
            (chg_str,                          chg_attr),
            (p["name"][:22].ljust(22),         row_attr | curses.A_BOLD),
            (p["team"][:4].ljust(4),           row_attr),
            (p["pos"][:3].center(3),           row_attr),
            (p["toi"][:5].rjust(5),            row_attr),
            (str(p["g"]).rjust(3),             pts_a),
            (str(p["a"]).rjust(3),             row_attr),
            (str(p["pts"]).rjust(3),           pts_a),
            (pm_s[:4].rjust(4),                pm_a),
            (str(p["sog"]).rjust(4),           row_attr),
            (str(p["bs"]).rjust(4),            row_attr),
            (str(p["ht"]).rjust(4),            row_attr),
            (str(p["pim"]).rjust(4),           row_attr),
            (str(p["fopct"])[:5].rjust(5),     row_attr),
        ]

    def _afl_cells(self, rank, p, chg_str, chg_attr, row_attr):
        fpts_a = (row_attr | curses.A_BOLD) if p["fpts"] >= 100 else row_attr
        return [
            (str(rank).rjust(3),              row_attr),
            (chg_str,                          chg_attr),
            (p["name"][:20].ljust(20),         row_attr | curses.A_BOLD),
            (p["team"][:4].ljust(4),           row_attr),
            (p["pos"][:3].center(3),           row_attr),
            (str(p["fpts"]).rjust(4),          fpts_a),
            (str(p["d"]).rjust(4),             row_attr),
            (str(p["k"]).rjust(3),             row_attr),
            (str(p["hb"]).rjust(3),            row_attr),
            (str(p["m"]).rjust(3),             row_attr),
            (str(p["t"]).rjust(3),             row_attr),
            (str(p["g"]).rjust(3),             row_attr),
            (str(p["b"]).rjust(3),             row_attr),
            (str(p["ho"]).rjust(3),            row_attr),
            (str(p["i50"]).rjust(4),           row_attr),
            (str(p["r50"]).rjust(4),           row_attr),
            (str(p["ff"]).rjust(3),            row_attr),
            (str(p["fa"]).rjust(3),            row_attr),
        ]

    def _nfl_cells(self, rank, p, chg_str, chg_attr, row_attr):
        is_star = (p["pyds"] >= 200 or p["ryds"] >= 100
                   or p["wyds"] >= 100 or p["tkl"] >= 10)
        star_a  = (row_attr | curses.A_BOLD) if is_star else row_attr
        total_td = p["ptd"] + p["rtd"] + p["wtd"]
        int_shown = p["int_thrown"] if p["pyds"] > 0 else p.get("def_int", 0)
        sacks_s = f"{p['sacks']:g}" if p["sacks"] else "0"
        return [
            (str(rank).rjust(3),              row_attr),
            (chg_str,                          chg_attr),
            (p["name"][:18].ljust(18),         row_attr | curses.A_BOLD),
            (p["team"][:4].ljust(4),           row_attr),
            (p["pos"][:3].center(3),           row_attr),
            (p["catt"][:7].center(7),          star_a),
            (str(p["pyds"]).rjust(4),          star_a),
            (str(total_td).rjust(3),           star_a),
            (str(int_shown).rjust(3),          row_attr),
            (str(p["car"]).rjust(3),           row_attr),
            (str(p["ryds"]).rjust(4),          star_a),
            (str(p["rec"]).rjust(3),           row_attr),
            (str(p["wyds"]).rjust(4),          star_a),
            (str(p["tkl"]).rjust(3),           row_attr),
            (sacks_s[:3].rjust(3),             row_attr),
        ]


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main(stdscr: "curses._CursesWindow") -> None:
    app = App(stdscr)
    app.run()


def cli_entry() -> None:
    """Console-script entry point — called when user types `sportpulse`."""
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    cli_entry()
