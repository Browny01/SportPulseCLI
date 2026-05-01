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
        if let icon = makeMenuBarIcon() {
            Image(nsImage: icon)
        } else {
            Text(state.menuBarText)
                .font(.system(size: 12, weight: .medium, design: .monospaced))
        }
    }

    /// Loads the custom PDF icon from the asset catalog, stamps it to exactly
    /// 18×18pt (the correct macOS menu bar icon size), and marks it as a
    /// template image so macOS tints it correctly for light/dark mode.
    private func makeMenuBarIcon() -> NSImage? {
        guard let source = NSImage(named: "MenuBarIcon") else { return nil }
        let size = NSSize(width: 18, height: 18)
        let target = NSImage(size: size, flipped: false) { rect in
            source.draw(in: rect,
                        from: NSRect(origin: .zero, size: source.size),
                        operation: .copy,
                        fraction: 1.0)
            return true
        }
        target.isTemplate = true
        return target
    }
}


