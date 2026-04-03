import HealthKit
import Foundation

/// HealthKit manager — anchor-based incremental sync to Clintela backend.
///
/// Uses HKAnchoredObjectQuery for reliable incremental sync:
///   - Tracks an anchor per data type
///   - Handles retroactive timestamp adjustments (Apple Watch backfill)
///   - Supports both foreground sync and background delivery
///
/// Synced data types:
///   - Heart Rate (HKQuantityTypeIdentifierHeartRate)
///   - Blood Pressure (systolic + diastolic)
///   - Body Weight
///   - SpO2
///   - Body Temperature
///   - Step Count
///   - Sleep Analysis
final class HealthKitManager: ObservableObject {
    static let shared = HealthKitManager()

    private let healthStore = HKHealthStore()
    private let defaults = UserDefaults(suiteName: "group.com.clintela.app") ?? .standard

    /// Data types we request read access for.
    private let readTypes: Set<HKObjectType> = {
        var types = Set<HKObjectType>()
        let quantityTypes: [HKQuantityTypeIdentifier] = [
            .heartRate,
            .bloodPressureSystolic,
            .bloodPressureDiastolic,
            .bodyMass,
            .oxygenSaturation,
            .bodyTemperature,
            .stepCount,
        ]
        for id in quantityTypes {
            if let type = HKQuantityType.quantityType(forIdentifier: id) {
                types.insert(type)
            }
        }
        if let sleepType = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) {
            types.insert(sleepType)
        }
        return types
    }()

    @Published var isAuthorized = false
    @Published var lastSyncDate: Date?

    // MARK: - Authorization

    /// Request HealthKit read authorization. Call from onboarding screen 3.
    func requestAuthorization() async -> Bool {
        guard HKHealthStore.isHealthDataAvailable() else {
            return false
        }

        do {
            try await healthStore.requestAuthorization(toShare: [], read: readTypes)
            await MainActor.run { isAuthorized = true }
            return true
        } catch {
            print("[HealthKit] Authorization failed: \(error)")
            return false
        }
    }

    // MARK: - Anchored Object Query (Incremental Sync)

    /// Perform incremental sync for all data types.
    /// Returns observations ready for the /api/v1/health/sync/ endpoint.
    func syncAllTypes() async -> [[String: Any]] {
        var allObservations: [[String: Any]] = []

        // Quantity types
        let quantityMappings: [(HKQuantityTypeIdentifier, String, HKUnit)] = [
            (.heartRate, "HKQuantityTypeIdentifierHeartRate", HKUnit.count().unitDivided(by: .minute())),
            (.bloodPressureSystolic, "HKQuantityTypeIdentifierBloodPressureSystolic", .millimeterOfMercury()),
            (.bloodPressureDiastolic, "HKQuantityTypeIdentifierBloodPressureDiastolic", .millimeterOfMercury()),
            (.bodyMass, "HKQuantityTypeIdentifierBodyMass", .pound()),
            (.oxygenSaturation, "HKQuantityTypeIdentifierOxygenSaturation", .percent()),
            (.bodyTemperature, "HKQuantityTypeIdentifierBodyTemperature", HKUnit.degreeFahrenheit()),
            (.stepCount, "HKQuantityTypeIdentifierStepCount", .count()),
        ]

        for (typeId, typeString, unit) in quantityMappings {
            guard let quantityType = HKQuantityType.quantityType(forIdentifier: typeId) else { continue }
            let observations = await queryWithAnchor(type: quantityType, typeString: typeString, unit: unit)
            allObservations.append(contentsOf: observations)
        }

        // Sleep analysis (category type, handled separately)
        if let sleepType = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) {
            let observations = await querySleepWithAnchor(type: sleepType)
            allObservations.append(contentsOf: observations)
        }

        if !allObservations.isEmpty {
            await MainActor.run { lastSyncDate = Date() }
        }

        return allObservations
    }

    // MARK: - Anchor-Based Query

    /// Query new/updated samples since the last anchor for a quantity type.
    private func queryWithAnchor(
        type: HKQuantityType,
        typeString: String,
        unit: HKUnit
    ) async -> [[String: Any]] {
        let anchorKey = "healthkit_anchor_\(type.identifier)"
        let storedAnchorData = defaults.data(forKey: anchorKey)
        let anchor: HKQueryAnchor? = storedAnchorData.flatMap {
            try? NSKeyedUnarchiver.unarchivedObject(ofClass: HKQueryAnchor.self, from: $0)
        }

        return await withCheckedContinuation { continuation in
            let query = HKAnchoredObjectQuery(
                type: type,
                predicate: nil,
                anchor: anchor,
                limit: HKObjectQueryNoLimit
            ) { _, addedSamples, _, newAnchor, error in
                guard error == nil, let samples = addedSamples as? [HKQuantitySample] else {
                    continuation.resume(returning: [])
                    return
                }

                // Persist the new anchor
                if let newAnchor = newAnchor,
                   let data = try? NSKeyedArchiver.archivedData(withRootObject: newAnchor, requiringSecureCoding: true) {
                    self.defaults.set(data, forKey: anchorKey)
                }

                // Map to observation dicts
                let observations = samples.map { sample -> [String: Any] in
                    [
                        "concept_id": self.conceptId(for: typeString),
                        "value_numeric": sample.quantity.doubleValue(for: unit),
                        "value_text": "",
                        "unit": unit.unitString,
                        "observed_at": ISO8601DateFormatter().string(from: sample.startDate),
                        "source_device": sample.sourceRevision.source.name,
                        "metadata": sample.metadata ?? [:],
                    ]
                }

                continuation.resume(returning: observations)
            }

            healthStore.execute(query)
        }
    }

    /// Query sleep analysis samples with anchor.
    private func querySleepWithAnchor(type: HKCategoryType) async -> [[String: Any]] {
        let anchorKey = "healthkit_anchor_\(type.identifier)"
        let storedAnchorData = defaults.data(forKey: anchorKey)
        let anchor: HKQueryAnchor? = storedAnchorData.flatMap {
            try? NSKeyedUnarchiver.unarchivedObject(ofClass: HKQueryAnchor.self, from: $0)
        }

        return await withCheckedContinuation { continuation in
            let query = HKAnchoredObjectQuery(
                type: type,
                predicate: nil,
                anchor: anchor,
                limit: HKObjectQueryNoLimit
            ) { _, addedSamples, _, newAnchor, error in
                guard error == nil, let samples = addedSamples as? [HKCategorySample] else {
                    continuation.resume(returning: [])
                    return
                }

                if let newAnchor = newAnchor,
                   let data = try? NSKeyedArchiver.archivedData(withRootObject: newAnchor, requiringSecureCoding: true) {
                    self.defaults.set(data, forKey: anchorKey)
                }

                // Convert sleep samples to hours
                let observations = samples.compactMap { sample -> [String: Any]? in
                    let duration = sample.endDate.timeIntervalSince(sample.startDate) / 3600.0
                    guard duration > 0 else { return nil }
                    return [
                        "concept_id": 40762503, // CONCEPT_SLEEP_DURATION
                        "value_numeric": duration,
                        "value_text": "",
                        "unit": "hours",
                        "observed_at": ISO8601DateFormatter().string(from: sample.startDate),
                        "source_device": sample.sourceRevision.source.name,
                        "metadata": ["sleep_value": sample.value],
                    ]
                }

                continuation.resume(returning: observations)
            }

            healthStore.execute(query)
        }
    }

    // MARK: - OMOP Concept ID Mapping

    /// Map HealthKit type string to OMOP concept ID.
    /// Must match apps/clinical/constants.py.
    private func conceptId(for typeString: String) -> Int {
        let mapping: [String: Int] = [
            "HKQuantityTypeIdentifierHeartRate": 3027018,
            "HKQuantityTypeIdentifierBloodPressureSystolic": 3004249,
            "HKQuantityTypeIdentifierBloodPressureDiastolic": 3012888,
            "HKQuantityTypeIdentifierBodyMass": 3025315,
            "HKQuantityTypeIdentifierOxygenSaturation": 3016502,
            "HKQuantityTypeIdentifierBodyTemperature": 3020891,
            "HKQuantityTypeIdentifierStepCount": 40762499,
        ]
        return mapping[typeString] ?? 0
    }

    // MARK: - Background Delivery

    /// Enable background delivery for key data types.
    /// Called after authorization to receive updates even when app is not in foreground.
    func enableBackgroundDelivery() {
        let backgroundTypes: [HKQuantityTypeIdentifier] = [
            .heartRate, .stepCount, .bodyMass, .oxygenSaturation,
        ]

        for typeId in backgroundTypes {
            guard let type = HKQuantityType.quantityType(forIdentifier: typeId) else { continue }
            healthStore.enableBackgroundDelivery(for: type, frequency: .hourly) { success, error in
                if let error = error {
                    print("[HealthKit] Background delivery failed for \(typeId.rawValue): \(error)")
                } else if success {
                    print("[HealthKit] Background delivery enabled for \(typeId.rawValue)")
                }
            }
        }
    }
}
