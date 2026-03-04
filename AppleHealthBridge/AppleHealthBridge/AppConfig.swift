import Foundation

enum AppConfig {
    // Replace with your Mac MagicDNS name (for example: `my-mac.tailnet.ts.net`).
    // If `tailscale` CLI is unavailable, open the Tailscale app/admin console and copy this device's DNS name.
    static let collectorURL = URL(string: "https://janices-macbook-air.tailcc4114.ts.net:8443")!
    static let ingestPath = "/ingest"
    static let ingestToken = "dev-token"
    static let deviceID = "dad-iphone"
    static let userID = "dad"
    static let bootstrapDays = 14
    static let maxBatchSamples = 500
}
