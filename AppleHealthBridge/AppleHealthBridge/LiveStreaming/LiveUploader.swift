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
        let url = config.liveEventsURL

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue("Bearer \(config.ingestToken)", forHTTPHeaderField: "Authorization")
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
