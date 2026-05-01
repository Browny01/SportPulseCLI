#!/usr/bin/env python3
"""
SportPulse — Live Sports CLI Dashboard
=======================================
Real-time NBA scores and player stats, right in your terminal.

Usage:
    python sportpulse.py

Controls:
    ↑ / ↓      Navigate
    ↵  Enter   Select / Open
    q  ESC     Back / Quit
    r          Force refresh
"""

import curses
import time
import threading
import requests
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

REFRESH_INTERVAL = 30  # seconds between auto-refreshes

ESPN_SCOREBOARD = (
    "http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
)
ESPN_SUMMARY = (
    "http://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
)

SPORTS = [
    {"id": "nba", "label": "NBA",  "available": True},
    {"id": "nhl", "label": "NHL",  "available": False},
    {"id": "afl", "label": "AFL",  "available": False},
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

# Player stats table column definitions: (header, width, alignment)
TABLE_COLS: List[Tuple[str, int, str]] = [
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
# ESPN DATA LAYER
# ─────────────────────────────────────────────────────────────────────────────

def _int(s) -> int:
    try:
        return int(str(s).replace("+", "").strip())
    except (ValueError, TypeError):
        return 0


def _period_str(period: int) -> str:
    if period == 0:    return ""
    if period <= 4:    return f"Q{period}"
    if period == 5:    return "OT"
    return f"OT{period - 4}"


def fetch_scoreboard() -> Optional[Dict]:
    try:
        r = requests.get(ESPN_SCOREBOARD, timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def fetch_game_detail(event_id: str) -> Optional[Dict]:
    try:
        r = requests.get(ESPN_SUMMARY, params={"event": event_id}, timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def parse_games(data: Dict) -> List[Dict]:
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

        games.append({
            "id":          event.get("id", ""),
            "status":      g_status,
            "home_name":   home_t.get("displayName", "Home"),
            "home_abbrev": home_t.get("abbreviation", "HOM"),
            "home_score":  home.get("score", "0"),
            "away_name":   away_t.get("displayName", "Away"),
            "away_abbrev": away_t.get("abbreviation", "AWY"),
            "away_score":  away.get("score", "0"),
            "period":      _period_str(stat.get("period", 0)),
            "clock":       stat.get("displayClock", ""),
            "detail":      stype.get("shortDetail", stype.get("detail", "")),
            "date":        event.get("date", ""),
        })
    return games


def parse_boxscore(data: Dict) -> Tuple[Dict, List[Dict]]:
    if not data:
        return {}, []

    hcomp  = (data.get("header", {}).get("competitions") or [{}])[0]
    hstat  = hcomp.get("status", {})
    htype  = hstat.get("type", {})
    hcomps = hcomp.get("competitors", [])
    home   = next((c for c in hcomps if c.get("homeAway") == "home"), {})
    away   = next((c for c in hcomps if c.get("homeAway") == "away"), {})

    game_header = {
        "home_name":   home.get("team", {}).get("displayName", "Home"),
        "home_abbrev": home.get("team", {}).get("abbreviation", "HOM"),
        "home_score":  home.get("score", "0"),
        "away_name":   away.get("team", {}).get("displayName", "Away"),
        "away_abbrev": away.get("team", {}).get("abbreviation", "AWY"),
        "away_score":  away.get("score", "0"),
        "period":      _period_str(hstat.get("period", 0)),
        "clock":       hstat.get("displayClock", ""),
        "detail":      htype.get("shortDetail", htype.get("detail", "")),
        "state":       htype.get("state", "pre"),
    }

    players: List[Dict] = []
    for team_block in data.get("boxscore", {}).get("players", []):
        abbrev = team_block.get("team", {}).get("abbreviation", "")
        for stats_block in team_block.get("statistics", []):
            names = [n.upper() for n in stats_block.get("names", [])]
            for ab in stats_block.get("athletes", []):
                if not ab.get("active", True):
                    continue
                raw = ab.get("stats", [])
                if not raw:
                    continue
                sm  = dict(zip(names, raw))
                ath = ab.get("athlete", {})
                players.append({
                    "name":    ath.get("displayName", "Unknown"),
                    "pos":     ath.get("position", {}).get("abbreviation", ""),
                    "team":    abbrev,
                    "starter": ab.get("starter", False),
                    "min":     sm.get("MIN", "0"),
                    "pts":     _int(sm.get("PTS", "0")),
                    "reb":     _int(sm.get("REB", "0")),
                    "ast":     _int(sm.get("AST", "0")),
                    "stl":     _int(sm.get("STL", "0")),
                    "blk":     _int(sm.get("BLK", "0")),
                    "to":      _int(sm.get("TO",  "0")),
                    "pf":      _int(sm.get("PF",  "0")),
                    "fg":      sm.get("FG",  "0-0"),
                    "fg3":     sm.get("3PT", "0-0"),
                    "ft":      sm.get("FT",  "0-0"),
                    "pm":      sm.get("+/-", "0"),
                })

    players.sort(key=lambda p: (p["pts"], p["ast"], p["reb"]), reverse=True)
    return game_header, players


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

        # Navigation indices
        self.sport_idx     = 0
        self.game_idx      = 0
        self.game_scroll   = 0   # top row of visible game list window
        self.player_scroll = 0

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

        # Stale-fetch guard — captures (state, game_id) at fetch-start so we
        # never apply results that belong to a different screen/game.
        self._fetch_token: Tuple[str, Optional[str]] = ("", None)
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
                self.state = "game_list"
                self.game_idx  = 0
                self.game_scroll = 0
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
                self.state = "game_detail"
                self._wake.set()

    # ── Background refresh ────────────────────────────────────────────────────

    def _bg_loop(self) -> None:
        while self._running:
            self._fetch()
            self._wake.wait(timeout=REFRESH_INTERVAL)
            self._wake.clear()

    def _fetch(self) -> None:
        # Snapshot the current intent so stale results are discarded
        token = (self.state, self.current_game_id)
        self._fetch_token = token
        self.loading = True
        try:
            state = token[0]
            if state == "game_list":
                data = fetch_scoreboard()
                with self._lock:
                    if self._fetch_token != token:
                        return  # navigated away while fetching
                    if data is not None:
                        self.games        = parse_games(data)
                        self.last_refresh = time.time()
                        self.fetch_error  = None
                    else:
                        self.fetch_error = "Network error — press r to retry"

            elif state == "game_detail" and token[1]:
                data = fetch_game_detail(token[1])
                if data is not None:
                    header, players = parse_boxscore(data)
                    new_ranks = {p["name"]: i for i, p in enumerate(players)}
                    changes: Dict[str, int] = {}
                    with self._lock:
                        prev = dict(self._prev_ranks)
                    for name, nr in new_ranks.items():
                        if name in prev and prev[name] != nr:
                            changes[name] = prev[name] - nr  # +ve = moved up
                    with self._lock:
                        if self._fetch_token != token:
                            return  # user navigated elsewhere mid-fetch
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
        right = " ↑↓ Navigate  ↵ Select  q Back  r Refresh "
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

        # Logo
        for i, line in enumerate(LOGO):
            self._add(sy + i, lx, line, cp("logo", bold=True))

        # Tagline
        ty = sy + len(LOGO) + 1
        self._add_center(ty, TAGLINE, curses.A_DIM)

        # Divider
        div_y = ty + 2
        div   = "─" * min(50, w - 4)
        self._add_center(div_y, div, curses.A_DIM)

        # Sport list
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

            if sport["available"]:
                self._add(y, list_x, f" {arrow} {sport['label']}", row_attr)
            else:
                label = f" {arrow} {sport['label']}  · Coming Soon"
                if sel:
                    self._add(y, list_x, label, cp("selected"))
                else:
                    self._add(y, list_x, label, curses.A_DIM)

        # Hint at bottom
        hint = "  ↑↓ Navigate   ↵ Select   q Quit  "
        self._add_center(h - 3, hint, curses.A_DIM)

    # ── Screen: Game List ─────────────────────────────────────────────────────

    def _game_list(self) -> None:
        h, w = self.scr.getmaxyx()

        self._bar(0, "NBA  ·  Today's Games", cp("header", bold=True))

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
                self._add_center(h // 2 - 1, "No NBA games scheduled today.", curses.A_DIM)
                self._add_center(h // 2 + 1, "Press  r  to refresh.", curses.A_DIM)
            return

        # Clamp selection, then keep selected row visible (scroll window)
        self.game_idx = max(0, min(self.game_idx, len(flat) - 1))
        visible_rows  = h - 3  # rows between header bar and status bar
        if self.game_idx < self.game_scroll:
            self.game_scroll = self.game_idx
        elif self.game_idx >= self.game_scroll + visible_rows:
            self.game_scroll = self.game_idx - visible_rows + 1

        y       = 1
        flat_i  = 0
        row_abs = 0  # absolute rendered-row counter (for scroll window)

        for glist, label, badge_key in sections:
            if not glist:
                continue

            # Section header (always rendered at its natural position)
            if row_abs >= self.game_scroll and y < h - 2:
                self._bar(y, label, cp(badge_key, bold=True))
                y += 1
            elif row_abs < self.game_scroll:
                pass  # scrolled past; don't advance y
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

                    # Safe score formatting (ESPN can return "" or "--")
                    a_sc = _int(g["away_score"])
                    h_sc = _int(g["home_score"])

                    if g["status"] == "live":
                        line = (
                            f"{pfx}{g['away_abbrev']:>4}  "
                            f"{a_sc:>3} - {h_sc:<3}"
                            f"  {g['home_abbrev']:<4}   "
                            f"{g['period']} {g['clock']}"
                        )
                    elif g["status"] == "final":
                        line = (
                            f"{pfx}{g['away_abbrev']:>4}  "
                            f"{a_sc:>3} - {h_sc:<3}"
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

            row_abs += 1  # gap row between sections

    # ── Screen: Game Detail ───────────────────────────────────────────────────

    def _game_detail(self) -> None:
        h, w = self.scr.getmaxyx()

        with self._lock:
            header  = dict(self.game_header)
            players = list(self.players)
            changes = dict(self.rank_changes)

        # Clamp scroll in case player list shrank after a refresh
        if players:
            self.player_scroll = max(0, min(self.player_scroll, len(players) - 1))
        else:
            self.player_scroll = 0

        # ── Loading / error state ──────────────────────────────────────────
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

        # Header bar
        title = f"  {header['away_abbrev']} @ {header['home_abbrev']}"
        self._bar(0, title, cp("header", bold=True))
        self._add(0, w - len(state_tag) - 2, state_tag, tag_attr)

        # ── Score box (rows 1–7) ──────────────────────────────────────────
        BOX_H = 7
        box_attr = cp("score_box")

        for row in range(1, BOX_H + 1):
            self._fill_row(row, box_attr)

        mid = w // 2

        away_name = header.get("away_name", header.get("away_abbrev", "")).upper()
        home_name = header.get("home_name", header.get("home_abbrev", "")).upper()
        max_name  = min(26, (w - 8) // 2)
        away_name = away_name[:max_name]
        home_name = home_name[:max_name]

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
        self._add(score_y, max(2, mid - len(away_score) - 7), away_score,
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

        # ── Divider ───────────────────────────────────────────────────────
        div_y = BOX_H + 1
        self._add(div_y, 0, "─" * (w - 1), curses.A_DIM)
        self._add(div_y, 2, " PLAYER STATISTICS ", cp("accent", bold=True))

        # ── Column headers ────────────────────────────────────────────────
        col_hdr_y = div_y + 1
        self._fill_row(col_hdr_y, cp("col_hdr"))

        col_x = 1
        col_positions: List[int] = []
        for cname, cw, align in TABLE_COLS:
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

        for i, player in enumerate(players[start: start + table_rows]):
            ry   = data_top + i
            rank = start + i + 1

            # Alternating row shade
            row_attr = curses.A_NORMAL

            # Rank-change arrow
            chg = changes.get(player["name"], 0)
            if chg > 0:
                chg_str, chg_attr = "↑", cp("positive", bold=True)
            elif chg < 0:
                chg_str, chg_attr = "↓", cp("negative", bold=True)
            else:
                chg_str, chg_attr = " ", row_attr

            # +/- colour
            try:
                pm_n = int(str(player["pm"]).replace("+", ""))
                if pm_n > 0:
                    pm_str, pm_attr = f"+{pm_n}", cp("positive")
                elif pm_n < 0:
                    pm_str, pm_attr = str(pm_n), cp("negative")
                else:
                    pm_str, pm_attr = "0", row_attr
            except (ValueError, TypeError):
                pm_str, pm_attr = str(player["pm"]), row_attr

            # Points get bold treatment for top scorers
            pts_attr = (row_attr | curses.A_BOLD) if player["pts"] >= 20 else row_attr

            cells = [
                (str(rank).rjust(3),                   row_attr),
                (chg_str,                               chg_attr),
                (player["name"][:22].ljust(22),         row_attr | curses.A_BOLD),
                (player["team"][:4].ljust(4),           row_attr),
                (player["pos"][:3].center(3),           row_attr),
                (player["min"][:5].rjust(5),            row_attr),
                (str(player["pts"]).rjust(4),           pts_attr),
                (str(player["reb"]).rjust(4),           row_attr),
                (str(player["ast"]).rjust(4),           row_attr),
                (str(player["stl"]).rjust(3),           row_attr),
                (str(player["blk"]).rjust(3),           row_attr),
                (player["fg"][:7].center(7),            row_attr),
                (player["fg3"][:7].center(7),           row_attr),
                (player["ft"][:6].center(6),            row_attr),
                (pm_str[:4].rjust(4),                   pm_attr),
            ]

            for (_, cw, _), (val, vattr), cx in zip(TABLE_COLS, cells, col_positions):
                self._add(ry, cx, val[:cw], vattr)

        # Scroll indicator
        if players and len(players) > table_rows:
            shown_end = min(start + table_rows, len(players))
            pct = int(100 * start / max(1, len(players) - table_rows))
            scroll_msg = (
                f" ↑↓ Scroll  rows {start + 1}–{shown_end} of {len(players)}"
                f"  ({pct}%) "
            )
            self._add(h - 2, 1, scroll_msg, curses.A_DIM)


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
