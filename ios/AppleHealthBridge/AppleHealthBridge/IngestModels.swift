import Foundation

struct IngestPayload: Codable {
    let batchID: String
    let deviceID: String
    let userID: String
    let sentAt: Int
    let samples: [AnySample]

    enum CodingKeys: String, CodingKey {
        case batchID = "batch_id"
        case deviceID = "device_id"
        case userID = "user_id"
        case sentAt = "sent_at"
        case samples
    }
}

struct IngestResponse: Codable {
    let ok: Bool
    let duplicateBatch: Bool
    let inserted: Int
    let skipped: Int

    enum CodingKeys: String, CodingKey {
        case ok
        case duplicateBatch = "duplicate_batch"
        case inserted
        case skipped
    }
}

struct QuantitySample: Codable {
    let sampleID: String
    let kind: String
    let type: String
    let ts: Int
    let value: Double
    let unit: String
    let source: String
    let device: String?
    let metadata: [String: String]?

    enum CodingKeys: String, CodingKey {
        case sampleID = "sample_id"
        case kind, type, ts, value, unit, source, device, metadata
    }
}

struct CategorySample: Codable {
    let sampleID: String
    let kind: String
    let type: String
    let startTs: Int
    let endTs: Int
    let category: String
    let source: String
    let device: String?
    let metadata: [String: String]?

    enum CodingKeys: String, CodingKey {
        case sampleID = "sample_id"
        case kind, type, category, source, device, metadata
        case startTs = "start_ts"
        case endTs = "end_ts"
    }
}

enum AnySample: Codable {
    case quantity(QuantitySample)
    case category(CategorySample)

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let quantity = try? container.decode(QuantitySample.self) {
            self = .quantity(quantity)
        } else {
            self = .category(try container.decode(CategorySample.self))
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .quantity(let sample):
            try container.encode(sample)
        case .category(let sample):
            try container.encode(sample)
        }
    }
}
