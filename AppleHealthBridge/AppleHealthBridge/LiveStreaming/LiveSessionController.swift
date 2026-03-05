import Foundation
import Combine

@MainActor
final class LiveSessionController: ObservableObject {
    @Published var isRunning = false
    @Published var status = "Idle"
    @Published var bufferSize = 0
    @Published var lastAckSeq = 0

    let ble = BLESensorManager()
    private let uploader = LiveUploader()

    private var sessionID = UUID().uuidString
    private var seq = 0
    private var buffer: [LiveHREvent] = []
    private var flushTask: Task<Void, Never>?
    private var backoffNs: UInt64 = 500_000_000
    private var bleCancellable: AnyCancellable?

    init() {
        ble.onBPM = { [weak self] bpm in
            self?.handle(bpm: bpm)
        }
        // Forward BLE published-property changes so SwiftUI views that observe
        // this controller re-render whenever ble.discoveredDevices,
        // connectedName, or latestBPM change.
        bleCancellable = ble.objectWillChange
            .receive(on: RunLoop.main)
            .sink { [weak self] _ in self?.objectWillChange.send() }
    }

    func startSession() {
        sessionID = UUID().uuidString
        seq = 0
        buffer.removeAll()
        bufferSize = 0
        lastAckSeq = 0
        isRunning = true
        status = "Live session started"

        flushTask?.cancel()
        flushTask = Task { [weak self] in
            await self?.flushLoop()
        }
    }

    func stopSession() {
        isRunning = false
        flushTask?.cancel()
        flushTask = nil
        status = "Session stopped"
    }

    private func handle(bpm: Int) {
        guard isRunning else { return }
        seq += 1
        let event = LiveHREvent(
            type: "hr",
            ts: Date().timeIntervalSince1970,
            value: bpm,
            unit: "bpm",
            source: LiveEventSource(
                kind: "ble",
                vendor: "wahoo",
                device_id: AppConfig.shared.deviceID,
                device_name: ble.connectedName
            ),
            session_id: sessionID,
            seq: seq
        )
        buffer.append(event)
        if buffer.count > 300 {
            buffer.removeFirst(buffer.count - 300)
        }
        bufferSize = buffer.count
    }

    private func flushLoop() async {
        while !Task.isCancelled {
            do {
                try await Task.sleep(nanoseconds: 1_000_000_000)
                try await flushOnce()
            } catch {
                status = "Upload retrying"
            }
        }
    }

    private func flushOnce() async throws {
        guard isRunning, !buffer.isEmpty else { return }
        let batch = Array(buffer.prefix(10))
        do {
            let ackSeq = try await uploader.upload(sessionID: sessionID, deviceID: AppConfig.shared.deviceID, events: batch)
            trimBuffer(ackSeq: ackSeq)
            lastAckSeq = ackSeq
            backoffNs = 500_000_000
            status = "Streaming"
        } catch {
            try await Task.sleep(nanoseconds: backoffNs)
            backoffNs = min(backoffNs * 2, 10_000_000_000)
            throw error
        }
    }

    private func trimBuffer(ackSeq: Int) {
        buffer.removeAll { $0.seq <= ackSeq }
        bufferSize = buffer.count
    }
}
