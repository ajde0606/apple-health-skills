import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var coordinator: SyncCoordinator
    @ObservedObject private var config = AppConfig.shared

    var body: some View {
        NavigationView {
            VStack(spacing: 12) {
                if !config.isConfigured {
                    setupBanner
                }

                Text(coordinator.status)
                    .font(.subheadline)

                Text(coordinator.lastResult)
                    .font(.footnote)
                    .foregroundStyle(.secondary)

                Button("Authorize HealthKit") {
                    Task { await coordinator.authorize() }
                }
                .buttonStyle(.borderedProminent)
                .disabled(!config.isConfigured)

                Button("Bootstrap Sync (Last 14 Days)") {
                    Task { await coordinator.bootstrapSync() }
                }
                .buttonStyle(.bordered)
                .disabled(!config.isConfigured)

                Button("Incremental Sync") {
                    Task { await coordinator.incrementalSync() }
                }
                .buttonStyle(.bordered)
                .disabled(!config.isConfigured)

                GroupBox("Sync Logs") {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 6) {
                            if coordinator.logs.isEmpty {
                                Text("No logs yet")
                                    .foregroundStyle(.secondary)
                            } else {
                                ForEach(Array(coordinator.logs.enumerated()), id: \.offset) { _, line in
                                    Text(line)
                                        .font(.caption2)
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                }
                            }
                        }
                    }
                    .frame(maxHeight: 180)
                }

                Spacer()
            }
            .padding()
            .navigationTitle("AppleHealthBridge")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    NavigationLink(destination: SettingsView()) {
                        Image(systemName: "gear")
                    }
                }
            }
        }
    }

    private var setupBanner: some View {
        NavigationLink(destination: SettingsView()) {
            HStack {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundStyle(.orange)
                Text("Tap to complete setup")
                    .font(.subheadline)
                    .foregroundStyle(.primary)
                Spacer()
                Image(systemName: "chevron.right")
                    .foregroundStyle(.secondary)
                    .font(.caption)
            }
            .padding()
            .background(Color.orange.opacity(0.12), in: RoundedRectangle(cornerRadius: 10))
        }
    }
}
