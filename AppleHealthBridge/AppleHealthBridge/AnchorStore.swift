import Foundation
import HealthKit

final class AnchorStore {
    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    func anchor(for key: String) -> HKQueryAnchor? {
        guard let data = defaults.data(forKey: key) else {
            return nil
        }
        return try? NSKeyedUnarchiver.unarchivedObject(ofClass: HKQueryAnchor.self, from: data)
    }

    func save(anchor: HKQueryAnchor?, for key: String) {
        guard let anchor else {
            defaults.removeObject(forKey: key)
            return
        }
        if let data = try? NSKeyedArchiver.archivedData(withRootObject: anchor, requiringSecureCoding: true) {
            defaults.set(data, forKey: key)
        }
    }
}
