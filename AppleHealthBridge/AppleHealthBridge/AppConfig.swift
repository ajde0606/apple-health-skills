import Foundation

enum AppConfig {
    // Use your Mac's reachable collector host (MagicDNS or LAN IP), e.g. `my-mac.tailnet.ts.net`.
    // NSURLErrorDomain -1003 means iPhone DNS cannot resolve this hostname.
    static let collectorURL = URL(string: "https://YOUR-MAC-REACHABLE-HOST:8443")!
    static let ingestPath = "/ingest"
    static let ingestToken = "dev-token"
    static let deviceID = "dad-iphone"
    static let userID = "dad"
    static let bootstrapDays = 14
    static let maxBatchSamples = 500
}
