# PPAHE (Per-Pixel Adaptive Histogram Equalization)

PPAHE is an advanced image enhancement tool that builds upon traditional CLAHE (Contrast Limited Adaptive Histogram Equalization) by computing optimal contrast adjustments for each individual pixel. This results in superior contrast enhancement, particularly in images with varying levels of detail and contrast.

![PPAHE Example](http://via.placeholder.com/800x400)

## Features

- 🖼️ Advanced per-pixel contrast enhancement
- 🎚️ Adjustable parameters for fine-tuning results
- 🖱️ User-friendly GUI interface
- 💾 Support for common image formats (PNG, JPEG, BMP, TIFF)
- 📊 Real-time processing feedback
- 🔄 Side-by-side comparison view

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ppahe.git
cd ppahe
```

2. Create and activate a virtual environment (recommended):
```bash
python -m venv ppahe-env
# On Windows:
ppahe-env\Scripts\activate
# On Unix or MacOS:
source ppahe-env/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### GUI Application

1. Start the application:
```bash
python ppahe_gui.py
```

2. Use the interface:
   - Click "Load Image" to select an input image
   - Adjust parameters:
     - Min Window Size: Smallest neighborhood size (odd number, typically 3-7)
     - Max Window Size: Largest neighborhood size (odd number, typically 33-65)
     - Clip Limit: Controls contrast enhancement aggressiveness (typically 2.0-4.0)
   - Click "Enhance" to process the image
   - Use "Save Enhanced" to export the result

### Command Line Usage

You can also use PPAHE programmatically:

```python
from ppahe import PPAHE
import cv2

# Initialize PPAHE
enhancer = PPAHE(
    min_window=3,
    max_window=65,
    clip_limit=3.0,
    n_bins=256
)

# Load and process image
image = cv2.imread('input.png', cv2.IMREAD_GRAYSCALE)
enhanced = enhancer.enhance(image)

# Save result
cv2.imwrite('enhanced.png', enhanced)
```

## Parameters

| Parameter | Description | Typical Range | Notes |
|-----------|-------------|---------------|-------|
| min_window | Minimum window size | 3-7 | Must be odd number |
| max_window | Maximum window size | 33-65 | Must be odd number |
| clip_limit | Contrast limit factor | 2.0-4.0 | Higher values = more contrast |
| n_bins | Number of histogram bins | 256 | Usually leave at default |

## Performance Considerations

- Processing time scales with image size due to per-pixel calculations
- Recommended maximum image size: 1000x1000 pixels
- Large window sizes increase processing time
- Consider downscaling large images before processing

## How It Works

PPAHE improves upon traditional CLAHE by:

1. Computing optimal window sizes for each pixel based on:
   - Local variance
   - Gradient magnitude
   - Edge strength

2. Performing contrast-limited histogram equalization with:
   - Per-pixel neighborhood analysis
   - Adaptive clipping limits
   - Gradient-aware enhancement

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Based on research in adaptive histogram equalization techniques
- Inspired by the CLAHE algorithm
- Built with Python and modern image processing libraries

## Citation

If you use PPAHE in your research, please cite:

```bibtex
@software{ppahe2024,
  author = {Your Name},
  title = {PPAHE: Per-Pixel Adaptive Histogram Equalization},
  year = {2024},
  url = {https://github.com/yourusername/ppahe}
}
```

## Support

For support, please:
1. Check the existing issues
2. Create a new issue with:
   - Your system information
   - Steps to reproduce the problem
   - Example images (if applicable)
   - Error messages and logs