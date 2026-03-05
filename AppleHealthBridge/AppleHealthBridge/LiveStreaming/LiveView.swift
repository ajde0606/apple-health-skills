import SwiftUI

struct LiveView: View {
    @StateObject private var controller = LiveSessionController()

    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                bpmCard
                sensorCard
                sessionCard
            }
            .padding()
        }
        .navigationTitle("Live Heart Rate")
        .background(Color(.systemGroupedBackground))
    }

    // MARK: - BPM Display

    private var bpmCard: some View {
        VStack(spacing: 6) {
            Image(systemName: "heart.fill")
                .font(.title)
                .foregroundStyle(bpmColor)

            Text(controller.ble.latestBPM.map(String.init) ?? "--")
                .font(.system(size: 88, weight: .bold, design: .rounded))
                .foregroundStyle(bpmColor)
                .contentTransition(.numericText())
                .animation(.easeInOut(duration: 0.2), value: controller.ble.latestBPM)

            Text("BPM")
                .font(.title3)
                .foregroundStyle(.secondary)

            if let bpm = controller.ble.latestBPM {
                Text(hrZoneLabel(bpm: bpm))
                    .font(.caption)
                    .fontWeight(.medium)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 4)
                    .background(bpmColor.opacity(0.15))
                    .foregroundStyle(bpmColor)
                    .clipShape(Capsule())
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 28)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 20))
    }

    private var bpmColor: Color {
        guard let bpm = controller.ble.latestBPM else { return .secondary }
        switch bpm {
        case ..<60:  return .blue
        case 60..<100: return .green
        case 100..<140: return .orange
        default:     return .red
        }
    }

    private func hrZoneLabel(bpm: Int) -> String {
        switch bpm {
        case ..<60:  return "Resting"
        case 60..<100: return "Normal"
        case 100..<140: return "Elevated"
        default:     return "High"
        }
    }

    // MARK: - Sensor Card

    private var sensorCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("Sensor", systemImage: "sensor.tag.radiowaves.forward.fill")
                .font(.headline)

            if isConnected {
                HStack(spacing: 10) {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                        .font(.title3)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(controller.ble.connectedName)
                            .fontWeight(.medium)
                        Text("Connected")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button("Disconnect") {
                        controller.ble.disconnect()
                    }
                    .font(.caption)
                    .foregroundStyle(.red)
                }
                .padding(12)
                .background(Color.green.opacity(0.08))
                .clipShape(RoundedRectangle(cornerRadius: 12))
            } else {
                Button {
                    controller.ble.startScan()
                } label: {
                    Label("Scan for Sensors", systemImage: "antenna.radiowaves.left.and.right")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)

                if !controller.ble.discoveredDevices.isEmpty {
                    Divider()
                    Text("Nearby devices")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    ForEach(controller.ble.discoveredDevices) { device in
                        Button {
                            controller.ble.connect(device)
                        } label: {
                            HStack {
                                Image(systemName: "sensor.tag.radiowaves.forward.fill")
                                    .foregroundStyle(.blue)
                                Text(device.name)
                                    .foregroundStyle(.primary)
                                Spacer()
                                SignalBars(rssi: device.rssi)
                            }
                            .padding(.vertical, 6)
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
        }
        .padding()
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16))
    }

    private var isConnected: Bool {
        let name = controller.ble.connectedName
        return !name.isEmpty && name != "Not connected" && name != "Disconnected" && name != "Bluetooth unavailable"
    }

    // MARK: - Session Card

    private var sessionCard: some View {
        VStack(spacing: 14) {
            Button {
                controller.isRunning ? controller.stopSession() : controller.startSession()
            } label: {
                Label(
                    controller.isRunning ? "Stop Session" : "Start Session",
                    systemImage: controller.isRunning ? "stop.circle.fill" : "play.circle.fill"
                )
                .font(.headline)
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(controller.isRunning ? .red : .blue)
            .disabled(!isConnected && !controller.isRunning)

            if controller.isRunning || controller.status != "Idle" {
                Divider()

                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 4) {
                        Label(sessionStatusLabel, systemImage: sessionStatusIcon)
                            .font(.subheadline)
                            .foregroundStyle(sessionStatusColor)
                    }
                    Spacer()
                    if controller.bufferSize > 0 {
                        VStack(alignment: .trailing, spacing: 2) {
                            Text("\(controller.bufferSize)")
                                .font(.headline)
                                .foregroundStyle(.orange)
                            Text("pending")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }
        .padding()
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16))
    }

    private var sessionStatusLabel: String {
        switch controller.status {
        case "Idle":             return "Ready"
        case "Streaming":        return "Streaming live"
        case "Upload retrying":  return "Reconnecting…"
        case "Session stopped":  return "Session ended"
        default:                 return controller.status
        }
    }

    private var sessionStatusIcon: String {
        switch controller.status {
        case "Streaming":        return "dot.radiowaves.up.forward"
        case "Upload retrying":  return "arrow.clockwise"
        default:                 return "circle"
        }
    }

    private var sessionStatusColor: Color {
        switch controller.status {
        case "Streaming":       return .green
        case "Upload retrying": return .orange
        default:                return .secondary
        }
    }
}

// MARK: - Signal Bars

private struct SignalBars: View {
    let rssi: Int

    private var strength: Int {
        switch rssi {
        case (-60)...:    return 3
        case (-75)...(-61): return 2
        default:          return 1
        }
    }

    var body: some View {
        HStack(alignment: .bottom, spacing: 3) {
            ForEach(1...3, id: \.self) { level in
                RoundedRectangle(cornerRadius: 2)
                    .frame(width: 5, height: CGFloat(level * 5 + 3))
                    .foregroundStyle(level <= strength ? Color.blue : Color.secondary.opacity(0.25))
            }
        }
    }
}
