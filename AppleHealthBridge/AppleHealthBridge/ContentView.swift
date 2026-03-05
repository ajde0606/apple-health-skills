import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var coordinator: SyncCoordinator
    @ObservedObject private var config = AppConfig.shared

    var body: some View {
        NavigationView {
            List {
                if !config.isConfigured {
                    setupBanner
                }

                Section {
                    NavigationLink(destination: AppleHealthView()) {
                        MenuRow(
                            title: "Apple Health",
                            subtitle: config.isConfigured ? coordinator.status : "Not configured",
                            icon: "heart.fill",
                            color: .red
                        )
                    }

                    NavigationLink(destination: LiveView()) {
                        MenuRow(
                            title: "Wahoo",
                            subtitle: "Live Heart Rate",
                            icon: "sensor.tag.radiowaves.forward.fill",
                            color: .blue
                        )
                    }

                    NavigationLink(destination: SettingsView()) {
                        MenuRow(
                            title: "Settings",
                            subtitle: config.isConfigured ? "Configured" : "Setup required",
                            icon: "gear",
                            color: .gray
                        )
                    }
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("Health Bridge")
        }
    }

    private var setupBanner: some View {
        Section {
            NavigationLink(destination: SettingsView()) {
                HStack(spacing: 10) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(.orange)
                    Text("Setup required — open Settings to configure")
                        .font(.subheadline)
                }
                .padding(.vertical, 4)
            }
        }
    }
}

// MARK: - Menu Row

struct MenuRow: View {
    let title: String
    let subtitle: String
    let icon: String
    let color: Color

    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundStyle(.white)
                .frame(width: 44, height: 44)
                .background(color, in: RoundedRectangle(cornerRadius: 10))

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.headline)
                Text(subtitle)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 4)
    }
}
