# Blender AI Brush Texture Generator

Generate custom brush textures for Blender using AI image generation. This plugin allows you to create high-quality, procedural brush textures by simply describing the texture you want.

## Features
- Generate custom brush textures directly within Blender
- High-quality 8K monochrome outputs optimized for Blender brushes
- Perfect circular gradient falloff for smooth brush behavior
- Secure API token management
- Simple one-click texture generation
- Automatic texture import into Blender

## Installation

### Prerequisites
1. Blender 3.0 or newer
2. A Replicate API token ([Get one here](https://replicate.com))
3. Internet connection

### Steps
1. Install the `replicate` Python package in Blender:
```python
import subprocess
import sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "replicate"])
```

2. Install the plugin:
   - Download `ai_brush_generator.py`
   - Open Blender: Edit > Preferences > Add-ons > Install
   - Select the downloaded file
   - Enable the add-on

3. Configure:
   - In Blender Preferences, find "AI Brush Generator" in the add-ons list
   - Enter your Replicate API token in the preferences panel

## Usage
1. Open the 3D View sidebar (N key)
2. Find the "AI Brush Gen" tab
3. Enter a texture type (e.g., "brick", "stone", "cracked earth")
4. Click "Generate Brush Texture"
5. The texture will be automatically added to your Blender textures

## Best Practices
- Use descriptive texture names (e.g., "rough stone" instead of just "rough")
- The generated textures are optimized for:
  - Sculpting brushes
  - Texture painting
  - Displacement maps
  - Alpha masks

## Technical Details
- Output format: WebP
- Resolution: 8K monochrome
- Aspect ratio: 1:1
- Optimized for brush falloff with smooth gradient edges
- Uses the Flux Schnell model via Replicate API

## Troubleshooting
- If the plugin can't find the `replicate` package, try reinstalling it using the provided Python script
- Ensure your API token is entered correctly in the preferences
- Check your internet connection if generation fails
- Make sure you have enough disk space for temporary files

## Credits
- Uses the Flux Schnell model by Black Forest Labs
- Replicate API for image generation
- Developed with ♥ for the Blender community

## License
MIT License - Feel free to use, modify, and distribute!

Would you like me to add any additional sections or information to the README?
