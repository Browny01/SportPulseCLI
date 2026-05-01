import Foundation

// ─────────────────────────────────────────────────────────────────────────────
// MARK: - Sport
// ─────────────────────────────────────────────────────────────────────────────

enum Sport: String, CaseIterable, Identifiable {
    case nba = "nba"
    case nhl = "nhl"
    case afl = "afl"
    case nfl = "nfl"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .nba: return "NBA"
        case .nhl: return "NHL"
        case .afl: return "AFL"
        case .nfl: return "NFL"
        }
    }

    var emoji: String {
        switch self {
        case .nba: return "🏀"
        case .nhl: return "🏒"
        case .afl: return "🏉"
        case .nfl: return "🏈"
        }
    }

    var espnPath: String {
        switch self {
        case .nba: return "basketball/nba"
        case .nhl: return "hockey/nhl"
        case .afl: return "australian-football/afl"
        case .nfl: return "football/nfl"
        }
    }

    var kayoURL: URL {
        let urls: [Sport: String] = [
            .nba: "https://kayosports.com.au/sport/nba",
            .nhl: "https://kayosports.com.au/sport/nhl",
            .afl: "https://kayosports.com.au/sport/afl",
            .nfl: "https://kayosports.com.au/sport/nfl",
        ]
        return URL(string: urls[self]!)!
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// MARK: - GameStatus
// ─────────────────────────────────────────────────────────────────────────────

enum GameStatus: String, Hashable {
    case pre  = "pre"
    case live = "in"
    case post = "post"
}

// ─────────────────────────────────────────────────────────────────────────────
// MARK: - GameSummary  (scoreboard row)
// ─────────────────────────────────────────────────────────────────────────────

struct GameSummary: Identifiable, Hashable, Sendable {
    let id: String
    let sport: Sport

    let awayAbbrev: String
    let homeAbbrev: String
    let awayName: String
    let homeName: String
    let awayLogo: URL?
    let homeLogo: URL?

    let awayScore: String
    let homeScore: String

    let status: GameStatus
    let statusDetail: String    // e.g. "Q4 2:14", "7:30 PM", "Final"
    let period: String
    let clock: String
    let isLive: Bool
}

// ─────────────────────────────────────────────────────────────────────────────
// MARK: - Player (boxscore row)
// ─────────────────────────────────────────────────────────────────────────────

struct Player: Identifiable, Sendable {
    let id: String
    let name: String
    let teamAbbrev: String
    let position: String
    let didNotPlay: Bool
    let statusLabel: String     // "INJ", "REST", "DNP", "" etc.

    let statLabels: [String]    // column headers for this sport
    let statValues: [String]    // corresponding values
    let sortKey: Double         // primary sort stat (e.g. PTS for NBA, Disposals for AFL)
    let fantasyPoints: Double   // AFL Fantasy pts (0 for other sports)
}

// ─────────────────────────────────────────────────────────────────────────────
// MARK: - GameDetail (game summary screen)
// ─────────────────────────────────────────────────────────────────────────────

struct GameDetail: Sendable {
    let gameId: String
    let sport: Sport

    let awayAbbrev: String
    let homeAbbrev: String
    let awayName: String
    let homeName: String
    let awayScore: String
    let homeScore: String
    let status: GameStatus
    let statusDetail: String
    let period: String
    let clock: String

    let players: [Player]

    // Timeline entries (most recent first)
    let timeline: [TimelineEntry]
    // H2H games
    let h2hGames: [H2HGame]
    let h2hLabel: String
}

// ─────────────────────────────────────────────────────────────────────────────
// MARK: - TimelineEntry
// ─────────────────────────────────────────────────────────────────────────────

struct TimelineEntry: Identifiable, Sendable {
    let id = UUID()
    let period: String
    let clock: String
    let text: String
    let typeLabel: String
    let awayScore: String
    let homeScore: String
    let teamId: String
}

// ─────────────────────────────────────────────────────────────────────────────
// MARK: - H2HGame
// ─────────────────────────────────────────────────────────────────────────────

struct H2HGame: Identifiable, Sendable {
    let id = UUID()
    let date: String
    let awayAbbrev: String
    let homeAbbrev: String
    let awayScore: String
    let homeScore: String
    let awayWinner: Bool
    let homeWinner: Bool
}

// ─────────────────────────────────────────────────────────────────────────────
// MARK: - Team Colours
// ─────────────────────────────────────────────────────────────────────────────

import SwiftUI

let teamColors: [String: [String: Color]] = [
    "nba": [
        "ATL": .red,    "BOS": .green,   "BKN": .white,
        "CHA": .cyan,   "CHI": .red,     "CLE": .red,
        "DAL": .blue,   "DEN": .yellow,  "DET": .red,
        "GSW": .yellow, "HOU": .red,     "IND": .yellow,
        "LAC": .red,    "LAL": Color(red: 0.55, green: 0.18, blue: 0.60),
        "MEM": .blue,   "MIA": .red,     "MIL": .green,
        "MIN": .green,  "NOP": .yellow,  "NYK": .blue,
        "OKC": .blue,   "ORL": .blue,    "PHI": .blue,
        "PHX": Color(red: 0.55, green: 0.18, blue: 0.60),
        "POR": .red,    "SAC": Color(red: 0.55, green: 0.18, blue: 0.60),
        "SAS": .white,  "TOR": .red,     "UTA": .yellow,
        "WAS": .red,
    ],
    "nhl": [
        "ANA": .yellow, "ARI": .red,     "BOS": .yellow,
        "BUF": .blue,   "CAR": .red,     "CBJ": .blue,
        "CGY": .red,    "CHI": .red,     "COL": Color(red: 0.55, green: 0.18, blue: 0.60),
        "DAL": .green,  "DET": .red,     "EDM": .orange,
        "FLA": .red,    "LA":  .yellow,  "MIN": .green,
        "MTL": .red,    "NJ":  .red,     "NSH": .yellow,
        "NYI": .blue,   "NYR": .blue,    "OTT": .red,
        "PHI": .yellow, "PIT": .yellow,  "SEA": .cyan,
        "SJS": .cyan,   "STL": .blue,    "TB":  .blue,
        "TOR": .blue,   "UTA": .cyan,    "VAN": .blue,
        "VGK": .yellow, "WSH": .red,     "WPG": .blue,
    ],
    "afl": [
        "ADE": .red,    "BL":   .blue,   "CARL": .blue,
        "COLL": .white, "ESS":  .red,    "FRE":  Color(red: 0.55, green: 0.18, blue: 0.60),
        "GC":  .yellow, "GEE":  .blue,   "GWS":  .orange,
        "HAW": .orange, "MELB": .red,    "NM":   .blue,
        "PA":  .cyan,   "RICH": .yellow, "STK":  .red,
        "SYD": .red,    "WB":   .red,    "WCE":  .blue,
    ],
    "nfl": [
        "ARI": .red,    "ATL": .red,     "BAL": Color(red: 0.55, green: 0.18, blue: 0.60),
        "BUF": .blue,   "CAR": .cyan,    "CHI": .blue,
        "CIN": .orange, "CLE": .orange,  "DAL": .blue,
        "DEN": .orange, "DET": .blue,    "GB":  .green,
        "HOU": .blue,   "IND": .blue,    "JAX": .cyan,
        "KC":  .red,    "LAC": .blue,    "LAR": .blue,
        "LV":  .gray,   "MIA": .cyan,    "MIN": Color(red: 0.55, green: 0.18, blue: 0.60),
        "NE":  .blue,   "NO":  .yellow,  "NYG": .blue,
        "NYJ": .green,  "PHI": .green,   "PIT": .yellow,
        "SEA": .green,  "SF":  .red,     "TB":  .red,
        "TEN": .blue,   "WAS": .red,
    ],
]

func teamColor(sport: Sport, abbrev: String) -> Color {
    teamColors[sport.rawValue]?[abbrev] ?? .primary
}
