import SwiftUI

struct ContentView: View {
    @StateObject private var coordinator = SyncCoordinator()

    var body: some View {
        NavigationView {
            VStack(spacing: 12) {
                Text("Apple Health Bridge")
                    .font(.title2)
                    .bold()

                Text(coordinator.status)
                    .font(.subheadline)

                Text(coordinator.lastResult)
                    .font(.footnote)
                    .foregroundStyle(.secondary)

                Button("Authorize HealthKit") {
                    Task { await coordinator.authorize() }
                }
                .buttonStyle(.borderedProminent)

                Button("Bootstrap Sync (Last 14 Days)") {
                    Task { await coordinator.bootstrapSync() }
                }
                .buttonStyle(.bordered)

                Button("Incremental Sync") {
                    Task { await coordinator.incrementalSync() }
                }
                .buttonStyle(.bordered)

                Spacer()
            }
            .padding()
            .navigationTitle("AppleHealthBridge")
        }
    }
}
