import Foundation

enum HeartRateParser {
    static func parseBPM(from data: Data) -> Int? {
        guard data.count >= 2 else { return nil }
        let flags = data[0]
        let isUInt16 = (flags & 0x01) == 0x01
        if isUInt16 {
            guard data.count >= 3 else { return nil }
            let low = UInt16(data[1])
            let high = UInt16(data[2]) << 8
            return Int(high | low)
        }
        return Int(data[1])
    }
}
