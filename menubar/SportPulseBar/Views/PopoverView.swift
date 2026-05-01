import SwiftUI

struct PopoverView: View {
    @EnvironmentObject var state: AppState
    @State private var navigationPath: [GameSummary] = []

    var body: some View {
        NavigationStack(path: $navigationPath) {
            VStack(spacing: 0) {

                // ── Sport Picker ─────────────────────────────────────────────
                Picker("Sport", selection: $state.selectedSport) {
                    ForEach(Sport.allCases) { sport in
                        Text(sport.displayName).tag(sport)
                    }
                }
                .pickerStyle(.segmented)
                .padding(.horizontal, 12)
                .padding(.vertical, 10)
                .background(Color(nsColor: .windowBackgroundColor))

                Divider()

                // ── Game List ────────────────────────────────────────────────
                SportTabView(navigationPath: $navigationPath)

                Divider()

                // ── Footer ───────────────────────────────────────────────────
                footerBar
            }
            .frame(width: 380)
            .navigationDestination(for: GameSummary.self) { game in
                GameDetailView(game: game)
            }
        }
    }

    private var footerBar: some View {
        HStack {
            if state.isLoadingScoreboard {
                ProgressView().scaleEffect(0.6).frame(width: 14, height: 14)
                Text("Refreshing…")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else {
                Image(systemName: "clock")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                Text("Updated \(state.lastRefreshedText)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            Button {
                Task { await state.fetchAll() }
            } label: {
                Image(systemName: "arrow.clockwise")
                    .font(.caption)
            }
            .buttonStyle(.plain)
            .foregroundStyle(.secondary)
            .help("Refresh now")

            Button {
                NSApplication.shared.terminate(nil)
            } label: {
                Image(systemName: "xmark.circle")
                    .font(.caption)
            }
            .buttonStyle(.plain)
            .foregroundStyle(.secondary)
            .help("Quit SportPulse")
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(Color(nsColor: .windowBackgroundColor))
    }
}
