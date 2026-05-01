import Foundation

// ─────────────────────────────────────────────────────────────────────────────
// MARK: - ESPN API Service
// ─────────────────────────────────────────────────────────────────────────────

actor ESPNService {

    static let shared = ESPNService()

    private let session: URLSession = {
        let cfg = URLSessionConfiguration.default
        cfg.timeoutIntervalForRequest  = 10
        cfg.timeoutIntervalForResource = 20
        cfg.urlCache = URLCache(memoryCapacity: 4 * 1024 * 1024,
                                diskCapacity:   20 * 1024 * 1024)
        return URLSession(configuration: cfg)
    }()

    // ── Public API ────────────────────────────────────────────────────────────

    func fetchScoreboard(sport: Sport) async throws -> [GameSummary] {
        let url = URL(string: "https://site.api.espn.com/apis/site/v2/sports/\(sport.espnPath)/scoreboard")!
        let data = try await get(url)
        return try parseScoreboard(data, sport: sport)
    }

    func fetchGameDetail(sport: Sport, gameId: String) async throws -> GameDetail {
        let url = URL(string: "https://site.api.espn.com/apis/site/v2/sports/\(sport.espnPath)/summary?event=\(gameId)")!
        let data = try await get(url)
        return try parseGameDetail(data, sport: sport, gameId: gameId)
    }

    // ── HTTP ─────────────────────────────────────────────────────────────────

    private func get(_ url: URL) async throws -> [String: Any] {
        let (data, _) = try await session.data(from: url)
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw URLError(.cannotParseResponse)
        }
        return json
    }

    // ─────────────────────────────────────────────────────────────────────────
    // MARK: - Scoreboard Parsing
    // ─────────────────────────────────────────────────────────────────────────

    private func parseScoreboard(_ json: [String: Any], sport: Sport) throws -> [GameSummary] {
        let events = json["events"] as? [[String: Any]] ?? []
        var games: [GameSummary] = []

        for event in events {
            guard let id = event["id"] as? String else { continue }
            let comps = (event["competitions"] as? [[String: Any]])?.first ?? [:]
            let competitors = comps["competitors"] as? [[String: Any]] ?? []

            let away = competitors.first(where: { ($0["homeAway"] as? String) == "away" }) ?? [:]
            let home = competitors.first(where: { ($0["homeAway"] as? String) == "home" }) ?? [:]

            let awayTeam = away["team"] as? [String: Any] ?? [:]
            let homeTeam = home["team"] as? [String: Any] ?? [:]

            let awayAbbrev = awayTeam["abbreviation"] as? String ?? "AWY"
            let homeAbbrev = homeTeam["abbreviation"] as? String ?? "HOM"
            let awayName   = awayTeam["shortDisplayName"] as? String
                          ?? awayTeam["displayName"] as? String ?? awayAbbrev
            let homeName   = homeTeam["shortDisplayName"] as? String
                          ?? homeTeam["displayName"] as? String ?? homeAbbrev

            let awayLogoStr = (awayTeam["logos"] as? [[String: Any]])?.first?["href"] as? String
                           ?? awayTeam["logo"] as? String
            let homeLogoStr = (homeTeam["logos"] as? [[String: Any]])?.first?["href"] as? String
                           ?? homeTeam["logo"] as? String

            let statusObj   = comps["status"] as? [String: Any] ?? [:]
            let statusType  = statusObj["type"] as? [String: Any] ?? [:]
            let stateStr    = statusType["state"] as? String ?? "pre"
            let status: GameStatus = {
                switch stateStr {
                case "in":   return .live
                case "post": return .post
                default:     return .pre
                }
            }()

            let awayScore = away["score"] as? String ?? (status == .pre ? "—" : "0")
            var homeScore = home["score"] as? String ?? (status == .pre ? "—" : "0")

            // AFL: format scores as G.B.Total
            if sport == .afl && status != .pre {
                let awayLinescores = away["linescores"] as? [[String: Any]] ?? []
                let homeLinescores = home["linescores"] as? [[String: Any]] ?? []
                // ESPN sometimes provides goals/behinds in linescores[0]
                // Fall back to raw score
                _ = awayLinescores; _ = homeLinescores
            }

            let detail      = statusType["detail"] as? String ?? ""
            let shortDetail = statusType["shortDetail"] as? String ?? detail
            let period      = periodString(from: comps, sport: sport, statusType: statusType)
            let clock       = clockString(from: comps)
            let isLive      = status == .live

            // For pre-game, replace ESPN's ET-formatted time with AWST (UTC+8)
            let eventDate   = event["date"] as? String ?? comps["date"] as? String
            let displayTime: String
            if status == .pre, let iso = eventDate {
                displayTime = formatAWST(isoDate: iso)
            } else {
                displayTime = shortDetail
            }

            games.append(GameSummary(
                id:           id,
                sport:        sport,
                awayAbbrev:   awayAbbrev,
                homeAbbrev:   homeAbbrev,
                awayName:     awayName,
                homeName:     homeName,
                awayLogo:     awayLogoStr.flatMap { URL(string: $0) },
                homeLogo:     homeLogoStr.flatMap { URL(string: $0) },
                awayScore:    awayScore,
                homeScore:    homeScore,
                status:       status,
                statusDetail: displayTime,
                period:       period,
                clock:        clock,
                isLive:       isLive
            ))
        }
        return games
    }

    private func periodString(from comps: [String: Any], sport: Sport, statusType: [String: Any]) -> String {
        let period = comps["period"] as? Int ?? 0
        if period == 0 { return "" }
        switch sport {
        case .nba:
            if period <= 4 { return "Q\(period)" }
            return period > 5 ? "OT\(period - 4)" : "OT"
        case .nhl:
            if period <= 3 { return "P\(period)" }
            return period == 4 ? "OT" : "SO"
        case .afl:
            return "Q\(period)"
        case .nfl:
            if period <= 4 { return "Q\(period)" }
            return "OT"
        }
    }

    private func clockString(from comps: [String: Any]) -> String {
        let clock = comps["clock"] as? [String: Any] ?? [:]
        return clock["displayValue"] as? String ?? ""
    }

    /// Parses an ESPN ISO 8601 UTC date string and returns the time in AWST (UTC+8).
    private func formatAWST(isoDate: String) -> String {
        let parser = ISO8601DateFormatter()
        parser.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        var date = parser.date(from: isoDate)
        if date == nil {
            parser.formatOptions = [.withInternetDateTime]
            date = parser.date(from: isoDate)
        }
        guard let date else { return isoDate }

        let fmt = DateFormatter()
        fmt.timeZone = TimeZone(identifier: "Australia/Perth")
        fmt.dateFormat = "h:mm a"
        return fmt.string(from: date)
    }

    // ─────────────────────────────────────────────────────────────────────────
    // MARK: - Game Detail Parsing
    // ─────────────────────────────────────────────────────────────────────────

    private func parseGameDetail(_ json: [String: Any], sport: Sport, gameId: String) throws -> GameDetail {
        let header  = parseHeader(json, sport: sport)
        let players = parseBoxscore(json, sport: sport)
        let timeline = parseTimeline(json, sport: sport)
        let (h2hGames, h2hLabel) = parseH2H(json)

        return GameDetail(
            gameId:       gameId,
            sport:        sport,
            awayAbbrev:   header.awayAbbrev,
            homeAbbrev:   header.homeAbbrev,
            awayName:     header.awayName,
            homeName:     header.homeName,
            awayLogo:     header.awayLogo,
            homeLogo:     header.homeLogo,
            awayScore:    header.awayScore,
            homeScore:    header.homeScore,
            status:       header.status,
            statusDetail: header.statusDetail,
            period:       header.period,
            clock:        header.clock,
            players:      players,
            timeline:     timeline,
            h2hGames:     h2hGames,
            h2hLabel:     h2hLabel
        )
    }

    // ── Header ───────────────────────────────────────────────────────────────

    private struct HeaderInfo {
        var awayAbbrev, homeAbbrev, awayName, homeName: String
        var awayLogo: URL?
        var homeLogo: URL?
        var awayScore, homeScore: String
        var status: GameStatus
        var statusDetail, period, clock: String
    }

    private func parseHeader(_ json: [String: Any], sport: Sport) -> HeaderInfo {
        let header     = json["header"] as? [String: Any] ?? [:]
        let comps      = (header["competitions"] as? [[String: Any]])?.first ?? [:]
        let competitors = comps["competitors"] as? [[String: Any]] ?? []

        let away = competitors.first(where: { ($0["homeAway"] as? String) == "away" }) ?? [:]
        let home = competitors.first(where: { ($0["homeAway"] as? String) == "home" }) ?? [:]

        let awayTeam = away["team"] as? [String: Any] ?? [:]
        let homeTeam = home["team"] as? [String: Any] ?? [:]

        let statusObj  = comps["status"] as? [String: Any] ?? [:]
        let statusType = statusObj["type"] as? [String: Any] ?? [:]
        let stateStr   = statusType["state"] as? String ?? "pre"
        let status: GameStatus = stateStr == "in" ? .live : stateStr == "post" ? .post : .pre

        let period = comps["period"] as? Int ?? 0
        let clockObj = comps["clock"] as? [String: Any] ?? [:]
        let clockStr = clockObj["displayValue"] as? String ?? ""

        let periodStr: String = {
            if period == 0 { return "" }
            switch sport {
            case .nba: return period <= 4 ? "Q\(period)" : "OT"
            case .nhl: return period <= 3 ? "P\(period)" : (period == 4 ? "OT" : "SO")
            case .afl: return "Q\(period)"
            case .nfl: return period <= 4 ? "Q\(period)" : "OT"
            }
        }()

        let awayLogoStr = (awayTeam["logos"] as? [[String: Any]])?.first?["href"] as? String
                       ?? awayTeam["logo"] as? String
        let homeLogoStr = (homeTeam["logos"] as? [[String: Any]])?.first?["href"] as? String
                       ?? homeTeam["logo"] as? String

        let rawStatusDetail = statusType["shortDetail"] as? String ?? statusType["detail"] as? String ?? ""
        let statusDetail: String
        if status == .pre, let isoDate = comps["date"] as? String {
            statusDetail = formatAWST(isoDate: isoDate)
        } else {
            statusDetail = rawStatusDetail
        }

        return HeaderInfo(
            awayAbbrev:   awayTeam["abbreviation"] as? String ?? "AWY",
            homeAbbrev:   homeTeam["abbreviation"] as? String ?? "HOM",
            awayName:     awayTeam["shortDisplayName"] as? String ?? awayTeam["displayName"] as? String ?? "Away",
            homeName:     homeTeam["shortDisplayName"] as? String ?? homeTeam["displayName"] as? String ?? "Home",
            awayLogo:     awayLogoStr.flatMap { URL(string: $0) },
            homeLogo:     homeLogoStr.flatMap { URL(string: $0) },
            awayScore:    away["score"] as? String ?? "0",
            homeScore:    home["score"] as? String ?? "0",
            status:       status,
            statusDetail: statusDetail,
            period:       periodStr,
            clock:        clockStr
        )
    }

    // ── Boxscore ─────────────────────────────────────────────────────────────

    private func parseBoxscore(_ json: [String: Any], sport: Sport) -> [Player] {
        let boxscore = json["boxscore"] as? [String: Any] ?? [:]
        let teams    = boxscore["players"] as? [[String: Any]] ?? []
        var players: [Player] = []

        for teamBlock in teams {
            let team       = teamBlock["team"] as? [String: Any] ?? [:]
            let abbrev     = team["abbreviation"] as? String ?? "???"
            let statistics = teamBlock["statistics"] as? [[String: Any]] ?? []

            for statBlock in statistics {
                let labels  = (statBlock["labels"] as? [String])
                           ?? (statBlock["names"]  as? [String])
                           ?? []
                let athletes = statBlock["athletes"] as? [[String: Any]] ?? []

                for athleteBlock in athletes {
                    let athleteInfo = athleteBlock["athlete"] as? [String: Any] ?? [:]
                    let name        = athleteInfo["shortName"] as? String
                                   ?? athleteInfo["displayName"] as? String ?? "Unknown"
                    let pid         = athleteInfo["id"] as? String ?? UUID().uuidString
                    let pos         = (athleteInfo["position"] as? [String: Any])?["abbreviation"] as? String ?? ""

                    let active      = athleteBlock["active"] as? Bool ?? true
                    let dnp         = athleteBlock["didNotPlay"] as? Bool ?? !active

                    // Reason for not playing
                    let reason      = athleteBlock["reason"] as? String ?? ""
                    let statusLabel: String = {
                        if !dnp { return "" }
                        let r = reason.lowercased()
                        if r.contains("injur") || r.contains("inj") { return "INJ" }
                        if r.contains("rest") { return "REST" }
                        if r.contains("suspend") || r.contains("susp") { return "SUSP" }
                        if r.contains("ill") { return "ILL" }
                        return "DNP"
                    }()

                    let stats = athleteBlock["stats"] as? [String] ?? []
                    let zipped = zip(labels, stats).map { ($0.0, $0.1) }

                    // Sport-specific column selection and sort key
                    let (filteredLabels, filteredValues, sortKey, fantasy) =
                        filterStats(labels: labels, values: stats, sport: sport, dnp: dnp)

                    players.append(Player(
                        id:           pid,
                        name:         name,
                        teamAbbrev:   abbrev,
                        position:     pos,
                        didNotPlay:   dnp,
                        statusLabel:  statusLabel,
                        statLabels:   filteredLabels,
                        statValues:   filteredValues,
                        sortKey:      sortKey,
                        fantasyPoints: fantasy
                    ))
                    _ = zipped
                }
            }
        }

        // Sort: active players by sortKey desc, then DNP players at bottom
        players.sort {
            if $0.didNotPlay != $1.didNotPlay { return !$0.didNotPlay }
            return $0.sortKey > $1.sortKey
        }
        return players
    }

    private func filterStats(labels: [String], values: [String], sport: Sport, dnp: Bool)
        -> (labels: [String], values: [String], sortKey: Double, fantasy: Double)
    {
        let statMap = Dictionary(uniqueKeysWithValues: zip(labels, values))

        func val(_ key: String) -> String { statMap[key] ?? statMap[key.uppercased()] ?? "-" }
        func dbl(_ key: String) -> Double { Double(val(key)) ?? 0 }

        switch sport {
        case .nba:
            let cols = ["PTS","REB","AST","STL","BLK","FG","3PT","FT","+/-","MIN"]
            let filt = cols.filter { statMap[$0] != nil || statMap[$0.uppercased()] != nil }
            let chosen = filt.isEmpty ? labels : filt
            let vals   = chosen.map { val($0) }
            return (chosen, vals, dbl("PTS"), 0)

        case .nhl:
            let cols = ["G","A","PTS","+/-","TOI","SOG","BS","HITS","PIM","FO%"]
            let filt = cols.filter { statMap[$0] != nil }
            let chosen = filt.isEmpty ? labels : filt
            let vals   = chosen.map { val($0) }
            return (chosen, vals, dbl("PTS"), 0)

        case .afl:
            // Calculate AFL Fantasy Points (standard formula)
            let d  = dbl("DIS") // Disposals (K+H)
            let k  = dbl("K")
            let h  = dbl("H")
            let m  = dbl("MK")
            let t  = dbl("TK")
            let g  = dbl("G")
            let b  = dbl("B")
            let ho = dbl("HO")
            let i50 = dbl("I50")
            let clr  = dbl("CLR")
            let ff   = dbl("FF")
            let fa   = dbl("FA")
            let cp   = dbl("CP")
            let up   = dbl("UP")
            let fantasy = k*3 + h*2 + m*3 + t*4 + g*6 + b*1 + ho*1 + i50*1 + clr*2
                        + ff*1 - fa*3 + cp*1 + up*1 + d*0
            let _ = (d, cp, up)

            let cols = ["FPTS","DIS","K","H","MK","TK","G","B","HO","I50","R50","CLR","CM","INT","FF","FA"]
            var chosenLabels: [String] = []
            var chosenValues: [String] = []
            for col in cols {
                if col == "FPTS" {
                    chosenLabels.append("FPTS")
                    chosenValues.append(dnp ? "-" : String(format: "%.0f", fantasy))
                } else if let v = statMap[col] {
                    chosenLabels.append(col)
                    chosenValues.append(v)
                }
            }
            if chosenLabels.isEmpty {
                chosenLabels = labels
                chosenValues = values
            }
            let disposals = (Double(statMap["DIS"] ?? "") ?? 0)
                          + (Double(statMap["K"] ?? "") ?? 0)
                          + (Double(statMap["H"] ?? "") ?? 0)
            return (chosenLabels, chosenValues, disposals, fantasy)

        case .nfl:
            // Merge all stat categories
            let cols = ["C/ATT","YDS","TD","INT","RYDS","RTD","REC","RCYDS","RCTD","TKL","SACKS"]
            let filt = cols.filter { statMap[$0] != nil }
            let chosen = filt.isEmpty ? labels : filt
            let vals   = chosen.map { val($0) }
            let sortVal = dbl("YDS") + dbl("RYDS") + dbl("RCYDS")
            return (chosen, vals, sortVal, 0)
        }
    }

    // ── Timeline ─────────────────────────────────────────────────────────────

    private let aflScoreTypes: Set<String> = ["goal", "behind", "rushed"]

    private func parseTimeline(_ json: [String: Any], sport: Sport) -> [TimelineEntry] {
        let plays = json["plays"] as? [[String: Any]] ?? []
        var result: [TimelineEntry] = []

        for p in plays {
            let typeObj   = p["type"] as? [String: Any] ?? [:]
            let typeName  = typeObj["type"] as? String ?? ""
            let isScoring = (p["scoringPlay"] as? Bool == true)
                         || (sport == .afl && aflScoreTypes.contains(typeName))
            if !isScoring { continue }

            let periodObj = p["period"] as? [String: Any] ?? [:]
            let periodStr: String
            if sport == .afl {
                let n = periodObj["number"] as? Int ?? 0
                periodStr = n > 0 ? "Q\(n)" : ""
            } else {
                periodStr = periodObj["displayValue"] as? String ?? ""
            }

            let clockObj  = p["clock"] as? [String: Any] ?? [:]
            let clockStr  = clockObj["displayValue"] as? String ?? ""
            let teamObj   = p["team"] as? [String: Any] ?? [:]
            let teamId    = teamObj["id"] as? String ?? ""
            let typeLabel = typeObj["text"] as? String ?? ""
            let text      = p["text"] as? String ?? ""

            result.append(TimelineEntry(
                period:     periodStr,
                clock:      clockStr,
                text:       p["shortDescription"] as? String ?? text,
                typeLabel:  typeLabel,
                awayScore:  "\(p["awayScore"] ?? "")",
                homeScore:  "\(p["homeScore"] ?? "")",
                teamId:     teamId
            ))
        }
        result.reverse() // most recent first
        return result
    }

    // ── H2H ─────────────────────────────────────────────────────────────────

    private func parseH2H(_ json: [String: Any]) -> ([H2HGame], String) {
        // Standard leagues
        if let seriesList = json["seasonseries"] as? [[String: Any]],
           let series = seriesList.first {
            let label  = series["seriesLabel"] as? String
                      ?? series["summary"] as? String
                      ?? "Season Series"
            var games: [H2HGame] = []
            for ev in series["events"] as? [[String: Any]] ?? [] {
                let comps = ev["competitors"] as? [[String: Any]] ?? []
                let away  = comps.first(where: { ($0["homeAway"] as? String) == "away" }) ?? [:]
                let home  = comps.first(where: { ($0["homeAway"] as? String) == "home" }) ?? [:]
                let awayT = away["team"] as? [String: Any] ?? [:]
                let homeT = home["team"] as? [String: Any] ?? [:]
                let date  = formatDateString(ev["date"] as? String ?? "")
                games.append(H2HGame(
                    date:        date,
                    awayAbbrev:  awayT["abbreviation"] as? String ?? "AWY",
                    homeAbbrev:  homeT["abbreviation"] as? String ?? "HOM",
                    awayScore:   away["score"] as? String ?? "?",
                    homeScore:   home["score"] as? String ?? "?",
                    awayWinner:  away["winner"] as? Bool ?? false,
                    homeWinner:  home["winner"] as? Bool ?? false
                ))
            }
            return (games, label)
        }

        // AFL: lastFiveGames
        let lfg = json["lastFiveGames"] as? [[String: Any]] ?? []
        guard lfg.count >= 2 else { return ([], "") }

        let t0 = lfg[0], t1 = lfg[1]
        let t0Team = t0["team"] as? [String: Any] ?? [:]
        let t1Team = t1["team"] as? [String: Any] ?? [:]
        let t0Id   = t0Team["id"] as? String ?? ""
        let t0Abbr = t0Team["abbreviation"] as? String ?? "T1"
        let t1Abbr = t1Team["abbreviation"] as? String ?? "T2"

        var t0Map: [String: [String: Any]] = [:]
        var t1Map: [String: [String: Any]] = [:]
        for ev in t0["events"] as? [[String: Any]] ?? [] {
            if let id = ev["id"] as? String { t0Map[id] = ev }
        }
        for ev in t1["events"] as? [[String: Any]] ?? [] {
            if let id = ev["id"] as? String { t1Map[id] = ev }
        }

        let commonIds = Set(t0Map.keys).intersection(t1Map.keys).sorted()
        var games: [H2HGame] = []
        for gid in commonIds {
            guard let ev = t0Map[gid] else { continue }
            let homeId  = ev["homeTeamId"] as? String ?? ""
            let t0Home  = homeId == t0Id
            let date    = formatDateString(ev["gameDate"] as? String ?? "")
            let hscore  = "\(ev["homeTeamScore"] ?? "?")"
            let ascore  = "\(ev["awayTeamScore"] ?? "?")"
            let result  = ev["gameResult"] as? String ?? ""
            games.append(H2HGame(
                date:       date,
                awayAbbrev: t0Home ? t1Abbr : t0Abbr,
                homeAbbrev: t0Home ? t0Abbr : t1Abbr,
                awayScore:  t0Home ? ascore : hscore,
                homeScore:  t0Home ? hscore : ascore,
                awayWinner: t0Home ? false : result == "W",
                homeWinner: t0Home ? result == "W" : false
            ))
        }
        return (games, games.isEmpty ? "No Recent Meetings" : "Recent Meetings (\(games.count))")
    }

    private func formatDateString(_ str: String) -> String {
        let fmtIn = ISO8601DateFormatter()
        fmtIn.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let fmtOut = DateFormatter()
        fmtOut.dateFormat = "MMM d"
        if let d = fmtIn.date(from: str) ?? ISO8601DateFormatter().date(from: str) {
            return fmtOut.string(from: d)
        }
        return String(str.prefix(10))
    }
}
