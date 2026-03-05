# AppleHealthBridge Icon Design

## Concept
The icon combines three ideas:
- **Health signal**: an ECG-style line represents Apple Health data.
- **Bridge structure**: stylized bridge pillars and deck symbolize data transfer.
- **Trusted sync**: clean blue gradients imply secure transport over private networking.

## Visual spec
- Canvas: 1024×1024 (App Store source size)
- Corner radius target: 200 on source canvas (system will apply final masks)
- Primary colors:
  - `#1C9EFF` (light blue)
  - `#0064D2` (deep blue)
  - `#FFFFFF` and `#E8F5FF` for foreground elements
- Style: minimal, high contrast, no text, recognizable at small sizes

## File
- Source vector: `app_icon_concept.svg`

## Export guidance
Export from the SVG to PNG for Xcode AppIcon slots, including:
- iOS marketing icon: 1024×1024
- macOS slots: 16, 32, 64, 128, 256, 512, 1024

Keep foreground centered and avoid placing key strokes too close to the edge so masking does not clip the signal line.
