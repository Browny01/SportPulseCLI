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
        // When a custom icon exists in Assets (menubar-icon.pdf), it shows here.
        // Drop your PDF into Assets.xcassets/MenuBarIcon.imageset/ and switch
        // the comment below to use the image instead of the text label.
        if NSImage(named: "MenuBarIcon") != nil {
            Image("MenuBarIcon")
                .renderingMode(.template)
        } else {
            Text(state.menuBarText)
                .font(.system(size: 12, weight: .medium, design: .monospaced))
        }
    }
}

