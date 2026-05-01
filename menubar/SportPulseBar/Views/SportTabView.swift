import SwiftUI

struct SportTabView: View {
    @EnvironmentObject var state: AppState
    @Binding var navigationPath: [GameSummary]

    var body: some View {
        let games = state.gamesForSelectedSport
        Group {
            if state.isLoadingScoreboard && games.isEmpty {
                loadingView
            } else if games.isEmpty {
                emptyView
            } else {
                gameList(games)
            }
        }
        .frame(minHeight: 300, maxHeight: 440)
    }

    private var loadingView: some View {
        VStack(spacing: 12) {
            ProgressView()
            Text("Fetching \(state.selectedSport.displayName) scores…")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var emptyView: some View {
        VStack(spacing: 8) {
            Image(systemName: "sportscourt")
                .font(.largeTitle)
                .foregroundStyle(.secondary)
            Text("No games today")
                .font(.headline)
                .foregroundStyle(.secondary)
            Text("Check back later for live scores")
                .font(.caption)
                .foregroundStyle(.tertiary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func gameList(_ games: [GameSummary]) -> some View {
        ScrollView {
            LazyVStack(spacing: 0) {
                ForEach(games) { game in
                    Button {
                        navigationPath.append(game)
                        state.fetchDetail(sport: game.sport, gameId: game.id)
                    } label: {
                        GameRowView(game: game)
                    }
                    .buttonStyle(.plain)

                    if game.id != games.last?.id {
                        Divider().padding(.leading, 12)
                    }
                }
            }
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// MARK: - GameRowView
// ─────────────────────────────────────────────────────────────────────────────

struct GameRowView: View {
    let game: GameSummary

    var body: some View {
        HStack(spacing: 8) {
            statusBadge
            teamsAndScore
            Spacer()
            chevron
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .contentShape(Rectangle())
        .background(hoverBackground)
    }

    @State private var isHovered = false

    private var hoverBackground: some View {
        RoundedRectangle(cornerRadius: 6)
            .fill(isHovered ? Color.primary.opacity(0.06) : .clear)
            .padding(.horizontal, 4)
            .onHover { isHovered = $0 }
    }

    private var statusBadge: some View {
        Group {
            switch game.status {
            case .live:
                ZStack {
                    Circle().fill(Color.red).frame(width: 8, height: 8)
                    Circle().stroke(Color.red.opacity(0.4), lineWidth: 2).frame(width: 12, height: 12)
                }
            case .pre:
                Circle().fill(Color.secondary.opacity(0.3)).frame(width: 8, height: 8)
            case .post:
                Circle().fill(Color.secondary.opacity(0.15)).frame(width: 8, height: 8)
            }
        }
        .frame(width: 16)
    }

    private var teamsAndScore: some View {
        VStack(alignment: .leading, spacing: 3) {
            // Teams + scores
            HStack(spacing: 6) {
                teamLabel(abbrev: game.awayAbbrev, sport: game.sport, score: game.awayScore, isLeading: false)
                Text("·").font(.caption).foregroundStyle(.tertiary)
                teamLabel(abbrev: game.homeAbbrev, sport: game.sport, score: game.homeScore, isLeading: true)
            }
            // Status line
            statusLine
        }
    }

    private func teamLabel(abbrev: String, sport: Sport, score: String, isLeading: Bool) -> some View {
        HStack(spacing: 4) {
            Text(abbrev)
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(teamColor(sport: sport, abbrev: abbrev))
            Text(score)
                .font(.system(size: 13, weight: .bold, design: .monospaced))
                .foregroundStyle(.primary)
        }
    }

    @ViewBuilder
    private var statusLine: some View {
        switch game.status {
        case .live:
            HStack(spacing: 4) {
                Text("LIVE")
                    .font(.system(size: 10, weight: .bold))
                    .foregroundStyle(.red)
                if !game.period.isEmpty {
                    Text(game.period)
                        .font(.system(size: 10, weight: .medium, design: .monospaced))
                        .foregroundStyle(.secondary)
                }
                if !game.clock.isEmpty {
                    Text(game.clock)
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundStyle(.secondary)
                }
            }
        case .pre:
            Text(game.statusDetail)
                .font(.system(size: 10))
                .foregroundStyle(.secondary)
        case .post:
            Text("Final")
                .font(.system(size: 10, weight: .medium))
                .foregroundStyle(.secondary)
        }
    }

    private var chevron: some View {
        Image(systemName: "chevron.right")
            .font(.caption2)
            .foregroundStyle(.tertiary)
    }
}
