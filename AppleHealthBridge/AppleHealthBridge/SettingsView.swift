import SwiftUI

struct SettingsView: View {
    @ObservedObject private var config = AppConfig.shared
    @State private var showScanner = false
    @State private var scanError: String?

    var body: some View {
        Form {
            // ── QR scan ───────────────────────────────────────────
            Section {
                Button {
                    showScanner = true
                } label: {
                    Label("Scan QR Code from Mac", systemImage: "qrcode.viewfinder")
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .listRowInsets(EdgeInsets(top: 12, leading: 16, bottom: 12, trailing: 16))

                if let err = scanError {
                    Text(err)
                        .font(.caption)
                        .foregroundStyle(.red)
                }
            } header: {
                Text("Quick Setup")
            } footer: {
                Text("Open https://<your-mac>:8443/qr in a browser and scan the code to fill in all fields at once.")
            }

            // ── Status ────────────────────────────────────────────
            Section {
                HStack {
                    Image(systemName: config.isConfigured ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                        .foregroundStyle(config.isConfigured ? .green : .orange)
                    Text(config.isConfigured ? "Ready to sync" : "Not configured")
                        .foregroundStyle(config.isConfigured ? .primary : .secondary)
                }
            }

            // ── Manual fields (advanced / fallback) ───────────────
            Section {
                LabeledContent("Device ID") {
                    Text(config.deviceID)
                        .foregroundStyle(.secondary)
                        .font(.footnote)
                        .textSelection(.enabled)
                }
            } header: {
                Text("Your Device")
            } footer: {
                Text("Auto-generated. Copy this into AHB_ALLOWED_DEVICES on your Mac.")
            }

            Section("Manual Override") {
                TextField("Your name or short ID", text: $config.userID)
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(.never)

                TextField("my-mac.tail12345.ts.net", text: $config.collectorHost)
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(.never)
                    .keyboardType(.URL)

                SecureField("Paste the token from your Mac", text: $config.ingestToken)
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(.never)
            }
        }
        .navigationTitle("Setup")
        .navigationBarTitleDisplayMode(.inline)
        .sheet(isPresented: $showScanner) {
            QRScannerSheet(isPresented: $showScanner) { code in
                if config.apply(qrPayload: code) {
                    scanError = nil
                } else {
                    scanError = "Unrecognised QR code. Use the code from /qr on your Mac."
                }
            }
        }
    }
}
