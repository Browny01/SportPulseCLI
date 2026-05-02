import SwiftUI
import Combine

// ─────────────────────────────────────────────────────────────────────────────
// MARK: - AppState
// ─────────────────────────────────────────────────────────────────────────────

@MainActor
final class AppState: ObservableObject {

    // ── Published state ───────────────────────────────────────────────────────

    @Published var gamesBySport: [Sport: [GameSummary]] = [:]
    @Published var selectedSport: Sport = .nba
    @Published var selectedGame: GameDetail? = nil
    @Published var isLoadingScoreboard = false
    @Published var isLoadingDetail     = false
    @Published var lastRefreshed: Date? = nil
    @Published var error: String?       = nil

    // Menu bar cycling
    @Published var menuBarText: String = "SportPulse"

    // Pinned game — shows that game's score in menu bar instead of cycling
    @Published var pinnedGameId: String? = nil

    // Popover is open — used to speed up refresh
    var isPopoverOpen = false {
        didSet { restartRefreshTimer() }
    }

    // ── Private ───────────────────────────────────────────────────────────────

    private var refreshTimer:  AnyCancellable?
    private var cycleTimer:    AnyCancellable?
    private var cycleIndex     = 0
    private var liveGames:     [GameSummary] = []
    private var detailTask:    Task<Void, Never>? = nil

    // ── Init ─────────────────────────────────────────────────────────────────

    init() {
        Task { await fetchAll() }
        startCycleTimer()
        restartRefreshTimer()
    }

    // ─────────────────────────────────────────────────────────────────────────
    // MARK: - Data Fetching
    // ─────────────────────────────────────────────────────────────────────────

    func fetchAll() async {
        isLoadingScoreboard = true
        error = nil

        await withTaskGroup(of: (Sport, [GameSummary]).self) { group in
            for sport in Sport.allCases {
                group.addTask {
                    let games = (try? await ESPNService.shared.fetchScoreboard(sport: sport)) ?? []
                    return (sport, games)
                }
            }
            for await (sport, games) in group {
                gamesBySport[sport] = games
            }
        }

        // Rebuild live game list for cycling
        liveGames = Sport.allCases.flatMap { (gamesBySport[$0] ?? []).filter { $0.isLive } }
        updateMenuBarText()

        isLoadingScoreboard = false
        lastRefreshed = Date()
    }

    func fetchDetail(sport: Sport, gameId: String) {
        detailTask?.cancel()
        isLoadingDetail = true
        selectedGame = nil

        detailTask = Task { [weak self] in
            guard let self else { return }
            do {
                let detail = try await ESPNService.shared.fetchGameDetail(sport: sport, gameId: gameId)
                await MainActor.run {
                    self.selectedGame    = detail
                    self.isLoadingDetail = false
                }
            } catch {
                await MainActor.run {
                    self.error           = error.localizedDescription
                    self.isLoadingDetail = false
                }
            }
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // MARK: - Timers
    // ─────────────────────────────────────────────────────────────────────────

    private func restartRefreshTimer() {
        // Refresh interval: 12s if popover open + live game visible, else 20s
        let hasLive = !(gamesBySport[selectedSport] ?? []).filter { $0.isLive }.isEmpty
        let interval: TimeInterval = (isPopoverOpen && hasLive) ? 12 : 20

        refreshTimer?.cancel()
        refreshTimer = Timer.publish(every: interval, on: .main, in: .common)
            .autoconnect()
            .sink { [weak self] _ in
                Task { await self?.fetchAll() }
            }
    }

    private func startCycleTimer() {
        cycleTimer = Timer.publish(every: 3, on: .main, in: .common)
            .autoconnect()
            .sink { [weak self] _ in
                self?.advanceCycle()
            }
    }

    private func advanceCycle() {
        guard !liveGames.isEmpty else {
            menuBarText = "SportPulse"
            return
        }
        cycleIndex = (cycleIndex + 1) % liveGames.count
        updateMenuBarText()
    }

    private func updateMenuBarText() {
        // Pinned game takes priority over cycling
        if let pinId = pinnedGameId {
            for sport in Sport.allCases {
                if let game = (gamesBySport[sport] ?? []).first(where: { $0.id == pinId }) {
                    let clock  = game.clock.isEmpty  ? "" : " \(game.clock)"
                    let period = game.period.isEmpty ? "" : " \(game.period)\(clock)"
                    menuBarText = "\(game.sport.emoji) \(game.awayAbbrev) \(game.awayScore) · \(game.homeAbbrev) \(game.homeScore)\(period)"
                    return
                }
            }
            // Pinned game no longer in any scoreboard — clear pin
            pinnedGameId = nil
        }

        guard !liveGames.isEmpty else {
            menuBarText = "SportPulse"
            return
        }
        if cycleIndex >= liveGames.count { cycleIndex = 0 }
        let game = liveGames[cycleIndex]
        let clock = game.clock.isEmpty ? "" : " \(game.clock)"
        let period = game.period.isEmpty ? "" : " \(game.period)\(clock)"
        menuBarText = "\(game.sport.emoji) \(game.awayAbbrev) \(game.awayScore) · \(game.homeAbbrev) \(game.homeScore)\(period)"
    }

    func togglePin(gameId: String) {
        pinnedGameId = (pinnedGameId == gameId) ? nil : gameId
        updateMenuBarText()
    }

    // ─────────────────────────────────────────────────────────────────────────
    // MARK: - Helpers
    // ─────────────────────────────────────────────────────────────────────────

    var lastRefreshedText: String {
        guard let d = lastRefreshed else { return "Never" }
        let secs = Int(Date().timeIntervalSince(d))
        if secs < 5  { return "just now" }
        if secs < 60 { return "\(secs)s ago" }
        return "\(secs / 60)m ago"
    }

    var gamesForSelectedSport: [GameSummary] {
        gamesBySport[selectedSport] ?? []
    }
}
