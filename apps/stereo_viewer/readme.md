# 3D Image Creator

A Python application for creating stereoscopic 3D images suitable for viewing with VR headsets like Google Cardboard. The app combines left and right perspective images into a single side-by-side format optimized for VR viewing.

## Table of Contents
- [Installation](#installation)
- [Usage](#usage)
- [Image Preparation Guide](#image-preparation-guide)
- [Troubleshooting](#troubleshooting)
- [Tips for Best Results](#tips-for-best-results)

## Installation

1. Ensure you have Python 3.7 or newer installed
2. Install required dependencies:
```bash
pip install Pillow tk
```
3. Download the script and run:
```bash
python stereo_image_viewer.py
```

## Usage

1. Launch the application
2. Load images either by:
   - Dragging and dropping images onto the designated areas
   - Clicking the areas to browse for files
3. The preview will generate automatically
4. Use Ctrl+S or click Save to export the final image

## Image Preparation Guide

### Taking Stereoscopic Photos

1. **Basic Method (Two Sequential Photos)**:
   - Keep the camera level and parallel to the ground
   - Take first photo (left perspective)
   - Move camera horizontally to the right ~6.5cm (2.5 inches, average human eye separation)
   - Take second photo (right perspective)
   - Keep all camera settings identical between shots
   - Subject should be stationary

2. **Dual Camera Method**:
   - Use two identical cameras mounted ~6.5cm apart
   - Trigger simultaneously (or near-simultaneous)
   - Ensure cameras have identical settings

### Correcting Common Issues

1. **Vertical Misalignment**:
   - Open both images in a photo editor (e.g., GIMP, Photoshop)
   - Overlay images at 50% opacity
   - Align using horizon or prominent features
   - Crop both images to same dimensions

2. **Fixing Lens Distortion**:
   - Use lens correction tools in photo editing software
   - Apply identical corrections to both images
   - Common software options:
     - Adobe Lightroom: Use Lens Corrections panel
     - GIMP: Use Lens Distortion filter
     - DxO PhotoLab: Use automatic lens corrections

3. **Adjusting Convergence**:
   - If objects appear too far in front/behind the screen:
     1. Open images in photo editor
     2. Shift images horizontally closer/further apart
     3. Maintain equal crop dimensions
     4. Generally, align foreground subjects for comfortable viewing

### Image Requirements

- Identical resolutions for left and right images
- Minimal rotation differences (<1 degree)
- Similar exposure and color balance
- Sharp focus
- Recommended minimum resolution: 1080p per eye (2160x1080 total)

### Dealing with Distorted Images

1. **Barrel/Pincushion Distortion**:
   ```
   Barrel Distortion:           Pincushion Distortion:
   (edges curve outward)        (edges curve inward)
   ╭──────────╮                ╱────────╲
   │          │     →         │          │
   │    []    │               │    []    │
   │          │               │          │
   ╰──────────╯                ╲────────╱
   ```
   
   Fix using:
   - Lightroom: Lens Corrections > Manual > Distortion slider
   - GIMP: Filters > Distorts > Lens Distortion
   - Apply identical corrections to both images

2. **Keystone Distortion** (converging vertical lines):
   ```
   Before:          After:
   ╱──────╲         ┌──────┐
   │      │    →    │      │
   │      │         │      │
   ╲──────╱         └──────┘
   ```
   
   Fix using:
   - Perspective correction tools
   - Ensure vertical lines are parallel
   - Apply identical corrections to both images

3. **Rotational Misalignment**:
   ```
   Before:          After:
   ╱────────┐       ┌────────┐
   │        │  →    │        │
   └────────╲       └────────┘
   ```
   
   Fix by:
   - Using horizon line as reference
   - Rotating images to align
   - Crop to remove empty corners

## Troubleshooting

Common Issues and Solutions:

1. **Double Vision When Viewing**:
   - Images might be too far apart
   - Try regenerating with less separation
   - Ensure parallel camera alignment when shooting

2. **Uncomfortable Viewing**:
   - Check for vertical misalignment
   - Verify images are same size
   - Confirm both images have identical distortion correction

3. **Blurry Output**:
   - Verify source images are sharp
   - Check original resolution meets minimum requirements
   - Ensure both images were taken with same focus point

## Tips for Best Results

1. **Camera Settings**:
   - Use manual mode to ensure consistent settings
   - Avoid wide-angle lenses (increases distortion)
   - Use aperture f/8 or smaller for good depth of field
   - Keep ISO low to minimize noise
   - Use fast shutter speed to avoid motion blur

2. **Subject Choice**:
   - Start with static subjects
   - Avoid very close foreground objects
   - Include clear reference points at different depths
   - High-contrast scenes work best

3. **Viewing Distance**:
   - Optimal viewing distance: 6-8 inches from phone screen
   - Use Google Cardboard or similar VR viewer
   - View in a well-lit environment
   - Take breaks every 15-20 minutes

4. **File Management**:
   - Keep left/right pairs organized
   - Use consistent naming (e.g., scene_L.jpg, scene_R.jpg)
   - Store original unprocessed files
   - Save final 3D images in PNG format for best quality

## Contributing

Feel free to submit issues and enhancement requests through the GitHub repository.

## License

This project is licensed under the MIT License - see the LICENSE file for details.