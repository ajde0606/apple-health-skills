import Foundation
import Combine
import BackgroundTasks

@MainActor
final class SyncCoordinator: ObservableObject {
    static let shared = SyncCoordinator()

    @Published var status: String = "Idle"
    @Published var lastResult: String = ""
    @Published var logs: [String] = []

    static let backgroundProcessingTaskID = "com.applehealthbridge.sync.processing"

    private let healthService = HealthKitSyncService()
    private let client = CollectorClient()
    private let queue = UploadQueue()

    private var observersConfigured = false

    func authorize() async {
        do {
            status = "Requesting Health permissions..."
            addLog("Requesting HealthKit authorization")
            try await healthService.requestAuthorization()
            try await configureBackgroundDeliveryIfNeeded()
            status = "Authorized"
            addLog("HealthKit authorized")
        } catch {
            status = "Authorization failed: \(error.localizedDescription)"
            addLog("Authorization failed: \(error.localizedDescription)")
        }
    }

    func startBackgroundSync() async {
        do {
            try await configureBackgroundDeliveryIfNeeded()
            scheduleBackgroundProcessing()
            addLog("Background sync setup complete")
        } catch {
            lastResult = "Background sync setup failed: \(error.localizedDescription)"
            addLog(lastResult)
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
            let modeName = modeName(for: mode)
            addLog("Starting \(modeName) sync")
            let samples: [AnySample]
            switch mode {
            case .bootstrap:
                samples = try await healthService.collectBootstrapSamples(days: config.bootstrapDays)
            case .incremental:
                samples = try await healthService.collectIncrementalSamples()
            }

            if samples.isEmpty {
                status = "No new samples"
                addLog("No new samples found")
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
                    addLog("Upload failed; queued batch \(payload.batchID)")
                }
            }

            try await flushQueue()
            scheduleBackgroundProcessing()
            status = "Sync complete"
            lastResult = "Uploaded \(samples.count) samples"
            addLog(lastResult)
        } catch {
            status = "Sync failed: \(error.localizedDescription)"
            addLog(status)
        }
    }

    func runIncrementalSyncInBackground() async {
        let config = AppConfig.shared
        do {
            addLog("Background incremental sync triggered")
            let samples = try await healthService.collectIncrementalSamples()
            guard !samples.isEmpty else {
                try await flushQueue()
                scheduleBackgroundProcessing()
                addLog("Background sync: no new samples")
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
                    addLog("Background upload failed; queued batch \(payload.batchID)")
                }
            }

            try await flushQueue()
            scheduleBackgroundProcessing()
            addLog("Background sync uploaded \(samples.count) samples")
        } catch {
            lastResult = "Background sync failed: \(error.localizedDescription)"
            addLog(lastResult)
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
            addLog("Scheduled BGProcessing task")
        } catch {
            lastResult = "Could not schedule background sync: \(error.localizedDescription)"
            addLog(lastResult)
        }
    }

    func handleBackgroundProcessingTask(_ task: BGProcessingTask) {
        scheduleBackgroundProcessing()
        addLog("BGProcessing task started")

        task.expirationHandler = {
            self.addLog("BGProcessing task expired")
            task.setTaskCompleted(success: false)
        }

        Task {
            await runIncrementalSyncInBackground()
            task.setTaskCompleted(success: true)
            addLog("BGProcessing task completed")
        }
    }

    private func configureBackgroundDeliveryIfNeeded() async throws {
        guard !observersConfigured else { return }
        try await healthService.enableBackgroundDelivery()
        healthService.startObserverQueries { [weak self] in
            await self?.runIncrementalSyncInBackground()
        }
        observersConfigured = true
        addLog("HealthKit observer queries configured")
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
            addLog("Queue flush failed for \(failed.count) batch(es)")
        } else if !queued.isEmpty {
            addLog("Flushed \(queued.count) queued batch(es)")
        }
    }

    private func addLog(_ message: String) {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let line = "[\(formatter.string(from: Date()))] \(message)"
        logs.insert(line, at: 0)
        if logs.count > 100 {
            logs.removeLast(logs.count - 100)
        }
    }
}

private func modeName(for mode: SyncMode) -> String {
    switch mode {
    case .bootstrap: return "bootstrap"
    case .incremental: return "incremental"
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
