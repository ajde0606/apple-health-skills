import CryptoKit
import Foundation
import HealthKit

final class HealthKitSyncService {
    private let healthStore = HKHealthStore()
    private let anchorStore = AnchorStore()
    private var observerQueries: [HKObserverQuery] = []

    private var quantityTypes: [HKQuantityTypeIdentifier] {
        [.heartRate, .bloodGlucose]
    }

    private var monitoredSampleTypes: [HKSampleType] {
        let quantities = quantityTypes.compactMap { HKObjectType.quantityType(forIdentifier: $0) }
        let sleep = HKObjectType.categoryType(forIdentifier: .sleepAnalysis).map { [$0 as HKSampleType] } ?? []
        return quantities + sleep
    }

    func requestAuthorization() async throws {
        let readTypes: Set<HKObjectType> = Set(
            quantityTypes.compactMap { HKQuantityType.quantityType(forIdentifier: $0) } +
            [HKObjectType.categoryType(forIdentifier: .sleepAnalysis)!]
        )

        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            healthStore.requestAuthorization(toShare: [], read: readTypes) { success, error in
                if let error {
                    continuation.resume(throwing: error)
                } else if success {
                    continuation.resume(returning: ())
                } else {
                    continuation.resume(throwing: URLError(.userAuthenticationRequired))
                }
            }
        }
    }

    func collectBootstrapSamples(days: Int) async throws -> [AnySample] {
        let startDate = Calendar.current.date(byAdding: .day, value: -days, to: Date())!
        return try await collectSamples(since: startDate, useAnchors: false)
    }

    func collectIncrementalSamples() async throws -> [AnySample] {
        return try await collectSamples(since: nil, useAnchors: true)
    }

    func enableBackgroundDelivery() async throws {
        for sampleType in monitoredSampleTypes {
            try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
                healthStore.enableBackgroundDelivery(for: sampleType, frequency: .immediate) { success, error in
                    if let error {
                        continuation.resume(throwing: error)
                    } else if success {
                        continuation.resume(returning: ())
                    } else {
                        continuation.resume(throwing: URLError(.cannotLoadFromNetwork))
                    }
                }
            }
        }
    }

    func startObserverQueries(onUpdate: @escaping () async -> Void) {
        stopObserverQueries()

        for sampleType in monitoredSampleTypes {
            let query = HKObserverQuery(sampleType: sampleType, predicate: nil) { _, completionHandler, _ in
                Task {
                    await onUpdate()
                }
                completionHandler()
            }

            observerQueries.append(query)
            healthStore.execute(query)
        }
    }

    func stopObserverQueries() {
        observerQueries.forEach { healthStore.stop($0) }
        observerQueries.removeAll()
    }

    private func collectSamples(since startDate: Date?, useAnchors: Bool) async throws -> [AnySample] {
        var output: [AnySample] = []

        for id in quantityTypes {
            guard let quantityType = HKQuantityType.quantityType(forIdentifier: id) else { continue }
            let (samples, anchor) = try await runAnchoredQuery(type: quantityType, key: id.rawValue, startDate: startDate, useAnchor: useAnchors)
            output += samples
            anchorStore.save(anchor: anchor, for: id.rawValue)
        }

        if let sleepType = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) {
            let (samples, anchor) = try await runAnchoredCategoryQuery(type: sleepType, key: HKCategoryTypeIdentifier.sleepAnalysis.rawValue, startDate: startDate, useAnchor: useAnchors)
            output += samples
            anchorStore.save(anchor: anchor, for: HKCategoryTypeIdentifier.sleepAnalysis.rawValue)
        }

        return output
    }

    private func runAnchoredQuery(
        type: HKQuantityType,
        key: String,
        startDate: Date?,
        useAnchor: Bool
    ) async throws -> ([AnySample], HKQueryAnchor?) {
        let predicate = startDate.map { HKQuery.predicateForSamples(withStart: $0, end: nil, options: .strictStartDate) }
        let anchor = useAnchor ? anchorStore.anchor(for: key) : nil

        return try await withCheckedThrowingContinuation { continuation in
            let query = HKAnchoredObjectQuery(type: type, predicate: predicate, anchor: anchor, limit: HKObjectQueryNoLimit) { _, samples, _, newAnchor, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }

                let mapped: [AnySample] = (samples as? [HKQuantitySample] ?? []).map { sample in
                    let value = self.quantityValue(sample: sample, identifier: type.identifier)
                    let model = QuantitySample(
                        sampleID: self.sampleID(type: type.identifier, ts: Int(sample.startDate.timeIntervalSince1970), value: value, source: sample.sourceRevision.source.name),
                        kind: "quantity",
                        type: self.metricName(for: type.identifier),
                        ts: Int(sample.startDate.timeIntervalSince1970),
                        value: value,
                        unit: self.metricUnit(for: type.identifier),
                        source: sample.sourceRevision.source.name,
                        device: sample.device?.name,
                        metadata: nil
                    )
                    return .quantity(model)
                }

                continuation.resume(returning: (mapped, newAnchor))
            }

            self.healthStore.execute(query)
        }
    }

    private func runAnchoredCategoryQuery(
        type: HKCategoryType,
        key: String,
        startDate: Date?,
        useAnchor: Bool
    ) async throws -> ([AnySample], HKQueryAnchor?) {
        let predicate = startDate.map { HKQuery.predicateForSamples(withStart: $0, end: nil, options: .strictStartDate) }
        let anchor = useAnchor ? anchorStore.anchor(for: key) : nil

        return try await withCheckedThrowingContinuation { continuation in
            let query = HKAnchoredObjectQuery(type: type, predicate: predicate, anchor: anchor, limit: HKObjectQueryNoLimit) { _, samples, _, newAnchor, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }

                let mapped: [AnySample] = (samples as? [HKCategorySample] ?? []).map { sample in
                    let model = CategorySample(
                        sampleID: self.sampleID(type: "sleep_stage", ts: Int(sample.startDate.timeIntervalSince1970), value: Double(sample.value), source: sample.sourceRevision.source.name),
                        kind: "category",
                        type: "sleep_stage",
                        startTs: Int(sample.startDate.timeIntervalSince1970),
                        endTs: Int(sample.endDate.timeIntervalSince1970),
                        category: String(sample.value),
                        source: sample.sourceRevision.source.name,
                        device: sample.device?.name,
                        metadata: nil
                    )
                    return .category(model)
                }

                continuation.resume(returning: (mapped, newAnchor))
            }

            self.healthStore.execute(query)
        }
    }

    private func quantityValue(sample: HKQuantitySample, identifier: String) -> Double {
        switch identifier {
        case HKQuantityTypeIdentifier.heartRate.rawValue:
            return sample.quantity.doubleValue(for: HKUnit.count().unitDivided(by: .minute()))
        case HKQuantityTypeIdentifier.bloodGlucose.rawValue:
            return sample.quantity.doubleValue(for: HKUnit(from: "mg/dL"))
        default:
            return sample.quantity.doubleValue(for: .count())
        }
    }

    private func metricUnit(for identifier: String) -> String {
        switch identifier {
        case HKQuantityTypeIdentifier.heartRate.rawValue: return "bpm"
        case HKQuantityTypeIdentifier.bloodGlucose.rawValue: return "mg_dL"
        default: return "count"
        }
    }

    private func metricName(for identifier: String) -> String {
        switch identifier {
        case HKQuantityTypeIdentifier.heartRate.rawValue: return "heart_rate"
        case HKQuantityTypeIdentifier.bloodGlucose.rawValue: return "glucose"
        default: return identifier
        }
    }

    private func sampleID(type: String, ts: Int, value: Double, source: String) -> String {
        let raw = "\(type)|\(ts)|\(value)|\(source)"
        let digest = SHA256.hash(data: Data(raw.utf8))
        return digest.map { String(format: "%02x", $0) }.joined()
    }
}
