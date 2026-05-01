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
    @State private var isHovered = false

    var body: some View {
        HStack(spacing: 0) {
            // ── Away Team (left, trailing-aligned) ──────────────────────────
            awayBlock
                .frame(maxWidth: .infinity, alignment: .trailing)

            // ── Away Score ──────────────────────────────────────────────────
            Text(awayDisplayScore)
                .font(.system(size: 19, weight: .heavy, design: .monospaced))
                .foregroundStyle(awayScoreColor)
                .frame(width: 42, alignment: .trailing)
                .padding(.horizontal, 6)

            // ── Center Status ───────────────────────────────────────────────
            centerStatus
                .frame(width: 72)

            // ── Home Score ──────────────────────────────────────────────────
            Text(homeDisplayScore)
                .font(.system(size: 19, weight: .heavy, design: .monospaced))
                .foregroundStyle(homeScoreColor)
                .frame(width: 42, alignment: .leading)
                .padding(.horizontal, 6)

            // ── Home Team (right, leading-aligned) ─────────────────────────
            homeBlock
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 11)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(isHovered ? Color.primary.opacity(0.05) : .clear)
                .padding(.horizontal, 4)
        )
        .onHover { isHovered = $0 }
        .contentShape(Rectangle())
    }

    // ── Team blocks ───────────────────────────────────────────────────────────

    private var awayBlock: some View {
        VStack(alignment: .trailing, spacing: 2) {
            Text(game.awayAbbrev)
                .font(.system(size: 13, weight: .bold))
                .foregroundStyle(teamColor(sport: game.sport, abbrev: game.awayAbbrev))
            Text(game.awayName)
                .font(.system(size: 9))
                .foregroundStyle(.secondary)
                .lineLimit(1)
        }
    }

    private var homeBlock: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(game.homeAbbrev)
                .font(.system(size: 13, weight: .bold))
                .foregroundStyle(teamColor(sport: game.sport, abbrev: game.homeAbbrev))
            Text(game.homeName)
                .font(.system(size: 9))
                .foregroundStyle(.secondary)
                .lineLimit(1)
        }
    }

    // ── Center status block ───────────────────────────────────────────────────

    @ViewBuilder
    private var centerStatus: some View {
        VStack(spacing: 2) {
            switch game.status {
            case .live:
                HStack(spacing: 3) {
                    Circle().fill(.red).frame(width: 5, height: 5)
                    Text("LIVE")
                        .font(.system(size: 8, weight: .heavy))
                        .foregroundStyle(.red)
                }
                if !game.period.isEmpty {
                    Text(game.period)
                        .font(.system(size: 12, weight: .semibold, design: .monospaced))
                        .foregroundStyle(.primary)
                }
                if !game.clock.isEmpty {
                    Text(game.clock)
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundStyle(.secondary)
                }
            case .pre:
                Image(systemName: "clock")
                    .font(.system(size: 9))
                    .foregroundStyle(.secondary)
                Text(game.statusDetail)
                    .font(.system(size: 10))
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .lineLimit(2)
            case .post:
                Text("FT")
                    .font(.system(size: 11, weight: .bold))
                    .foregroundStyle(.secondary)
            }
        }
    }

    // ── Score display helpers ─────────────────────────────────────────────────

    private var awayDisplayScore: String {
        game.status == .pre ? "–" : game.awayScore
    }

    private var homeDisplayScore: String {
        game.status == .pre ? "–" : game.homeScore
    }

    private var awayScoreColor: Color {
        guard game.status == .post,
              let a = Int(game.awayScore), let h = Int(game.homeScore)
        else { return .primary }
        return a >= h ? .primary : .secondary
    }

    private var homeScoreColor: Color {
        guard game.status == .post,
              let h = Int(game.homeScore), let a = Int(game.awayScore)
        else { return .primary }
        return h >= a ? .primary : .secondary
    }
}

