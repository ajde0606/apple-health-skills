import Foundation

actor LiveUploader {
    private let session: URLSession
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    init(session: URLSession = .shared) {
        self.session = session
    }

    func upload(sessionID: String, deviceID: String, events: [LiveHREvent]) async throws -> Int {
        guard !events.isEmpty else { return 0 }

        let config = AppConfig.shared
        let primaryURL = config.liveEventsURL

        do {
            return try await upload(to: primaryURL, sessionID: sessionID, deviceID: deviceID, events: events, token: config.ingestToken)
        } catch {
            // Fallback once with the opposite scheme. This recovers from stale
            // local configuration where the collector switched HTTP<->HTTPS.
            guard let fallbackURL = swappedSchemeURL(from: primaryURL) else {
                throw error
            }
            let ack = try await upload(to: fallbackURL, sessionID: sessionID, deviceID: deviceID, events: events, token: config.ingestToken)
            if let appliedScheme = fallbackURL.scheme {
                await MainActor.run {
                    AppConfig.shared.collectorScheme = appliedScheme
                }
            }
            return ack
        }
    }

    private func swappedSchemeURL(from url: URL) -> URL? {
        guard var components = URLComponents(url: url, resolvingAgainstBaseURL: false),
              let scheme = components.scheme else { return nil }
        if scheme == "https" {
            components.scheme = "http"
        } else if scheme == "http" {
            components.scheme = "https"
        } else {
            return nil
        }
        return components.url
    }

    private func upload(
        to url: URL,
        sessionID: String,
        deviceID: String,
        events: [LiveHREvent],
        token: String
    ) async throws -> Int {

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.timeoutInterval = 15
        request.httpBody = try encoder.encode(LiveEventsPayload(session_id: sessionID, device_id: deviceID, events: events))

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        let parsed = try decoder.decode(LiveEventsResponse.self, from: data)
        return parsed.ack_seq
    }
}
