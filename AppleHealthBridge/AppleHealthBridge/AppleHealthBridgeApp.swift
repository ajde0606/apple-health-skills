import SwiftUI
import BackgroundTasks
import UIKit

final class AppDelegate: NSObject, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        BGTaskScheduler.shared.register(forTaskWithIdentifier: SyncCoordinator.backgroundProcessingTaskID, using: nil) { task in
            guard let processingTask = task as? BGProcessingTask else {
                task.setTaskCompleted(success: false)
                return
            }
            SyncCoordinator.shared.handleBackgroundProcessingTask(processingTask)
        }

        return true
    }
}

@main
struct AppleHealthBridgeApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var coordinator = SyncCoordinator.shared
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(coordinator)
                .task {
                    await coordinator.startBackgroundSync()
                }
        }
        .onChange(of: scenePhase) { newPhase in
            if newPhase == .background {
                coordinator.scheduleBackgroundProcessing()
            }
        }
    }
}
