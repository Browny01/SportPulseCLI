import SwiftUI

struct PlayerRowView: View {
    let player: Player
    let sport: Sport
    let labels: [String]

    var body: some View {
        Group {
            if player.didNotPlay {
                dnpRow
            } else {
                activeRow
            }
        }
        .contentShape(Rectangle())
        .onTapGesture {
            if let url = player.athleteURL {
                NSWorkspace.shared.open(url)
            }
        }
        .help(player.athleteURL != nil ? "View \(player.name)'s ESPN profile" : "")
    }

    // ── Active Player ─────────────────────────────────────────────────────────

    private var activeRow: some View {
        HStack(spacing: 0) {
            // Team color indicator
            teamColor(sport: sport, abbrev: player.teamAbbrev)
                .frame(width: 3)
                .clipShape(Capsule())
                .padding(.trailing, 5)

            // Name + position + external link hint
            VStack(alignment: .leading, spacing: 1) {
                HStack(spacing: 3) {
                    Text(player.name)
                        .font(.system(size: 12, weight: .semibold))
                        .lineLimit(1)
                    if player.athleteURL != nil {
                        Image(systemName: "arrow.up.right")
                            .font(.system(size: 8))
                            .foregroundStyle(.tertiary)
                    }
                }
                HStack(spacing: 3) {
                    Text(player.teamAbbrev)
                        .font(.system(size: 9))
                        .foregroundStyle(teamColor(sport: sport, abbrev: player.teamAbbrev))
                    if !player.position.isEmpty {
                        Text("·").font(.system(size: 9)).foregroundStyle(.tertiary)
                        Text(player.position)
                            .font(.system(size: 9))
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .frame(width: 110, alignment: .leading)

            Spacer()

            // Stat values aligned to column labels
            let shownLabels = labels.prefix(7)
            ForEach(Array(shownLabels.enumerated()), id: \.offset) { idx, label in
                let value = player.statValues.indices.contains(
                    player.statLabels.firstIndex(of: label) ?? -1
                ) ? (player.statLabels.firstIndex(of: label).map { player.statValues[$0] } ?? "-") : "-"

                Text(value)
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(highlightColor(label: label, value: value))
                    .frame(width: 32, alignment: .trailing)
            }
        }
        .padding(.vertical, 7)
    }

    // ── DNP Player ────────────────────────────────────────────────────────────

    private var dnpRow: some View {
        HStack(spacing: 0) {
            teamColor(sport: sport, abbrev: player.teamAbbrev)
                .opacity(0.3)
                .frame(width: 3)
                .clipShape(Capsule())
                .padding(.trailing, 5)

            Text(player.name)
                .font(.system(size: 12))
                .foregroundStyle(.tertiary)
                .lineLimit(1)
                .frame(width: 110, alignment: .leading)

            Spacer()

            Text(player.statusLabel.isEmpty ? "DNP" : player.statusLabel)
                .font(.system(size: 10, weight: .medium))
                .foregroundStyle(.secondary)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(Color.secondary.opacity(0.12))
                .clipShape(Capsule())
        }
        .padding(.vertical, 6)
        .opacity(0.6)
    }

    // ── Highlight logic ───────────────────────────────────────────────────────

    private func highlightColor(label: String, value: String) -> Color {
        guard let num = Double(value) else { return .primary }
        switch label {
        case "PTS", "G", "FPTS", "TD", "RCYDS", "RYDS":
            if num >= 25 { return .yellow }
            if num >= 15 { return .primary }
        case "REB", "MK":
            if num >= 10 { return .cyan }
        case "AST", "DIS":
            if num >= 10 { return .green }
        case "+/-":
            if num > 0  { return .green }
            if num < 0  { return .red }
        case "FA":
            if num > 0  { return .red }
        default: break
        }
        return .primary
    }
}
