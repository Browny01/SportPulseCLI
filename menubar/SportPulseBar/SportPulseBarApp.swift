import SwiftUI
import AppKit

@main
struct SportPulseBarApp: App {

    @StateObject private var state = AppState()

    var body: some Scene {
        MenuBarExtra {
            PopoverView()
                .environmentObject(state)
                .onAppear { state.isPopoverOpen = true }
                .onDisappear { state.isPopoverOpen = false }
        } label: {
            menuBarLabel
        }
        .menuBarExtraStyle(.window)
    }

    @ViewBuilder
    private var menuBarLabel: some View {
        if !state.pinnedGameIds.isEmpty {
            // Pinned: score text only, no icon
            Text(state.menuBarText)
                .font(.system(size: 11, weight: .medium, design: .monospaced))
        } else if let icon = makeMenuBarIcon() {
            Image(nsImage: icon)
        } else {
            Text("SportPulse")
        }
    }

    /// Loads the custom PDF icon from the asset catalog, stamps it to exactly
    /// 18×18pt (the correct macOS menu bar icon size).
    private func makeMenuBarIcon() -> NSImage? {
        guard let img = NSImage(named: "MenuBarIcon") else { return nil }
        img.size = NSSize(width: 18, height: 18)
        return img
    }
}


