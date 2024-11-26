# SuperStack

SuperStack is a powerful focus stacking application that combines multiple images with different focal points into a single, fully-focused image. It uses advanced object detection (YOLOv8) for precise image alignment and sophisticated focus analysis for optimal stacking results.

![SuperStack Demo](demo-focus-stack.jpg)

## Features

- **Intelligent Image Alignment**: Uses YOLOv8 object detection for precise automatic alignment of image sequences
- **Advanced Focus Stacking**: Block-based analysis for superior local contrast optimization
- **Batch Processing**: Process multiple images from a directory in one go
- **Flexible Output**: Support for various image formats (JPG, PNG)
- **Command-Line Interface**: Easy to integrate into photography workflows
- **Progress Logging**: Detailed progress tracking and error reporting

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/superstack.git
cd superstack
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Dependencies

- Python 3.8+
- OpenCV (cv2)
- NumPy
- PyTorch
- Ultralytics (YOLOv8)

## Usage

Basic usage:
```bash
python superstack.py /path/to/image/directory
```

Advanced usage with options:
```bash
python superstack.py /path/to/image/directory \
    --output result.jpg \
    --confidence 0.5 \
    --block-size 8
```

### Command Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `input_dir` | Directory containing input images | (Required) |
| `--output` | Output image path | focus_stacked.jpg |
| `--confidence` | Confidence threshold for object detection | 0.5 |
| `--block-size` | Block size for focus stacking analysis | 8 |

## Best Practices

1. **Image Capture**:
   - Use a tripod for maximum stability
   - Maintain consistent lighting across shots
   - Take photos in sequence from front to back focus
   - Ensure sufficient overlap in focus areas

2. **Input Images**:
   - Use high-quality, well-exposed images
   - Avoid significant movement between shots
   - Ensure all images have the same resolution
   - Use RAW format when possible

3. **Processing**:
   - Start with the default parameters
   - Adjust confidence threshold if alignment issues occur
   - Experiment with block size for different types of subjects

## Example Results

Before (Individual images):
- Image 1: Front focus
- Image 2: Middle focus
- Image 3: Back focus

After (Stacked result):
- Complete focus throughout the entire subject

## Common Issues and Solutions

### Alignment Problems
- **Symptom**: Blurry or doubled edges in output
- **Solution**: Try increasing the confidence threshold

### Missing Focus Areas
- **Symptom**: Some areas appear out of focus
- **Solution**: Decrease the block size for more detailed analysis

### Memory Issues
- **Symptom**: Program crashes with large images
- **Solution**: Reduce input image resolution or increase block size

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- YOLOv8 by Ultralytics
- OpenCV community
- All contributors and testers

## Version History

- 1.0.0
  - Initial release
  - Basic focus stacking functionality
  - YOLOv8 integration for alignment

## Support

For support, please open an issue in the GitHub repository or contact the maintainers.

## Roadmap

- [ ] GUI interface
- [ ] Batch processing improvements
- [ ] Additional alignment methods
- [ ] CUDA acceleration support
- [ ] Custom focus map algorithms

## Citation

If you use SuperStack in your research, please cite:

```bibtex
@software{superstack2024,
  title = {SuperStack: Advanced Focus Stacking with Object Detection},
  author = {Your Name},
  year = {2024},
  url = {https://github.com/yourusername/superstack}
}
```