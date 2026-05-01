# SportPulse 🏀🏒🏈🏉

> Real-time sports scores and live player stats — right in your terminal.

```
 ____                   _   ____        _
/ ___| _ __   ___  _ __| |_|  _ \ _   _| |___  ___
\___ \| '_ \ / _ \| '__| __| |_) | | | | / __|/ _ \
 ___) | |_) | (_) | |  | |_|  __/| |_| | \__ \  __/
|____/| .__/ \___/|_|   \__|_|    \__,_|_|___/\___|
      |_|
        Real-time Sports Stats  ·  Powered by ESPN
```

SportPulse is a Python terminal UI (TUI) that shows live game scores, player stats, league standings, and supports round-by-round navigation — all in the style of official sports websites but entirely in your CLI.

---

## Sports Supported

| Sport | Status | Stats |
|-------|--------|-------|
| 🏀 NBA | ✅ Live | PTS, REB, AST, STL, BLK, FG, 3PT, FT, +/- |
| 🏒 NHL | ✅ Live | G, A, PTS, +/-, TOI, SOG, BS, HITS, PIM, FO% |
| 🏉 AFL | ✅ Live | Fantasy Points, Disposals, Kicks, Handballs, Marks, Tackles, Goals, Behinds, Hit-Outs, I50, R50 |
| 🏈 NFL | ✅ Live | C/ATT, Pass YDS, Rush YDS, Rec YDS, TD, INT, Tackles, Sacks |

---

## Features

- **Live scores** — auto-refreshes every 12 seconds during live games
- **Player stats table** — sorted by performance, updates live (rank-change ↑↓ arrows)
- **Player cursor** — Up/Down moves a selection cursor; the list stays fixed, only your highlight moves
- **Season stats** — press Enter on any player to see their full-season averages
- **All players shown** — including DNP, injured, and inactive players with status labels (`INJ`, `REST`, `SUSP`, `ILL`, `DNP`)
- **Team filter tabs** — TAB cycles between All Players / Away Team / Home Team
- **Round navigation** — browse previous and future rounds/weeks/days
- **League ladder/standings** — live standings with streak, win%, points, and form
- **Game timeline** — chronological scoring plays (T key)
- **Head-to-head history** — season series / recent meetings (H key)
- **Team colour branding** — each team rendered in their brand colour
- **Kayo integration** — K opens the Kayo Sports livestream page in your browser
- **AFL score format** — displayed as `Goals.Behinds.Total` (e.g. `12.11.83`)
- **AFL Fantasy Points** — calculated with the standard AFL Fantasy scoring formula

---

## Requirements

- Python 3.7+
- `requests` library

---

## Installation

```bash
git clone https://github.com/Browny01/SportPulseCLI.git
cd SportPulseCLI
pip install -e .
```

---

## Usage

```bash
sportpulse
```

### Controls

| Key | Action |
|-----|--------|
| `↑` / `↓` | Navigate menus / move player cursor |
| `↵` Enter | Select item / open game / view season stats |
| `q` / `ESC` | Go back / quit |
| `P` | Previous round or day |
| `F` | Next round or day |
| `L` | Toggle league standings/ladder |
| `TAB` | Cycle team filter (All / Away / Home) |
| `T` | Game timeline (scoring plays) |
| `H` | Head-to-head history |
| `S` | Back to player stats |
| `K` | Open Kayo Sports livestream in browser |
| `r` | Force refresh data |

---

## Data Source

All data is sourced from **ESPN's public API** — no API key or account required.

---

## Screenshots

### Sport Selection
```
 ────────────────────────────────────────
  ► NBA                NBA Basketball
    NHL                NHL Hockey
    AFL                AFL Football
    NFL                NFL Football
 ────────────────────────────────────────
```

### Game Scores
```
NBA  ·  Today  (May 1)           ← P    F →
────────────────────────────────────────────
● LIVE
  ● BOS  118 - 105  MIA   Q3  4:22
    LAL  vs  GSW    8:30 PM ET

  FINAL
    DEN  132 - 121  PHX   FINAL
```

### Player Stats (NBA)
```
 RK   PLAYER                TEAM POS  MIN   PTS  REB  AST ...
  1 ↑ Jayson Tatum          BOS   SF  34:12   31    8    4 ...
  2   Bam Adebayo           MIA    C  36:00   24   11    3 ...
  3 ↓ Jaylen Brown          BOS   SG  33:45   22    5    2 ...
```

### League Ladder (AFL)
```
AFL  ·  Standings
─────────────────────────────────────────────────────
  AFL LADDER
  RK  TEAM                   W    L   D   PTS      %   DIFF   FORM
   1  FRE  Fremantle         7    0   0    28  175.2    +312  WWWWWWW
   2  GWS  GWS Giants        6    1   0    24  148.6    +201  LWWWWWW
```

---

## License

MIT
