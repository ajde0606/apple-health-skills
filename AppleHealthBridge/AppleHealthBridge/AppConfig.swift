import Foundation

enum AppConfig {
    static let collectorURL = URL(string: "https://mac-collector.tailnet.example:8443")!
    static let ingestPath = "/ingest"
    static let ingestToken = "replace-me"
    static let deviceID = "dad-iphone"
    static let userID = "dad"
    static let bootstrapDays = 14
    static let maxBatchSamples = 500
}
