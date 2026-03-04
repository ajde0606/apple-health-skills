import Foundation
import Combine

@MainActor
final class SyncCoordinator: ObservableObject {
    @Published var status: String = "Idle"
    @Published var lastResult: String = ""

    private let healthService = HealthKitSyncService()
    private let client = CollectorClient()
    private let queue = UploadQueue()

    func authorize() async {
        do {
            status = "Requesting Health permissions..."
            try await healthService.requestAuthorization()
            status = "Authorized"
        } catch {
            status = "Authorization failed: \(error.localizedDescription)"
        }
    }

    func bootstrapSync() async {
        await sync(mode: .bootstrap)
    }

    func incrementalSync() async {
        await sync(mode: .incremental)
    }

    private func sync(mode: SyncMode) async {
        do {
            status = "Collecting samples..."
            let samples: [AnySample]
            switch mode {
            case .bootstrap:
                samples = try await healthService.collectBootstrapSamples(days: AppConfig.bootstrapDays)
            case .incremental:
                samples = try await healthService.collectIncrementalSamples()
            }

            if samples.isEmpty {
                status = "No new samples"
                return
            }

            let chunks = samples.chunked(into: AppConfig.maxBatchSamples)
            for chunk in chunks {
                let payload = IngestPayload(
                    batchID: UUID().uuidString,
                    deviceID: AppConfig.deviceID,
                    userID: AppConfig.userID,
                    sentAt: Int(Date().timeIntervalSince1970),
                    samples: chunk
                )

                do {
                    _ = try await client.upload(payload: payload)
                } catch {
                    queue.enqueue(payload)
                }
            }

            try await flushQueue()
            status = "Sync complete"
            lastResult = "Uploaded \(samples.count) samples"
        } catch {
            status = "Sync failed: \(error.localizedDescription)"
        }
    }

    private func flushQueue() async throws {
        let queued = queue.popAll()
        var failed: [QueuedBatch] = []

        for item in queued {
            do {
                _ = try await client.upload(payload: item.payload)
            } catch {
                failed.append(item)
            }
        }

        if !failed.isEmpty {
            queue.prepend(failed)
        }
    }
}

private enum SyncMode {
    case bootstrap
    case incremental
}

private extension Array {
    func chunked(into size: Int) -> [[Element]] {
        guard size > 0 else { return [self] }
        return stride(from: 0, to: count, by: size).map {
            Array(self[$0 ..< Swift.min($0 + size, count)])
        }
    }
}
