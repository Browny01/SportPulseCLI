import SwiftUI

struct GameDetailView: View {
    let game: GameSummary

    @EnvironmentObject var state: AppState
    @State private var teamFilter: TeamFilter = .all
    @State private var detailTab: DetailTab   = .stats

    enum TeamFilter: CaseIterable {
        case all, away, home
        func label(away: String, home: String) -> String {
            switch self {
            case .all:  return "All"
            case .away: return away
            case .home: return home
            }
        }
    }

    enum DetailTab: String, CaseIterable {
        case stats    = "Stats"
        case timeline = "Timeline"
        case h2h      = "H2H"
    }

    var body: some View {
        VStack(spacing: 0) {

            if state.isLoadingDetail {
                loadingView
            } else if let detail = state.selectedGame {
                ScrollView {
                    VStack(spacing: 0) {
                        ScoreBoxView(detail: detail)
                            .padding(.horizontal, 12)
                            .padding(.top, 12)
                            .padding(.bottom, 8)

                        detailTabPicker(detail: detail)
                            .padding(.horizontal, 12)
                            .padding(.bottom, 8)

                        detailContent(detail: detail)
                    }
                }
            } else {
                errorView
            }
        }
        .navigationTitle("\(game.awayAbbrev) @ \(game.homeAbbrev)")
        .navigationBarBackButtonHidden(false)
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button {
                    NSWorkspace.shared.open(game.sport.kayoURL)
                } label: {
                    Label("Watch on Kayo", systemImage: "play.tv")
                        .font(.caption)
                }
                .help("Watch on Kayo Sports")
            }
        }
        .frame(width: 380)
    }

    // ── Loading / Error ───────────────────────────────────────────────────────

    private var loadingView: some View {
        VStack(spacing: 12) {
            ProgressView()
            Text("Loading game data…")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, minHeight: 200)
    }

    private var errorView: some View {
        VStack(spacing: 8) {
            Image(systemName: "exclamationmark.triangle")
                .font(.largeTitle)
                .foregroundStyle(.orange)
            Text("Could not load game data")
                .font(.headline)
            Button("Retry") {
                state.fetchDetail(sport: game.sport, gameId: game.id)
            }
        }
        .frame(maxWidth: .infinity, minHeight: 200)
    }

    // ── Tab Picker ────────────────────────────────────────────────────────────

    private func detailTabPicker(detail: GameDetail) -> some View {
        Picker("View", selection: $detailTab) {
            ForEach(DetailTab.allCases, id: \.self) { tab in
                Text(tab.rawValue).tag(tab)
            }
        }
        .pickerStyle(.segmented)
    }

    // ── Content ───────────────────────────────────────────────────────────────

    @ViewBuilder
    private func detailContent(detail: GameDetail) -> some View {
        switch detailTab {
        case .stats:
            statsContent(detail: detail)
        case .timeline:
            timelineContent(detail: detail)
        case .h2h:
            h2hContent(detail: detail)
        }
    }

    // ── Stats ─────────────────────────────────────────────────────────────────

    private func statsContent(detail: GameDetail) -> some View {
        VStack(spacing: 0) {
            teamFilterPicker(detail: detail)
                .padding(.horizontal, 12)
                .padding(.bottom, 6)

            if detail.players.isEmpty {
                Text("No player stats available")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .padding()
            } else {
                playerTable(detail: detail)
            }
        }
    }

    private func teamFilterPicker(detail: GameDetail) -> some View {
        Picker("Team", selection: $teamFilter) {
            ForEach(TeamFilter.allCases, id: \.self) { f in
                Text(f.label(away: detail.awayAbbrev, home: detail.homeAbbrev)).tag(f)
            }
        }
        .pickerStyle(.segmented)
    }

    private func visiblePlayers(_ detail: GameDetail) -> [Player] {
        switch teamFilter {
        case .all:  return detail.players
        case .away: return detail.players.filter { $0.teamAbbrev == detail.awayAbbrev }
        case .home: return detail.players.filter { $0.teamAbbrev == detail.homeAbbrev }
        }
    }

    private func playerTable(detail: GameDetail) -> some View {
        let players = visiblePlayers(detail)
        let labels  = players.first(where: { !$0.statLabels.isEmpty })?.statLabels ?? []

        return VStack(spacing: 0) {
            // Column headers
            if !labels.isEmpty {
                PlayerHeaderRow(labels: labels)
                    .padding(.horizontal, 12)
                Divider()
            }

            // Player rows
            ForEach(players) { player in
                PlayerRowView(player: player, sport: detail.sport, labels: labels)
                    .padding(.horizontal, 12)
                if player.id != players.last?.id {
                    Divider().padding(.leading, 12)
                }
            }
        }
    }

    // ── Timeline ──────────────────────────────────────────────────────────────

    private func timelineContent(detail: GameDetail) -> some View {
        Group {
            if detail.timeline.isEmpty {
                VStack(spacing: 8) {
                    Image(systemName: "timeline.selection")
                        .font(.title2)
                        .foregroundStyle(.secondary)
                    Text(detail.status == .pre ? "Game hasn't started yet" : "No scoring plays available")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .padding()
            } else {
                VStack(spacing: 0) {
                    ForEach(detail.timeline) { entry in
                        TimelineRowView(
                            entry: entry,
                            awayAbbrev: detail.awayAbbrev,
                            homeAbbrev: detail.homeAbbrev,
                            sport: detail.sport
                        )
                        .padding(.horizontal, 12)
                        if entry.id != detail.timeline.last?.id {
                            Divider().padding(.leading, 12)
                        }
                    }
                }
            }
        }
    }

    // ── H2H ──────────────────────────────────────────────────────────────────

    private func h2hContent(detail: GameDetail) -> some View {
        Group {
            if detail.h2hGames.isEmpty {
                VStack(spacing: 8) {
                    Image(systemName: "arrow.left.and.right.circle")
                        .font(.title2)
                        .foregroundStyle(.secondary)
                    Text(detail.h2hLabel.isEmpty ? "No head-to-head data available" : detail.h2hLabel)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                }
                .padding()
            } else {
                VStack(spacing: 0) {
                    if !detail.h2hLabel.isEmpty {
                        Text(detail.h2hLabel)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .padding(.vertical, 6)
                        Divider()
                    }
                    ForEach(detail.h2hGames) { h2h in
                        H2HRowView(game: h2h, sport: detail.sport)
                            .padding(.horizontal, 12)
                        if h2h.id != detail.h2hGames.last?.id {
                            Divider().padding(.leading, 12)
                        }
                    }
                }
            }
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// MARK: - ScoreBoxView
// ─────────────────────────────────────────────────────────────────────────────

struct ScoreBoxView: View {
    let detail: GameDetail

    var body: some View {
        VStack(spacing: 6) {
            // Teams + Scores
            HStack(alignment: .center, spacing: 0) {
                teamSide(abbrev: detail.awayAbbrev, name: detail.awayName,
                         score: detail.awayScore, sport: detail.sport)
                centerStatus
                teamSide(abbrev: detail.homeAbbrev, name: detail.homeName,
                         score: detail.homeScore, sport: detail.sport)
            }
        }
        .padding(14)
        .background {
            RoundedRectangle(cornerRadius: 12)
                .fill(Color(nsColor: .controlBackgroundColor))
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(Color.primary.opacity(0.08), lineWidth: 1)
                )
        }
    }

    private func teamSide(abbrev: String, name: String, score: String, sport: Sport) -> some View {
        VStack(spacing: 4) {
            Text(abbrev)
                .font(.system(size: 15, weight: .bold))
                .foregroundStyle(teamColor(sport: sport, abbrev: abbrev))
            Text(name)
                .font(.system(size: 10))
                .foregroundStyle(.secondary)
                .lineLimit(1)
            Text(score)
                .font(.system(size: 28, weight: .heavy, design: .monospaced))
                .foregroundStyle(.primary)
        }
        .frame(maxWidth: .infinity)
    }

    private var centerStatus: some View {
        VStack(spacing: 2) {
            switch detail.status {
            case .live:
                HStack(spacing: 4) {
                    Circle().fill(.red).frame(width: 6, height: 6)
                    Text("LIVE").font(.system(size: 9, weight: .heavy)).foregroundStyle(.red)
                }
                if !detail.period.isEmpty {
                    Text(detail.period)
                        .font(.system(size: 12, weight: .semibold, design: .monospaced))
                }
                if !detail.clock.isEmpty {
                    Text(detail.clock)
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundStyle(.secondary)
                }
            case .pre:
                Image(systemName: "clock")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text(detail.statusDetail)
                    .font(.system(size: 10))
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            case .post:
                Text("FINAL")
                    .font(.system(size: 10, weight: .bold))
                    .foregroundStyle(.secondary)
                if !detail.statusDetail.isEmpty {
                    Text(detail.statusDetail)
                        .font(.system(size: 9))
                        .foregroundStyle(.tertiary)
                }
            }
        }
        .frame(width: 60)
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// MARK: - PlayerHeaderRow
// ─────────────────────────────────────────────────────────────────────────────

struct PlayerHeaderRow: View {
    let labels: [String]

    var body: some View {
        HStack(spacing: 0) {
            Text("#")
                .font(.system(size: 10, weight: .semibold))
                .foregroundStyle(.secondary)
                .frame(width: 22, alignment: .trailing)
            Text("PLAYER")
                .font(.system(size: 10, weight: .semibold))
                .foregroundStyle(.secondary)
                .frame(width: 90, alignment: .leading)
                .padding(.leading, 6)
            Spacer()
            ForEach(labels.prefix(7), id: \.self) { label in
                Text(label)
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundStyle(.secondary)
                    .frame(width: 32, alignment: .trailing)
            }
        }
        .padding(.vertical, 5)
        .background(Color(nsColor: .controlBackgroundColor))
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// MARK: - TimelineRowView
// ─────────────────────────────────────────────────────────────────────────────

struct TimelineRowView: View {
    let entry: TimelineEntry
    let awayAbbrev: String
    let homeAbbrev: String
    let sport: Sport

    var body: some View {
        HStack(alignment: .center, spacing: 8) {
            // Period + Clock
            VStack(alignment: .trailing, spacing: 1) {
                Text(entry.period)
                    .font(.system(size: 10, weight: .semibold, design: .monospaced))
                    .foregroundStyle(.secondary)
                if !entry.clock.isEmpty {
                    Text(entry.clock)
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundStyle(.tertiary)
                }
            }
            .frame(width: 36, alignment: .trailing)

            // Type badge (AFL: Goal / Behind)
            if !entry.typeLabel.isEmpty {
                Text(entry.typeLabel)
                    .font(.system(size: 9, weight: .semibold))
                    .padding(.horizontal, 5)
                    .padding(.vertical, 2)
                    .background(typeBadgeColor(entry.typeLabel).opacity(0.15))
                    .foregroundStyle(typeBadgeColor(entry.typeLabel))
                    .clipShape(Capsule())
            }

            // Play text
            Text(entry.text)
                .font(.system(size: 11))
                .foregroundStyle(.primary)
                .lineLimit(2)
                .frame(maxWidth: .infinity, alignment: .leading)

            // Score
            VStack(alignment: .trailing, spacing: 1) {
                Text(entry.awayScore)
                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                Text(entry.homeScore)
                    .font(.system(size: 10, weight: .bold, design: .monospaced))
            }
            .foregroundStyle(.secondary)
        }
        .padding(.vertical, 7)
    }

    private func typeBadgeColor(_ label: String) -> Color {
        switch label.lowercased() {
        case "goal":    return .green
        case "behind":  return .yellow
        case "rushed":  return .orange
        default:        return .blue
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// MARK: - H2HRowView
// ─────────────────────────────────────────────────────────────────────────────

struct H2HRowView: View {
    let game: H2HGame
    let sport: Sport

    var body: some View {
        HStack(spacing: 8) {
            Text(game.date)
                .font(.system(size: 10))
                .foregroundStyle(.secondary)
                .frame(width: 40, alignment: .leading)

            Spacer()

            teamScore(abbrev: game.awayAbbrev, score: game.awayScore,
                      winner: game.awayWinner, sport: sport)

            Text("@")
                .font(.system(size: 10))
                .foregroundStyle(.tertiary)

            teamScore(abbrev: game.homeAbbrev, score: game.homeScore,
                      winner: game.homeWinner, sport: sport)
        }
        .padding(.vertical, 7)
    }

    private func teamScore(abbrev: String, score: String, winner: Bool, sport: Sport) -> some View {
        HStack(spacing: 4) {
            Text(abbrev)
                .font(.system(size: 12, weight: winner ? .bold : .regular))
                .foregroundStyle(winner ? teamColor(sport: sport, abbrev: abbrev) : .secondary)
            Text(score)
                .font(.system(size: 12, weight: winner ? .bold : .regular, design: .monospaced))
                .foregroundStyle(winner ? .primary : .secondary)
        }
    }
}
