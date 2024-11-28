import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import os
import threading
import json
from PIL import Image, ImageTk
import shutil

class FocusStackGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Focus Stack Pro")
        self.root.geometry("800x600")
        
        # Preset configurations
        self.presets = {
            "Modern Digital (High Quality)": {
                "align": "--gpu",
                "enfuse": "--exposure-weight=0 --saturation-weight=0 --contrast-weight=1 --hard-mask",
                "description": "Optimized for modern digital cameras with clean, sharp images"
            },
            "Modern Film Scan": {
                "align": "--gpu --correlation=0.8",
                "enfuse": "--exposure-weight=0.1 --saturation-weight=0.2 --contrast-weight=1 --hard-mask",
                "description": "Balanced settings for high-quality film scans"
            },
            "Vintage Film (Good Condition)": {
                "align": "--gpu --correlation=0.7",
                "enfuse": "--exposure-weight=0.2 --saturation-weight=0.3 --contrast-weight=1",
                "description": "Accommodates slight film degradation while maintaining quality"
            },
            "Damaged Color Film": {
                "align": "--correlation=0.6 --use-given-order",
                "enfuse": "--exposure-weight=0.3 --saturation-weight=0.4 --contrast-weight=0.8",
                "description": "Handles color shifts and moderate damage"
            },
            "Black & White (High Quality)": {
                "align": "--gpu --grayscale",
                "enfuse": "--exposure-weight=0.1 --saturation-weight=0 --contrast-weight=1",
                "description": "Optimized for B&W images with good contrast"
            },
            "Damaged B&W Film": {
                "align": "--grayscale --correlation=0.5",
                "enfuse": "--exposure-weight=0.2 --saturation-weight=0 --contrast-weight=0.8",
                "description": "Handles scratches and damage in B&W material"
            },
            "8mm Film Scan (Good)": {
                "align": "--grayscale --correlation=0.6",
                "enfuse": "--exposure-weight=0.3 --saturation-weight=0.1 --contrast-weight=0.7",
                "description": "Optimized for well-preserved 8mm film"
            },
            "8mm Film (Poor Condition)": {
                "align": "--grayscale --correlation=0.4 --use-given-order",
                "enfuse": "--exposure-weight=0.4 --saturation-weight=0 --contrast-weight=0.6",
                "description": "Handles heavy damage and missing frames"
            },
            "Microscope Images": {
                "align": "--gpu --correlation=0.9",
                "enfuse": "--exposure-weight=0 --saturation-weight=0.1 --contrast-weight=1 --hard-mask",
                "description": "Optimized for scientific microscopy"
            },
            "Quick Preview": {
                "align": "--gpu --downsample=2",
                "enfuse": "--exposure-weight=0 --saturation-weight=0 --contrast-weight=1",
                "description": "Fast processing for quick results"
            }
        }

        self.create_widgets()
        
    def create_widgets(self):
        # Create main containers
        self.left_frame = ttk.Frame(self.root, padding="10")
        self.right_frame = ttk.Frame(self.root, padding="10")
        self.left_frame.pack(side="left", fill="both", expand=True)
        self.right_frame.pack(side="right", fill="both", expand=True)

        # Source folder selection
        ttk.Label(self.left_frame, text="Source Images:").pack(anchor="w")
        self.source_frame = ttk.Frame(self.left_frame)
        self.source_frame.pack(fill="x", pady=5)
        self.source_entry = ttk.Entry(self.source_frame)
        self.source_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(self.source_frame, text="Browse", command=self.browse_source).pack(side="right", padx=5)

        # Output folder selection
        ttk.Label(self.left_frame, text="Output Folder:").pack(anchor="w")
        self.output_frame = ttk.Frame(self.left_frame)
        self.output_frame.pack(fill="x", pady=5)
        self.output_entry = ttk.Entry(self.output_frame)
        self.output_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(self.output_frame, text="Browse", command=self.browse_output).pack(side="right", padx=5)

        # Preset selection
        ttk.Label(self.left_frame, text="Select Preset:").pack(anchor="w", pady=(10,0))
        self.preset_var = tk.StringVar()
        self.preset_combo = ttk.Combobox(self.left_frame, textvariable=self.preset_var, state="readonly")
        self.preset_combo["values"] = list(self.presets.keys())
        self.preset_combo.pack(fill="x", pady=5)
        self.preset_combo.bind("<<ComboboxSelected>>", self.update_description)

        # Description box
        ttk.Label(self.left_frame, text="Preset Description:").pack(anchor="w", pady=(10,0))
        self.description_text = tk.Text(self.left_frame, height=4, wrap="word")
        self.description_text.pack(fill="x", pady=5)
        self.description_text.config(state="disabled")

        # Advanced options
        self.advanced_frame = ttk.LabelFrame(self.left_frame, text="Advanced Options", padding="5")
        self.advanced_frame.pack(fill="x", pady=10)
        
        # CPU/GPU selection
        self.gpu_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.advanced_frame, text="Use GPU Acceleration", variable=self.gpu_var).pack(anchor="w")
        
        # Threading selection
        ttk.Label(self.advanced_frame, text="CPU Threads:").pack(anchor="w")
        self.thread_var = tk.StringVar(value="auto")
        thread_combo = ttk.Combobox(self.advanced_frame, textvariable=self.thread_var, width=10)
        thread_combo["values"] = ["auto"] + [str(i) for i in range(1, os.cpu_count() + 1)]
        thread_combo.pack(anchor="w")

        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(self.left_frame, variable=self.progress_var, maximum=100)
        self.progress.pack(fill="x", pady=10)

        # Status label
        self.status_label = ttk.Label(self.left_frame, text="Ready")
        self.status_label.pack(fill="x")

        # Process button
        self.process_button = ttk.Button(self.left_frame, text="Start Processing", command=self.start_processing)
        self.process_button.pack(fill="x", pady=10)

        # Preview area
        self.preview_label = ttk.Label(self.right_frame, text="Preview")
        self.preview_label.pack()
        self.preview_canvas = tk.Canvas(self.right_frame, bg="gray", width=400, height=400)
        self.preview_canvas.pack(fill="both", expand=True)

    def browse_source(self):
        folder = filedialog.askdirectory()
        if folder:
            self.source_entry.delete(0, tk.END)
            self.source_entry.insert(0, folder)
            self.load_preview()

    def browse_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, folder)

    def update_description(self, event=None):
        preset = self.preset_var.get()
        if preset in self.presets:
            self.description_text.config(state="normal")
            self.description_text.delete(1.0, tk.END)
            self.description_text.insert(1.0, self.presets[preset]["description"])
            self.description_text.config(state="disabled")

    def load_preview(self):
        source_dir = self.source_entry.get()
        if os.path.exists(source_dir):
            image_files = [f for f in os.listdir(source_dir) 
                         if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp'))]
            if image_files:
                first_image = os.path.join(source_dir, image_files[0])
                try:
                    img = Image.open(first_image)
                    # Resize to fit canvas while maintaining aspect ratio
                    canvas_width = 400
                    canvas_height = 400
                    img.thumbnail((canvas_width, canvas_height))
                    photo = ImageTk.PhotoImage(img)
                    self.preview_canvas.create_image(
                        canvas_width//2, canvas_height//2,
                        image=photo, anchor="center"
                    )
                    self.preview_canvas.image = photo
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load preview: {str(e)}")

    def start_processing(self):
        source_dir = self.source_entry.get()
        output_dir = self.output_entry.get()
        preset = self.preset_var.get()

        if not all([source_dir, output_dir, preset]):
            messagebox.showerror("Error", "Please select source directory, output directory, and preset")
            return

        if not os.path.exists(source_dir):
            messagebox.showerror("Error", "Source directory does not exist")
            return

        # Disable UI during processing
        self.process_button.config(state="disabled")
        self.status_label.config(text="Processing...")
        self.progress_var.set(0)

        # Start processing in a separate thread
        threading.Thread(target=self.process_images, args=(source_dir, output_dir, preset)).start()

    def process_images(self, source_dir, output_dir, preset):
        try:
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)

            # Get preset parameters
            params = self.presets[preset]
            align_params = params["align"]
            enfuse_params = params["enfuse"]

            # Modify parameters based on advanced options
            if not self.gpu_var.get():
                align_params = align_params.replace("--gpu", "")
            
            thread_count = self.thread_var.get()
            if thread_count != "auto":
                align_params += f" --threads={thread_count}"
                enfuse_params += f" --threads={thread_count}"

            # Get list of image files
            image_files = [f for f in os.listdir(source_dir) 
                         if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp'))]
            
            if not image_files:
                raise Exception("No compatible image files found in source directory")

            # Create working directory
            work_dir = os.path.join(output_dir, "temp_work")
            os.makedirs(work_dir, exist_ok=True)

            # Copy images to working directory
            self.update_status("Copying files...", 10)
            for img in image_files:
                shutil.copy2(os.path.join(source_dir, img), work_dir)

            # Run alignment
            self.update_status("Aligning images...", 30)
            align_cmd = f"align_image_stack {align_params} -o aligned_ {work_dir}/*.{image_files[0].split('.')[-1]}"
            subprocess.run(align_cmd, shell=True, check=True)

            # Run enfuse
            self.update_status("Fusing images...", 70)
            enfuse_cmd = f"enfuse {enfuse_params} -o {os.path.join(output_dir, 'result.tiff')} {work_dir}/aligned_*.tif"
            subprocess.run(enfuse_cmd, shell=True, check=True)

            # Clean up
            self.update_status("Cleaning up...", 90)
            shutil.rmtree(work_dir)

            self.update_status("Processing complete!", 100)
            messagebox.showinfo("Success", "Focus stacking completed successfully!")

        except Exception as e:
            self.update_status(f"Error: {str(e)}", 0)
            messagebox.showerror("Error", str(e))

        finally:
            # Re-enable UI
            self.root.after(0, lambda: self.process_button.config(state="normal"))

    def update_status(self, message, progress):
        self.root.after(0, lambda: self.status_label.config(text=message))
        self.root.after(0, lambda: self.progress_var.set(progress))

def main():
    root = tk.Tk()
    app = FocusStackGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()