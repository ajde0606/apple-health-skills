# HealthBridge iOS App (Milestone 1 + 2 bootstrap)

This folder contains a SwiftUI app skeleton implementing the iOS-side deliverables from the plan:

- HealthKit permissions for core types (`heartRate`, `bloodGlucose`, `sleepAnalysis`)
- Foreground/manual sync flow
- Anchored incremental fetch per type (anchor persisted locally)
- Batched HTTPS upload to the Mac collector `/ingest`
- Local queue for failed uploads (retry on next sync)

## Wiring notes

1. Create an Xcode iOS app project named `HealthBridgeApp` and copy in these files.
2. Enable entitlements:
   - HealthKit capability
   - Background modes (when implementing Milestone 3)
3. Add `NSHealthShareUsageDescription` in `Info.plist`.
4. Configure collector URL/token/device in `AppConfig.swift`.

## Current scope

- This implementation focuses on Milestone 1 + Milestone 2 core data flow.
- Observer queries/background delivery are intentionally deferred to Milestone 3.
