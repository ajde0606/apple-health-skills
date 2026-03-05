import SwiftUI

struct LiveView: View {
    @StateObject private var controller = LiveSessionController()

    var body: some View {
        List {
            Section("Connection") {
                Text("Status: \(controller.ble.connectedName)")
                Text("Latest BPM: \(controller.ble.latestBPM.map(String.init) ?? "--")")
            }

            Section("Discovered Devices") {
                Button("Scan") {
                    controller.ble.startScan()
                }
                ForEach(controller.ble.discoveredDevices) { device in
                    Button("\(device.name) (RSSI \(device.rssi))") {
                        controller.ble.connect(device)
                    }
                }
            }

            Section("Live Session") {
                Text("Session state: \(controller.status)")
                Text("Buffered events: \(controller.bufferSize)")
                Text("Last ack seq: \(controller.lastAckSeq)")

                Button(controller.isRunning ? "Stop Live Session" : "Start Live Session") {
                    controller.isRunning ? controller.stopSession() : controller.startSession()
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .navigationTitle("Live HR")
    }
}
