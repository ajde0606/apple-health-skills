import Foundation

struct LiveEventSource: Codable {
    let kind: String
    let vendor: String
    let device_id: String
    let device_name: String?
}

struct LiveHREvent: Codable {
    let type: String
    let ts: Double
    let value: Int
    let unit: String
    let source: LiveEventSource
    let session_id: String
    let seq: Int
}

struct LiveEventsPayload: Codable {
    let session_id: String
    let device_id: String
    let events: [LiveHREvent]
}

struct LiveEventsResponse: Codable {
    let ok: Bool
    let ack_seq: Int
}
