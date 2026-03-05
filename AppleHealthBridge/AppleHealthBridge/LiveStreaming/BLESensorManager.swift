import CoreBluetooth
import Foundation
import Combine

struct BLEDiscoveredDevice: Identifiable, Hashable {
    let id: UUID
    let name: String
    let peripheral: CBPeripheral
    let rssi: Int
}

@MainActor
final class BLESensorManager: NSObject, ObservableObject {
    @Published var discoveredDevices: [BLEDiscoveredDevice] = []
    @Published var connectedName: String = "Not connected"
    @Published var latestBPM: Int?

    private var central: CBCentralManager!
    private var connectedPeripheral: CBPeripheral?
    private var measurementCharacteristic: CBCharacteristic?
    private var lastRSSIByDevice: [UUID: Int] = [:]
    private var peripheralByID: [UUID: CBPeripheral] = [:]

    var onBPM: ((Int) -> Void)?

    private let hrService = CBUUID(string: "180D")
    private let hrMeasurement = CBUUID(string: "2A37")

    override init() {
        super.init()
        central = CBCentralManager(delegate: self, queue: nil)
    }

    func startScan() {
        guard central.state == .poweredOn else { return }
        central.scanForPeripherals(withServices: [hrService], options: [CBCentralManagerScanOptionAllowDuplicatesKey: true])
    }

    func stopScan() {
        central.stopScan()
    }

    func connect(_ device: BLEDiscoveredDevice) {
        connectedPeripheral = device.peripheral
        connectedPeripheral?.delegate = self
        central.connect(device.peripheral, options: nil)
    }

    func disconnect() {
        guard let peripheral = connectedPeripheral else { return }
        if let characteristic = measurementCharacteristic {
            peripheral.setNotifyValue(false, for: characteristic)
        }
        central.cancelPeripheralConnection(peripheral)
    }
}

extension BLESensorManager: CBCentralManagerDelegate {
    nonisolated func centralManagerDidUpdateState(_ central: CBCentralManager) {
        Task { @MainActor in
            if central.state == .poweredOn {
                startScan()
            } else {
                connectedName = "Bluetooth unavailable"
            }
        }
    }

    nonisolated func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral, advertisementData: [String : Any], rssi RSSI: NSNumber) {
        Task { @MainActor in
            let id = peripheral.identifier
            let name = peripheral.name ?? "Unknown HR Device"
            lastRSSIByDevice[id] = RSSI.intValue
            peripheralByID[id] = peripheral
            discoveredDevices = lastRSSIByDevice.map { key, value in
                BLEDiscoveredDevice(id: key, name: peripheralByID[key]?.name ?? name, peripheral: peripheralByID[key] ?? peripheral, rssi: value)
            }
            .sorted { $0.rssi > $1.rssi }
        }
    }

    nonisolated func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        peripheral.delegate = self
        peripheral.discoverServices([CBUUID(string: "180D")])
        Task { @MainActor in
            connectedName = peripheral.name ?? "Connected"
        }
    }

    nonisolated func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral, error: Error?) {
        Task { @MainActor in
            connectedName = "Disconnected"
            measurementCharacteristic = nil
        }
    }
}

extension BLESensorManager: CBPeripheralDelegate {
    nonisolated func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        guard error == nil else { return }
        peripheral.services?.forEach { service in
            if service.uuid == CBUUID(string: "180D") {
                peripheral.discoverCharacteristics([CBUUID(string: "2A37")], for: service)
            }
        }
    }

    nonisolated func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        guard error == nil else { return }
        guard let chars = service.characteristics else { return }
        for characteristic in chars where characteristic.uuid == CBUUID(string: "2A37") {
            peripheral.setNotifyValue(true, for: characteristic)
            Task { @MainActor in
                measurementCharacteristic = characteristic
            }
        }
    }

    nonisolated func peripheral(_ peripheral: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        guard error == nil, characteristic.uuid == CBUUID(string: "2A37"), let data = characteristic.value else { return }
        guard let bpm = HeartRateParser.parseBPM(from: data) else { return }
        Task { @MainActor in
            latestBPM = bpm
            onBPM?(bpm)
        }
    }
}
