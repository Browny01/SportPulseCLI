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
import requests
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

REFRESH_INTERVAL = 30

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
    " ____                   _   ____        _           ",
    "/ ___| _ __   ___  _ __| |_|  _ \\ _   _| |___  ___ ",
    "\\___ \\| '_ \\ / _ \\| '__| __| |_) | | | | / __|/ _ \\",
    " ___) | |_) | (_) | |  | |_|  __/| |_| | \\__ \\  __/",
    "|____/| .__/ \\___/|_|   \\__|_|    \\__,_|_|___/\\___|",
    "      |_|                                           ",
]

TAGLINE = "Real-time Sports Stats  ·  Powered by ESPN"

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
    ("header",      curses.COLOR_WHITE,  curses.COLOR_BLUE),
    ("selected",    curses.COLOR_BLACK,  curses.COLOR_YELLOW),
    ("live_badge",  curses.COLOR_WHITE,  curses.COLOR_RED),
    ("upcoming_b",  curses.COLOR_BLACK,  curses.COLOR_GREEN),
    ("logo",        curses.COLOR_CYAN,   -1),
    ("col_hdr",     curses.COLOR_BLACK,  curses.COLOR_WHITE),
    ("positive",    curses.COLOR_GREEN,  -1),
    ("negative",    curses.COLOR_RED,    -1),
    ("score_away",  curses.COLOR_CYAN,   -1),
    ("score_home",  curses.COLOR_GREEN,  -1),
    ("status_bar",  curses.COLOR_BLACK,  curses.COLOR_WHITE),
    ("section",     curses.COLOR_YELLOW, curses.COLOR_BLUE),
    ("final_badge", curses.COLOR_WHITE,  curses.COLOR_BLACK),
    ("accent",      curses.COLOR_YELLOW, -1),
    ("score_box",   curses.COLOR_WHITE,  curses.COLOR_BLUE),
    ("dim",         curses.COLOR_WHITE,  -1),
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
        self.player_scroll = 0
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
                if   self.state == "game_detail":
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
            with self._lock:
                n = len(self.players)
            self.player_scroll = min(max(0, n - 1), self.player_scroll + 1)
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
                self.team_filter   = 0
                self.state         = "game_detail"
                self._wake.set()

    # ── Background refresh ────────────────────────────────────────────────────

    def _bg_loop(self) -> None:
        while self._running:
            self._fetch()
            self._wake.wait(timeout=REFRESH_INTERVAL)
            self._wake.clear()

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
        elif self.state == "game_detail":  self._game_detail()
        elif self.state == "ladder":       self._ladder()
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
        self._add_center(div_y, "─" * min(50, w - 4), curses.A_DIM)
        list_y = div_y + 2
        list_w = 38
        list_x = max(0, (w - list_w) // 2)
        for i, sport in enumerate(SPORTS):
            y   = list_y + i * 2
            sel = (i == self.sport_idx)
            if sel:
                self._hline(y, list_x - 1, ord(" "), list_w + 2, cp("selected"))
                arrow, row_attr = "►", cp("selected", bold=True)
            else:
                arrow, row_attr = " ", curses.A_NORMAL
            self._add(y, list_x, f" {arrow} {sport['label']}", row_attr)
        self._add_center(h - 3, "  ↑↓ Navigate   ↵ Select   q Quit  ", curses.A_DIM)

    # ── Screen: Game List ─────────────────────────────────────────────────────

    def _game_list(self) -> None:
        h, w = self.scr.getmaxyx()
        sport_label  = self.current_sport.upper()
        round_label  = self._round_label()
        nav_hint     = " ← P    F → "
        title        = f"{sport_label}  ·  {round_label}"
        self._bar(0, title, cp("header", bold=True))
        self._add(0, w - len(nav_hint) - 1, nav_hint, cp("header"))

        with self._lock:
            games = list(self.games)

        flat     = _flatten_games(games)
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
                    f"No {sport_label} games  ·  {round_label}", curses.A_DIM)
                self._add_center(h // 2,
                    "Press P / F to navigate rounds,  r to refresh", curses.A_DIM)
                self._add_center(h // 2 + 1, "L  →  View standings ladder", curses.A_DIM)
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
                self._bar(y, label, cp(badge_key, bold=True))
                y += 1
            row_abs += 1
            for g in glist:
                if y >= h - 2:
                    break
                if row_abs >= self.game_scroll:
                    sel      = (flat_i == self.game_idx)
                    row_attr = cp("selected", bold=True) if sel else curses.A_NORMAL
                    if sel:
                        self._fill_row(y, cp("selected"))
                    pfx  = " ► " if sel else "   "
                    a_sc = g["away_score"]
                    h_sc = g["home_score"]
                    if g["status"] == "live":
                        line = (f"{pfx}{g['away_abbrev']:>4}  "
                                f"{a_sc:>12} - {h_sc:<12}"
                                f"  {g['home_abbrev']:<4}   {g['period']} {g['clock']}")
                    elif g["status"] == "final":
                        line = (f"{pfx}{g['away_abbrev']:>4}  "
                                f"{a_sc:>12} - {h_sc:<12}"
                                f"  {g['home_abbrev']:<4}   FINAL")
                    else:
                        line = (f"{pfx}{g['away_abbrev']:>4}  vs  {g['home_abbrev']:<4}"
                                f"   {g['detail']}")
                    self._add(y, 0, line, row_attr)
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
                self._bar(y, f"  {group['name'].upper()}", cp("section", bold=True))
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

        # AFL: show G.B.Total if available
        if sport == "afl":
            ag, ab_val = header.get("away_goals"), header.get("away_behinds")
            hg, hb_val = header.get("home_goals"), header.get("home_behinds")
            away_score = (f"{ag}.{ab_val}.{header['away_score']}"
                          if ag and ab_val else str(header.get("away_score", "0")))
            home_score = (f"{hg}.{hb_val}.{header['home_score']}"
                          if hg and hb_val else str(header.get("home_score", "0")))
        else:
            away_score = str(header.get("away_score", "0"))
            home_score = str(header.get("home_score", "0"))

        # Team names (row 2)
        self._add(2, max(2, mid - len(away_name[:max_name]) - 4),
                  away_name[:max_name], box_attr | curses.A_BOLD)
        self._add(2, mid - 1, "vs", box_attr | curses.A_BOLD)
        self._add(2, mid + 3, home_name[:max_name], box_attr | curses.A_BOLD)

        # Scores (row 4)
        self._add(4, max(2, mid - len(away_score) - 4), away_score,
                  cp("score_away", bold=True))
        self._add(4, mid - 1, "●", box_attr)
        self._add(4, mid + 3, home_score, cp("score_home", bold=True))

        # Clock (row 6)
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
                ts, ta = f"[ {label} ]", cp("selected", bold=True)
            else:
                ts, ta = f"  {label}  ", curses.A_DIM
            self._add(div_y, tab_x, ts, ta)
            tab_x += len(ts) + 1
        self._add(div_y, w - 17, "⇥ Tab to switch", curses.A_DIM)

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
        col_hdr_y = div_y + 1
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
        start      = self.player_scroll

        for i, player in enumerate(visible[start: start + table_rows]):
            ry   = data_top + i
            rank = start + i + 1
            dnp  = player.get("did_not_play", False)
            row_attr = curses.A_DIM if dnp else curses.A_NORMAL
            chg  = changes.get(player["name"], 0) if not dnp else 0
            if chg > 0:   chg_str, chg_attr = "↑", cp("positive", bold=True)
            elif chg < 0: chg_str, chg_attr = "↓", cp("negative", bold=True)
            else:         chg_str, chg_attr = " ", row_attr

            if dnp:
                status = player.get("status_label", "DNP") or "DNP"
                cells  = self._dnp_cells(rank, player, status, row_attr,
                                         len(table_cols))
            else:
                cells  = self._player_cells(rank, player, chg_str, chg_attr,
                                            row_attr, sport)

            for (_, cw, _), (val, vattr), cx in zip(table_cols, cells, col_positions):
                self._add(ry, cx, val[:cw], vattr)

        # Scroll indicator
        total = len(visible)
        if total > table_rows:
            shown_end = min(start + table_rows, total)
            pct = int(100 * start / max(1, total - table_rows))
            self._add(h - 2, 1,
                f" ↑↓ Scroll  rows {start+1}–{shown_end} of {total}  ({pct}%) ",
                curses.A_DIM)

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


if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
