# tests/test_photo_stacker.py
import unittest
import tempfile
import shutil
from pathlib import Path
import os
from PIL import Image, ImageDraw
import threading
import queue
import time

from focus_stacking.main import PhotoStackerGUI
from focus_stacking.custom_types import MockTk


class TestPhotoStacker(unittest.TestCase):
    def setUp(self):
        """Set up test environment before each test"""
        # Create temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        self.input_dir = Path(self.test_dir) / "input"
        self.input_dir.mkdir()
        self.output_dir = Path(self.test_dir) / "output"
        self.output_dir.mkdir()
        
        # Create test images
        self.test_images = self.create_test_images()
        
        # Initialize app in testing mode
        self.root = MockTk()
        self.app = PhotoStackerGUI(self.root, testing_mode=True)
        
        # Mock process runner to avoid actual subprocess calls
        self.app.run_process = self.mock_run_process

    def create_test_images(self, count: int = 10, size: tuple[int, int] = (800, 600)) -> list[Path]:
        """Create a series of test images with different focus points"""
        images: list[Path] = []
        for i in range(count):
            img = Image.new('RGB', size, color='white')
            draw = ImageDraw.Draw(img)
            
            # Draw some shapes at different "depths"
            center_y = size[1] // 2
            
            # Draw rectangles at different positions to simulate focus
            for j in range(5):
                x = j * (size[0] // 5)
                # Make each rectangle sharp in its respective frame
                if j == i % 5:
                    color = 'black'  # Sharp
                    width = 3
                else:
                    color = 'gray'   # Blurry
                    width = 1
                
                # Draw rectangle
                draw.rectangle(
                    [x, center_y - 50, x + 80, center_y + 50],
                    outline=color,
                    width=width
                )
                
                # Add some text to help verify focus
                draw.text((x + 10, center_y), f"Focus {j}", fill=color)
            
            # Save image
            path = self.input_dir / f"test_image_{i:02d}.jpg"
            img.save(path, quality=95, optimize=True)
            images.append(path)
        
        return images
    
    def mock_run_process(self, cmd, desc=None) -> bool:
        """Mock process runner that creates dummy output files"""
        # Get the output path from the command
        output_path = None
        if '--output' in str(cmd):
            for i, arg in enumerate(cmd):
                if str(arg) == '--output' and i + 1 < len(cmd):
                    output_path = cmd[i + 1]
                    break
        
        if output_path:
            # Ensure the output directory exists
            Path(output_path).parent.mkdir(exist_ok=True)
            # Create a dummy output file
            with open(output_path, 'wb') as f:
                f.write(b'test output')
        
        # Always return success in test mode
        return True

    def test_basic_processing(self):
        """Test basic processing without optimizations"""
        output_path = str(self.output_dir / "output.tif")

        # Setup processing
        self.app.input_files = [str(path) for path in self.test_images]
        self.app.set_var("output_file", output_path)
        self.app.set_var("speed_mode", False)
        self.app.set_var("frame_skip", 1)

        # Run processing
        self.app.process_images()

        # Verify output
        self.assertTrue(os.path.exists(output_path))
        with open(output_path, "rb") as f:
            self.assertEqual(f.read(), b"test output")

    def test_speed_mode(self):
        """Test processing with speed mode enabled"""
        output_path = str(self.output_dir / "speed_mode.tif")

        self.app.input_files = [str(path) for path in self.test_images]
        self.app.set_var("output_file", output_path)
        self.app.set_var("speed_mode", True)
        self.app.set_var("frame_skip", 1)

        self.app.process_images()

        self.assertTrue(os.path.exists(output_path))

    def test_frame_skip(self):
        """Test processing with frame skipping"""
        output_path = str(self.output_dir / "frame_skip.tif")

        self.app.input_files = [str(path) for path in self.test_images]
        self.app.set_var("output_file", output_path)
        self.app.set_var("speed_mode", False)
        self.app.set_var("frame_skip", 2)

        initial_count = len(self.app.input_files)
        self.app.process_images()

        self.assertTrue(os.path.exists(output_path))

    def test_process_validation(self):
        """Test input validation"""
        # Test empty input
        self.app.input_files = []
        with self.assertRaises(ValueError):
            self.app.process_images()

        # Test missing output path
        self.app.input_files = [str(path) for path in self.test_images]
        self.app.set_var("output_file", "")
        with self.assertRaises(ValueError):
            self.app.process_images()

    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir)