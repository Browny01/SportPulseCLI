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
            menuBarLabel
        }
        .menuBarExtraStyle(.window)
    }

    @ViewBuilder
    private var menuBarLabel: some View {
        if NSImage(named: "MenuBarIcon") != nil {
            Image("MenuBarIcon")
                .renderingMode(.template)
                .resizable()
                .scaledToFit()
                .frame(width: 18, height: 18)
        } else {
            Text(state.menuBarText)
                .font(.system(size: 12, weight: .medium, design: .monospaced))
        }
    }
}

