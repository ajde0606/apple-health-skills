# App Store Metadata — AppleHealthBridge

## App Name
AppleHealthBridge

## Subtitle
Private HealthKit sync to your Mac

## Promotional Text
Securely sync your Apple Health data to your own Mac collector over HTTPS and Tailscale. No cloud account required.

## Description
AppleHealthBridge helps you move your Apple Health data from iPhone to your personal Mac collector so you can run private analytics and AI workflows on your own infrastructure.

With AppleHealthBridge you can:
- Connect to your Mac securely using HTTPS
- Configure quickly by scanning a QR code from your collector
- Authorize HealthKit access with clear, in-app controls
- Run an initial bootstrap sync for recent history
- Keep data updated with incremental sync and background delivery
- Stream live heart-rate sessions from supported BLE heart-rate sensors
- Review sync logs to monitor uploads, retries, and status

Privacy-first by design:
- Your data is uploaded only to the collector endpoint you configure
- No AppleHealthBridge cloud account is required
- Works well with Tailscale so traffic stays inside your private network

AppleHealthBridge is ideal for people who want personal health observability while keeping full control of data storage and processing.

## Keywords
Apple Health,HealthKit,health sync,heart rate,sleep,blood glucose,Tailscale,privacy,local first,wellness

## What’s New (1.0.0)
- Initial release of AppleHealthBridge
- HealthKit authorization and manual sync controls
- Bootstrap + incremental sync flows
- Background observer delivery for supported metrics
- QR-based collector configuration
- Live BLE heart-rate streaming mode
- Sync log timeline for easier troubleshooting

## Category
Health & Fitness

## Age Rating
4+

## Support URL
https://github.com/your-org/apple-health-skills

## Marketing URL
https://github.com/your-org/apple-health-skills

## Privacy Policy URL
https://github.com/your-org/apple-health-skills/blob/main/README.md

## Notes for App Review
- The app requests HealthKit read permissions to sync user-authorized samples to a user-owned backend.
- Data is sent only to a user-configured endpoint.
- HTTPS is required for production use.
