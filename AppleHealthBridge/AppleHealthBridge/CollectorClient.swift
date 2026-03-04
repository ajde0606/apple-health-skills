import Foundation

final class CollectorClient {
    private let session: URLSession
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    init(session: URLSession = .shared) {
        self.session = session
    }

    func upload(payload: IngestPayload) async throws -> IngestResponse {
        let config = AppConfig.shared
        var request = URLRequest(url: config.ingestURL)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue(config.ingestToken, forHTTPHeaderField: "X-Ingest-Token")
        request.timeoutInterval = 30
        request.httpBody = try encoder.encode(payload)

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }

        return try decoder.decode(IngestResponse.self, from: data)
    }
}
