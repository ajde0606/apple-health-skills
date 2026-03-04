import Foundation

struct QueuedBatch: Codable, Identifiable {
    let id: UUID
    let payload: IngestPayload
    let createdAt: Date
}

final class UploadQueue {
    private let fileURL: URL
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    init(fileManager: FileManager = .default) {
        let dir = fileManager.urls(for: .documentDirectory, in: .userDomainMask).first!
        fileURL = dir.appendingPathComponent("upload-queue.json")
    }

    func enqueue(_ payload: IngestPayload) {
        var queue = loadQueue()
        queue.append(QueuedBatch(id: UUID(), payload: payload, createdAt: Date()))
        persist(queue)
    }

    func popAll() -> [QueuedBatch] {
        let queue = loadQueue()
        persist([])
        return queue
    }

    func prepend(_ items: [QueuedBatch]) {
        let current = loadQueue()
        persist(items + current)
    }

    private func loadQueue() -> [QueuedBatch] {
        guard let data = try? Data(contentsOf: fileURL),
              let queue = try? decoder.decode([QueuedBatch].self, from: data) else {
            return []
        }
        return queue
    }

    private func persist(_ queue: [QueuedBatch]) {
        guard let data = try? encoder.encode(queue) else {
            return
        }
        try? data.write(to: fileURL, options: .atomic)
    }
}
