import SwiftUI

private let historyOptions: [(label: String, days: Int)] = [
    ("7 days", 7),
    ("14 days", 14),
    ("30 days", 30),
    ("90 days", 90),
    ("6 months", 180),
    ("1 year", 365),
]

struct AppleHealthView: View {
    @EnvironmentObject private var coordinator: SyncCoordinator
    @ObservedObject private var config = AppConfig.shared

    var body: some View {
        List {
            statusSection
            authorizeSection
            bootstrapSection
            liveSyncSection
            logsSection
        }
        .listStyle(.insetGrouped)
        .navigationTitle("Apple Health")
        .navigationBarTitleDisplayMode(.large)
    }

    // MARK: - Sections

    private var statusSection: some View {
        Section("Status") {
            HStack(spacing: 10) {
                Image(systemName: statusIcon)
                    .foregroundStyle(statusColor)
                VStack(alignment: .leading, spacing: 2) {
                    Text(coordinator.status)
                        .font(.subheadline)
                    if !coordinator.lastResult.isEmpty {
                        Text(coordinator.lastResult)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .padding(.vertical, 2)
        }
    }

    private var authorizeSection: some View {
        Section {
            Button {
                Task { await coordinator.authorize() }
            } label: {
                Label("Authorize HealthKit", systemImage: "heart.text.square.fill")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(.red)
            .disabled(!config.isConfigured)
            .listRowInsets(EdgeInsets(top: 10, leading: 16, bottom: 10, trailing: 16))
        } header: {
            Text("Permissions")
        } footer: {
            Text("Grants this app read access to your Apple Health data so it can sync samples to your Mac collector.")
        }
    }

    private var bootstrapSection: some View {
        Section {
            Picker("History window", selection: $config.bootstrapDays) {
                ForEach(historyOptions, id: \.days) { option in
                    Text(option.label).tag(option.days)
                }
            }

            Button {
                Task { await coordinator.bootstrapSync() }
            } label: {
                Label("Sync Health History", systemImage: "arrow.clockwise.icloud")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .disabled(!config.isConfigured)
            .listRowInsets(EdgeInsets(top: 10, leading: 16, bottom: 10, trailing: 16))
        } header: {
            Text("Bootstrap Sync")
        } footer: {
            Text("Downloads the selected window of historical Apple Health data and uploads it to your Mac collector. Safe to run multiple times — duplicates are ignored.")
        }
    }

    private var liveSyncSection: some View {
        Section {
            Button {
                Task { await coordinator.startBackgroundSync() }
            } label: {
                Label("Start Live Sync", systemImage: "dot.radiowaves.up.forward")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            .disabled(!config.isConfigured)
            .listRowInsets(EdgeInsets(top: 10, leading: 16, bottom: 10, trailing: 16))
        } header: {
            Text("Live Sync")
        } footer: {
            Text("Enables HealthKit background delivery so new samples (heart rate, glucose, etc.) are uploaded automatically as they arrive.")
        }
    }

    private var logsSection: some View {
        Section("Sync Logs") {
            if coordinator.logs.isEmpty {
                Text("No logs yet")
                    .foregroundStyle(.secondary)
                    .font(.caption)
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 4) {
                        ForEach(Array(coordinator.logs.enumerated()), id: \.offset) { _, line in
                            Text(line)
                                .font(.caption2)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                    .padding(.vertical, 4)
                }
                .frame(maxHeight: 220)
            }
        }
    }

    // MARK: - Helpers

    private var statusIcon: String {
        switch coordinator.status {
        case "Idle":                 return "circle"
        case "Authorized":           return "checkmark.circle.fill"
        case "Sync complete":        return "checkmark.circle.fill"
        case let s where s.hasPrefix("Sync failed"):   return "xmark.circle.fill"
        case let s where s.hasPrefix("Authorization failed"): return "xmark.circle.fill"
        default:                     return "arrow.clockwise"
        }
    }

    private var statusColor: Color {
        switch coordinator.status {
        case "Authorized", "Sync complete": return .green
        case let s where s.hasPrefix("Sync failed"):   return .red
        case let s where s.hasPrefix("Authorization failed"): return .red
        default: return .secondary
        }
    }
}
