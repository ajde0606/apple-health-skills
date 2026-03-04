import Foundation
import Combine
import BackgroundTasks

@MainActor
final class SyncCoordinator: ObservableObject {
    static let shared = SyncCoordinator()

    @Published var status: String = "Idle"
    @Published var lastResult: String = ""

    static let backgroundProcessingTaskID = "com.applehealthbridge.sync.processing"

    private let healthService = HealthKitSyncService()
    private let client = CollectorClient()
    private let queue = UploadQueue()

    private var observersConfigured = false

    func authorize() async {
        do {
            status = "Requesting Health permissions..."
            try await healthService.requestAuthorization()
            try await configureBackgroundDeliveryIfNeeded()
            status = "Authorized"
        } catch {
            status = "Authorization failed: \(error.localizedDescription)"
        }
    }

    func startBackgroundSync() async {
        do {
            try await configureBackgroundDeliveryIfNeeded()
            scheduleBackgroundProcessing()
        } catch {
            lastResult = "Background sync setup failed: \(error.localizedDescription)"
        }
    }

    func bootstrapSync() async {
        await sync(mode: .bootstrap)
    }

    func incrementalSync() async {
        await sync(mode: .incremental)
    }

    private func sync(mode: SyncMode) async {
        let config = AppConfig.shared
        do {
            status = "Collecting samples..."
            let samples: [AnySample]
            switch mode {
            case .bootstrap:
                samples = try await healthService.collectBootstrapSamples(days: config.bootstrapDays)
            case .incremental:
                samples = try await healthService.collectIncrementalSamples()
            }

            if samples.isEmpty {
                status = "No new samples"
                return
            }

            let chunks = samples.chunked(into: config.maxBatchSamples)
            for chunk in chunks {
                let payload = IngestPayload(
                    batchID: UUID().uuidString,
                    deviceID: config.deviceID,
                    userID: config.userID,
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
            scheduleBackgroundProcessing()
            status = "Sync complete"
            lastResult = "Uploaded \(samples.count) samples"
        } catch {
            status = "Sync failed: \(error.localizedDescription)"
        }
    }

    func runIncrementalSyncInBackground() async {
        let config = AppConfig.shared
        do {
            let samples = try await healthService.collectIncrementalSamples()
            guard !samples.isEmpty else {
                try await flushQueue()
                scheduleBackgroundProcessing()
                return
            }

            let chunks = samples.chunked(into: config.maxBatchSamples)
            for chunk in chunks {
                let payload = IngestPayload(
                    batchID: UUID().uuidString,
                    deviceID: config.deviceID,
                    userID: config.userID,
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
            scheduleBackgroundProcessing()
        } catch {
            lastResult = "Background sync failed: \(error.localizedDescription)"
        }
    }

    func scheduleBackgroundProcessing() {
        BGTaskScheduler.shared.cancel(taskRequestWithIdentifier: Self.backgroundProcessingTaskID)

        let request = BGProcessingTaskRequest(identifier: Self.backgroundProcessingTaskID)
        request.requiresNetworkConnectivity = true
        request.requiresExternalPower = false
        request.earliestBeginDate = Date(timeIntervalSinceNow: 15 * 60)

        do {
            try BGTaskScheduler.shared.submit(request)
        } catch {
            lastResult = "Could not schedule background sync: \(error.localizedDescription)"
        }
    }

    func handleBackgroundProcessingTask(_ task: BGProcessingTask) {
        scheduleBackgroundProcessing()

        task.expirationHandler = {
            task.setTaskCompleted(success: false)
        }

        Task {
            await runIncrementalSyncInBackground()
            task.setTaskCompleted(success: true)
        }
    }

    private func configureBackgroundDeliveryIfNeeded() async throws {
        guard !observersConfigured else { return }
        try await healthService.enableBackgroundDelivery()
        healthService.startObserverQueries { [weak self] in
            await self?.runIncrementalSyncInBackground()
        }
        observersConfigured = true
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
