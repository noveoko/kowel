import tkinter as tk
import subprocess
import os
from pathlib import Path
import threading
import queue
import cv2
import numpy as np
from PIL import Image
import statistics
from tkinter import ttk, filedialog, messagebox
import statistics
import datetime

class HuginAlignGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Hugin Image Alignment Tool")
        self.root.geometry("700x600")
        
        # Variables
        self.input_folder = tk.StringVar()
        self.output_folder = tk.StringVar()
        self.hugin_path = tk.StringVar(value="C:\\Program Files\\Hugin\\bin")
        self.use_quality_filter = tk.BooleanVar(value=False)
        self.frames_percentage = tk.StringVar(value="100")
        self.estimated_time = tk.StringVar(value="--:--:--")
        self.status_queue = queue.Queue()
        
        # Control flags
        self.processing = False
        self.stop_requested = False
        
        # Button references (initialize as None)
        self.start_button = None
        self.stop_button = None
        self.cancel_button = None
        
        # Create GUI (this will initialize the buttons)
        self.create_gui()
        self.update_status()
    
    def calculate_sharpness(self, image_path):
        """Calculate image sharpness using Laplacian variance."""
        try:
            img = cv2.imread(str(image_path))
            if img is None:
                return 0
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            return cv2.Laplacian(gray, cv2.CV_64F).var()
        except Exception as e:
            self.status_queue.put(f"Warning: Error calculating sharpness for {image_path}: {str(e)}")
            return 0

    def find_sharpest_image(self, image_files):
        """Find the sharpest image from a list of image files."""
        sharpness_scores = []
        for img_path in image_files:
            score = self.calculate_sharpness(img_path)
            sharpness_scores.append((score, img_path))
        
        # Sort by sharpness score
        sharpness_scores.sort(reverse=True)
        return sharpness_scores[0][1]

    def browse_input(self):
        folder = filedialog.askdirectory()
        if folder:
            self.input_folder.set(folder)

    def browse_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder.set(folder)

    def browse_hugin(self):
        folder = filedialog.askdirectory()
        if folder:
            self.hugin_path.set(folder)

    def update_status(self):
        while True:
            try:
                message = self.status_queue.get_nowait()
                self.status_text.insert(tk.END, message + "\n")
                self.status_text.see(tk.END)
            except queue.Empty:
                break
        self.root.after(100, self.update_status)

    def start_processing(self):
        if not all([self.input_folder.get(), self.output_folder.get(), self.hugin_path.get()]):
            messagebox.showerror("Error", "Please select all required folders")
            return
        
        if self.processing:
            return
        
        self.processing = True
        self.stop_requested = False
        self.progress_bar.start()
        self.update_button_states()
        
        thread = threading.Thread(target=self.process_images)
        thread.daemon = True
        thread.start()

    def cancel_processing(self):
        """Immediately cancel processing"""
        self.processing = False
        self.stop_requested = True
        self.progress_bar.stop()
        self.status_queue.put("Processing cancelled")
        self.update_button_states()

    def find_sharpest_image(self, image_files):
        """Find the sharpest image from a list of image files."""
        sharpness_scores = []
        for img_path in image_files:
            score = self.calculate_sharpness(img_path)
            sharpness_scores.append((score, img_path))
        
        # Sort by sharpness score
        sharpness_scores.sort(reverse=True)
        return sharpness_scores[0][1]

    def browse_input(self):
        folder = filedialog.askdirectory()
        if folder:
            self.input_folder.set(folder)
            self.update_time_estimate()

    def browse_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder.set(folder)

    def browse_hugin(self):
        folder = filedialog.askdirectory()
        if folder:
            self.hugin_path.set(folder)

    def create_gui(self):
        # Main frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Folder Selection Frame
        folder_frame = ttk.LabelFrame(self.main_frame, text="Folder Selection", padding="5")
        folder_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        # Input folder selection
        ttk.Label(folder_frame, text="Input Folder:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(folder_frame, textvariable=self.input_folder, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(folder_frame, text="Browse", command=self.browse_input).grid(row=0, column=2)
        
        # Output folder selection
        ttk.Label(folder_frame, text="Output Folder:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(folder_frame, textvariable=self.output_folder, width=50).grid(row=1, column=1, padx=5)
        ttk.Button(folder_frame, text="Browse", command=self.browse_output).grid(row=1, column=2)
        
        # Hugin path selection
        ttk.Label(folder_frame, text="Hugin Path:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(folder_frame, textvariable=self.hugin_path, width=50).grid(row=2, column=1, padx=5)
        ttk.Button(folder_frame, text="Browse", command=self.browse_hugin).grid(row=2, column=2)
        
        # Settings Frame
        settings_frame = ttk.LabelFrame(self.main_frame, text="Processing Settings", padding="5")
        settings_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        # Quality filter checkbox
        quality_check = ttk.Checkbutton(settings_frame, text="Use only high quality frames", 
                                    variable=self.use_quality_filter)
        quality_check.grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        
        # Percentage frame selection
        ttk.Label(settings_frame, text="Percentage of frames to use:").grid(row=1, column=0, sticky=tk.W, padx=5)
        percentage_entry = ttk.Entry(settings_frame, textvariable=self.frames_percentage, width=5)
        percentage_entry.grid(row=1, column=1, sticky=tk.W, padx=5)
        ttk.Label(settings_frame, text="%").grid(row=1, column=2, sticky=tk.W)
        
        # Estimated time display
        time_frame = ttk.Frame(settings_frame)
        time_frame.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=5)
        ttk.Label(time_frame, text="Approx. time to complete alignment:").pack(side=tk.LEFT, padx=5)
        ttk.Label(time_frame, textvariable=self.estimated_time).pack(side=tk.LEFT)

        # Progress frame
        progress_frame = ttk.LabelFrame(self.main_frame, text="Progress", padding="5")
        progress_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate')
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # Status text
        self.status_text = tk.Text(self.main_frame, height=12, width=70, wrap=tk.WORD)
        self.status_text.grid(row=3, column=0, columnspan=3, pady=5)
        
        # Scrollbar for status text
        scrollbar = ttk.Scrollbar(self.main_frame, orient="vertical", command=self.status_text.yview)
        scrollbar.grid(row=3, column=3, sticky="ns")
        self.status_text.configure(yscrollcommand=scrollbar.set)
        
        # Control buttons
        button_frame = ttk.Frame(self.main_frame)
        button_frame.grid(row=4, column=0, columnspan=3, pady=10)
        
        # Initialize buttons
        self.start_button = ttk.Button(
            button_frame, 
            text="Start Processing", 
            command=self.start_processing
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(
            button_frame, 
            text="Stop Processing", 
            command=self.stop_processing,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.cancel_button = ttk.Button(
            button_frame, 
            text="Cancel", 
            command=self.cancel_processing
        )
        self.cancel_button.pack(side=tk.LEFT, padx=5)

    def stop_processing(self):
        """Gracefully stop processing after current image completes"""
        if self.processing:
            self.stop_requested = True
            self.status_queue.put("Stopping after current image completes...")
            self.stop_button.configure(state=tk.DISABLED)

    def update_button_states(self):
        """Update button states based on processing status"""
        if not all([self.start_button, self.stop_button, self.cancel_button]):
            return  # Skip if buttons aren't initialized yet
            
        if self.processing:
            self.start_button.configure(state=tk.DISABLED)
            self.stop_button.configure(state=tk.NORMAL)
            self.cancel_button.configure(state=tk.NORMAL)
        else:
            self.start_button.configure(state=tk.NORMAL)
            self.stop_button.configure(state=tk.DISABLED)
            self.cancel_button.configure(state=tk.NORMAL)

    def update_time_estimate(self, *args):
        """Update the estimated completion time based on current settings."""
        try:
            # Get number of images in input folder
            input_path = Path(self.input_folder.get())
            if not input_path.exists():
                self.estimated_time.set("--:--:--")
                return

            # Count image files
            image_files = []
            for ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff']:
                image_files.extend(list(input_path.glob(f'*{ext}')))
                image_files.extend(list(input_path.glob(f'*{ext.upper()}')))

            total_images = len(image_files)
            if total_images < 2:
                self.estimated_time.set("--:--:--")
                return

            # Calculate number of images to process based on percentage
            try:
                percentage = float(self.frames_percentage.get())
                if not 0 < percentage <= 100:
                    self.estimated_time.set("--:--:--")
                    return
            except ValueError:
                self.estimated_time.set("--:--:--")
                return

            num_images = max(2, int(total_images * percentage / 100))
            
            # Adjust for quality filter if enabled
            if self.use_quality_filter.get():
                # Assume about 30% of images might be filtered out
                num_images = max(2, int(num_images * 0.7))

            # Calculate total estimated time
            # Formula: (time per frame) * (number of frames - 1)
            # Subtract 1 because reference frame doesn't need alignment
            total_seconds = self.avg_time_per_frame * (num_images - 1)
            
            # Convert to hours:minutes:seconds
            time_str = str(datetime.timedelta(seconds=int(total_seconds)))
            self.estimated_time.set(time_str)

        except Exception as e:
            self.estimated_time.set("--:--:--")

    def calculate_image_quality(self, image_path):
        """Calculate image quality using multiple metrics."""
        try:
            img = cv2.imread(str(image_path))
            if img is None:
                return 0
                
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Calculate sharpness (Laplacian variance)
            sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Calculate contrast (standard deviation of pixel values)
            contrast = np.std(gray)
            
            # Calculate noise level (mean of local standard deviation)
            noise = cv2.meanStdDev(gray)[1][0][0]
            
            # Combined quality score (you can adjust the weights)
            quality_score = (sharpness * 0.5) + (contrast * 0.3) - (noise * 0.2)
            
            return max(0, quality_score)  # Ensure non-negative
            
        except Exception as e:
            self.status_queue.put(f"Warning: Error calculating quality for {image_path}: {str(e)}")
            return 0

    def filter_images(self, image_files):
        """Filter images based on quality and percentage settings."""
        # Calculate quality scores for all images
        quality_scores = []
        self.status_queue.put("Analyzing image quality...")
        
        for img_path in image_files:
            quality = self.calculate_image_quality(img_path)
            quality_scores.append((quality, img_path))
        
        # Sort by quality score
        quality_scores.sort(reverse=True)
        
        if self.use_quality_filter.get():
            # Calculate quality threshold (median - 1 standard deviation)
            scores_only = [score for score, _ in quality_scores]
            median_score = statistics.median(scores_only)
            std_dev = statistics.stdev(scores_only) if len(scores_only) > 1 else 0
            threshold = median_score - std_dev
            
            # Filter out low quality images
            quality_scores = [(score, path) for score, path in quality_scores if score >= threshold]
            self.status_queue.put(f"Filtered out {len(image_files) - len(quality_scores)} low quality images")
        
        # Calculate how many images to use based on percentage
        try:
            percentage = float(self.frames_percentage.get())
            if not 0 < percentage <= 100:
                raise ValueError("Percentage must be between 0 and 100")
        except ValueError:
            self.status_queue.put("Invalid percentage value, using 100%")
            percentage = 100
        
        num_images = max(2, int(len(quality_scores) * percentage / 100))
        selected_images = [path for _, path in quality_scores[:num_images]]
        
        self.status_queue.put(f"Selected {len(selected_images)} images for processing")
        return selected_images

    def process_images(self):
        try:
            start_time = datetime.datetime.now()
            input_path = Path(self.input_folder.get())
            output_path = Path(self.output_folder.get())
            hugin_path = Path(self.hugin_path.get())

            # Create output directory if it doesn't exist
            output_path.mkdir(parents=True, exist_ok=True)

            # Get all image files
            image_files = []
            for ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff']:
                image_files.extend(list(input_path.glob(f'*{ext}')))
                image_files.extend(list(input_path.glob(f'*{ext.upper()}')))
            
            # Sort files to ensure consistent ordering
            image_files.sort()
            
            if len(image_files) < 2:
                self.status_queue.put(f"Error: Need at least 2 images to align. Found {len(image_files)} images.")
                self.status_queue.put("Supported formats: JPG, JPEG, PNG, TIF, TIFF")
                return

            self.status_queue.put(f"Found {len(image_files)} images")
            
            # Filter images based on quality and percentage settings
            selected_images = self.filter_images(image_files)
            
            if len(selected_images) < 2:
                self.status_queue.put("Error: Not enough images after filtering")
                return
            
            self.status_queue.put("Analyzing image sharpness...")
            
            # Find the sharpest image for reference
            reference_image = self.find_sharpest_image(selected_images)
            self.status_queue.put(f"Using {reference_image.name} as reference image (sharpest)")

            # Create temporary project file with proper initialization
            project_file = output_path / "temp_project.pto"
            
            if self.stop_requested:
                return
            
            # Initialize project file with pto_gen
            subprocess.run([
                str(hugin_path / "pto_gen"),
                str(reference_image),
                *[str(img) for img in selected_images if img != reference_image],
                "-o", str(project_file)
            ], check=True)

            # Process images
            for img in selected_images:
                if self.stop_requested:
                    self.status_queue.put("Processing stopped by user")
                    return

                if img == reference_image:
                    continue

                self.status_queue.put(f"Processing {img.name}")
                
                # Generate control points
                subprocess.run([
                    str(hugin_path / "cpfind"),
                    "--multirow",
                    "--fullscale",
                    "-o", str(project_file),
                    str(project_file)
                ], check=True)

                # Optimize
                subprocess.run([
                    str(hugin_path / "autooptimiser"),
                    "-a",  # Auto align mode
                    "-m",  # Optimize for photometric parameters
                    "-l",  # Optimize for geometric parameters
                    "-o", str(project_file),
                    str(project_file)
                ], check=True)

            # Process final alignment
            for img in selected_images:
                if self.stop_requested:
                    self.status_queue.put("Processing stopped by user")
                    return

                output_file = output_path / f"aligned_{img.name}"
                self.status_queue.put(f"Aligning {img.name}")
                
                subprocess.run([
                    str(hugin_path / "nona"),
                    "-r", "ldr",
                    "-m", "TIFF_m",
                    "-o", str(output_file),
                    str(project_file),
                    str(img)
                ], check=True)

            # Cleanup
            if project_file.exists():
                project_file.unlink()
            self.status_queue.put("Processing complete!")

            # Calculate processing time
            end_time = datetime.datetime.now()
            total_time = (end_time - start_time).total_seconds()
            num_processed = len(selected_images) - 1  # Subtract 1 for reference frame
            if num_processed > 0:
                self.avg_time_per_frame = total_time / num_processed
                self.update_time_estimate()

        except subprocess.CalledProcessError as e:
            self.status_queue.put(f"Command Error: {str(e)}")
            self.status_queue.put(f"Command output: {e.output if hasattr(e, 'output') else 'No output available'}")
        except Exception as e:
            self.status_queue.put(f"Error: {str(e)}")
        finally:
            self.processing = False
            self.stop_requested = False
            self.root.after(0, self.progress_bar.stop)
            self.root.after(0, self.update_button_states)

def main():
    root = tk.Tk()
    app = HuginAlignGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
