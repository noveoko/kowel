import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import os
from pathlib import Path
import threading


class ImageAlignerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Alignment Tool")
        self.root.geometry("600x400")

        # Variables
        self.input_dir = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")
        self.progress_var = tk.DoubleVar(value=0)

        # Create GUI elements
        self.create_widgets()

        # Hugin executable path
        self.align_tool = r"C:\Program Files\Hugin\bin\align_image_stack.exe"

        # Verify align_image_stack.exe exists
        if not os.path.exists(self.align_tool):
            messagebox.showerror(
                "Error", "align_image_stack.exe not found!\nPlease install Hugin first."
            )
            root.quit()

    def create_widgets(self):
        # Input directory selection
        input_frame = ttk.LabelFrame(self.root, text="Input Directory", padding=10)
        input_frame.pack(fill="x", padx=10, pady=5)

        ttk.Entry(input_frame, textvariable=self.input_dir, width=50).pack(
            side="left", padx=5
        )
        ttk.Button(input_frame, text="Browse", command=self.browse_input).pack(
            side="left"
        )

        # Output directory selection
        output_frame = ttk.LabelFrame(self.root, text="Output Directory", padding=10)
        output_frame.pack(fill="x", padx=10, pady=5)

        ttk.Entry(output_frame, textvariable=self.output_dir, width=50).pack(
            side="left", padx=5
        )
        ttk.Button(output_frame, text="Browse", command=self.browse_output).pack(
            side="left"
        )

        # Options Frame
        options_frame = ttk.LabelFrame(self.root, text="Alignment Options", padding=10)
        options_frame.pack(fill="x", padx=10, pady=5)

        # Checkboxes for common options
        self.use_gpu = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            options_frame, text="Use GPU acceleration", variable=self.use_gpu
        ).pack(anchor="w")

        self.auto_crop = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame, text="Auto-crop aligned images", variable=self.auto_crop
        ).pack(anchor="w")

        # Progress Frame
        progress_frame = ttk.LabelFrame(self.root, text="Progress", padding=10)
        progress_frame.pack(fill="x", padx=10, pady=5)

        self.progress_bar = ttk.Progressbar(
            progress_frame, variable=self.progress_var, maximum=100, mode="determinate"
        )
        self.progress_bar.pack(fill="x", padx=5, pady=5)

        ttk.Label(progress_frame, textvariable=self.status_var).pack()

        # Control buttons
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(
            button_frame, text="Start Alignment", command=self.start_alignment
        ).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel_alignment).pack(
            side="left"
        )

        # Log frame
        log_frame = ttk.LabelFrame(self.root, text="Log", padding=10)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.log_text = tk.Text(log_frame, height=8, width=50)
        self.log_text.pack(fill="both", expand=True)

        # Add scrollbar to log
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=scrollbar.set)

    def browse_input(self):
        directory = filedialog.askdirectory()
        if directory:
            self.input_dir.set(directory)

    def browse_output(self):
        directory = filedialog.askdirectory()
        if directory:
            self.output_dir.set(directory)

    def log(self, message):
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")

    def start_alignment(self):
        if not self.input_dir.get() or not self.output_dir.get():
            messagebox.showerror(
                "Error", "Please select both input and output directories!"
            )
            return

        # Start alignment in a separate thread
        self.alignment_thread = threading.Thread(target=self.align_images)
        self.alignment_thread.start()

    def cancel_alignment(self):
        if hasattr(self, "process"):
            self.process.terminate()
        self.status_var.set("Cancelled")
        self.progress_var.set(0)

    def align_images(self):
        input_path = Path(self.input_dir.get())
        output_path = Path(self.output_dir.get())

        # Get list of image files
        image_files = [
            f
            for f in input_path.glob("*")
            if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".tif", ".tiff")
        ]

        if not image_files:
            messagebox.showerror("Error", "No image files found in input directory!")
            return

        self.status_var.set("Aligning images...")
        self.log(f"Found {len(image_files)} images to process")

        # Build command
        cmd = [
            self.align_tool,
            "-a",
            str(output_path / "aligned_"),  # output prefix
            "-C" if self.auto_crop.get() else None,  # auto crop
            "--gpu" if self.use_gpu.get() else None,
        ]

        # Add input files
        cmd.extend(str(f) for f in image_files)

        # Remove None values
        cmd = [x for x in cmd if x is not None]

        try:
            self.log(f"Running command: {' '.join(cmd)}")
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )

            # Monitor process
            while True:
                output = self.process.stdout.readline()
                if output == "" and self.process.poll() is not None:
                    break
                if output:
                    self.log(output.strip())
                    # Update progress (this is approximate since align_image_stack doesn't provide progress)
                    if "writing" in output.lower():
                        self.progress_var.set(100)

            rc = self.process.poll()
            if rc == 0:
                self.status_var.set("Alignment complete!")
                messagebox.showinfo(
                    "Success", "Image alignment completed successfully!"
                )
            else:
                error = self.process.stderr.read()
                self.log(f"Error: {error}")
                self.status_var.set("Error during alignment")
                messagebox.showerror("Error", f"Alignment failed with error code {rc}")

        except Exception as e:
            self.log(f"Error: {str(e)}")
            self.status_var.set("Error during alignment")
            messagebox.showerror("Error", str(e))

        finally:
            self.progress_var.set(0)


if __name__ == "__main__":
    root = tk.Tk()
    app = ImageAlignerGUI(root)
    root.mainloop()
