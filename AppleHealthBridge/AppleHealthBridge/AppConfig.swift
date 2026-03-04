import Combine
import Foundation

/// User-configurable settings, persisted in UserDefaults.
/// Any user can set their own collector host, token, name, and device nickname.
final class AppConfig: ObservableObject {
    static let shared = AppConfig()

    private enum Keys {
        static let collectorHost = "collectorHost"
        static let ingestToken   = "ingestToken"
        static let deviceID      = "deviceID"
        static let userID        = "userID"
    }

    // MARK: - Published settings (bound to SettingsView)

    @Published var collectorHost: String {
        didSet { UserDefaults.standard.set(collectorHost, forKey: Keys.collectorHost) }
    }

    @Published var ingestToken: String {
        didSet { UserDefaults.standard.set(ingestToken, forKey: Keys.ingestToken) }
    }

    /// Stable device nickname, e.g. "alice-iphone". Auto-generated on first launch.
    @Published var deviceID: String {
        didSet { UserDefaults.standard.set(deviceID, forKey: Keys.deviceID) }
    }

    /// Short identifier for the user, e.g. "alice". Used to namespace DB rows.
    @Published var userID: String {
        didSet { UserDefaults.standard.set(userID, forKey: Keys.userID) }
    }

    // MARK: - Fixed constants

    let bootstrapDays = 14
    let maxBatchSamples = 500

    // MARK: - Derived helpers

    /// True once the user has filled in all required fields.
    var isConfigured: Bool {
        !collectorHost.trimmingCharacters(in: .whitespaces).isEmpty &&
        !ingestToken.trimmingCharacters(in: .whitespaces).isEmpty &&
        !deviceID.trimmingCharacters(in: .whitespaces).isEmpty &&
        !userID.trimmingCharacters(in: .whitespaces).isEmpty
    }

    /// Builds the full ingest URL from the collector host field.
    /// Accepts bare hostnames ("my-mac.tailXXX.ts.net"),
    /// host:port ("my-mac.tailXXX.ts.net:8443"), or full URLs.
    var ingestURL: URL {
        var raw = collectorHost.trimmingCharacters(in: .whitespaces)
        if !raw.hasPrefix("http://") && !raw.hasPrefix("https://") {
            raw = "http://\(raw)"
        }
        if !raw.contains(":8443") && !raw.hasSuffix("/") {
            // Default port if user omits it
            raw += ":8443"
        }
        return URL(string: raw + "/ingest")!
    }

    // MARK: - Init

    private init() {
        let defaults = UserDefaults.standard
        collectorHost = defaults.string(forKey: Keys.collectorHost) ?? ""
        ingestToken   = defaults.string(forKey: Keys.ingestToken)   ?? ""
        userID        = defaults.string(forKey: Keys.userID)        ?? ""
        // Auto-generate a stable device ID on first launch
        if let saved = defaults.string(forKey: Keys.deviceID), !saved.isEmpty {
            deviceID = saved
        } else {
            let generated = "iphone-\(UUID().uuidString.prefix(8).lowercased())"
            defaults.set(generated, forKey: Keys.deviceID)
            deviceID = generated
        }
    }
}
