import SwiftUI

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
            Text(state.menuBarText)
                .font(.system(size: 12, weight: .medium, design: .monospaced))
        }
        .menuBarExtraStyle(.window)
    }
}
