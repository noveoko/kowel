import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import os
from pathlib import Path
import threading
import re

class FocusStackGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Focus Stacking Tool")
        self.root.geometry("700x600")
        
        # Variables
        self.input_dir = tk.StringVar()
        self.output_file = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")
        self.progress_var = tk.DoubleVar(value=0)
        
        # Enfuse parameters
        self.exposure_weight = tk.DoubleVar(value=0.0)  # 0 for focus stacking
        self.saturation_weight = tk.DoubleVar(value=0.0)  # 0 for focus stacking
        self.contrast_weight = tk.DoubleVar(value=1.0)  # 1 for focus stacking
        self.hard_mask = tk.BooleanVar(value=True)
        self.contrast_window_size = tk.IntVar(value=5)
        self.contrast_edge_scale = tk.DoubleVar(value=0.3)
        
        # Create GUI elements
        self.create_widgets()
        
        # Enfuse executable path
        self.enfuse_tool = r"C:\Program Files\Hugin\bin\enfuse.exe"
        
        # Verify enfuse.exe exists
        if not os.path.exists(self.enfuse_tool):
            messagebox.showerror("Error", "enfuse.exe not found!\nPlease install Hugin first.")
            root.quit()
    
    def create_widgets(self):
        # Input directory selection
        input_frame = ttk.LabelFrame(self.root, text="Input Images", padding=10)
        input_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Entry(input_frame, textvariable=self.input_dir, width=60).pack(side="left", padx=5)
        ttk.Button(input_frame, text="Browse", command=self.browse_input).pack(side="left")
        
        # Output file selection
        output_frame = ttk.LabelFrame(self.root, text="Output Image", padding=10)
        output_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Entry(output_frame, textvariable=self.output_file, width=60).pack(side="left", padx=5)
        ttk.Button(output_frame, text="Browse", command=self.browse_output).pack(side="left")
        
        # Parameters Frame
        params_frame = ttk.LabelFrame(self.root, text="Focus Stacking Parameters", padding=10)
        params_frame.pack(fill="x", padx=10, pady=5)
        
        # Create parameter sliders
        self.create_slider(params_frame, "Contrast Weight:", self.contrast_weight, 0, 1, 0.1)
        self.create_slider(params_frame, "Contrast Window Size:", self.contrast_window_size, 3, 9, 2)
        self.create_slider(params_frame, "Contrast Edge Scale:", self.contrast_edge_scale, 0, 1, 0.1)
        
        # Checkboxes for options
        options_frame = ttk.Frame(params_frame)
        options_frame.pack(fill="x", pady=5)
        
        ttk.Checkbutton(
            options_frame, 
            text="Use Hard Mask (recommended for focus stacking)", 
            variable=self.hard_mask
        ).pack(anchor="w")
        
        # Advanced Options (initially hidden)
        advanced_frame = ttk.LabelFrame(self.root, text="Advanced Options", padding=10)
        advanced_frame.pack(fill="x", padx=10, pady=5)
        
        self.create_slider(advanced_frame, "Exposure Weight:", self.exposure_weight, 0, 1, 0.1)
        self.create_slider(advanced_frame, "Saturation Weight:", self.saturation_weight, 0, 1, 0.1)
        
        # Progress Frame
        progress_frame = ttk.LabelFrame(self.root, text="Progress", padding=10)
        progress_frame.pack(fill="x", padx=10, pady=5)
        
        self.progress_bar = ttk.Progressbar(
            progress_frame, 
            variable=self.progress_var,
            maximum=100,
            mode='determinate'
        )
        self.progress_bar.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(progress_frame, textvariable=self.status_var).pack()
        
        # Control buttons
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Button(button_frame, text="Start Focus Stacking", command=self.start_stacking).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel_stacking).pack(side="left")
        
        # Log frame
        log_frame = ttk.LabelFrame(self.root, text="Log", padding=10)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.log_text = tk.Text(log_frame, height=8, width=60)
        self.log_text.pack(fill="both", expand=True)
        
        # Add scrollbar to log
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=scrollbar.set)
    
    def create_slider(self, parent, label, variable, min_val, max_val, step):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=2)
        
        ttk.Label(frame, text=label, width=20).pack(side="left")
        
        slider = ttk.Scale(
            frame,
            from_=min_val,
            to=max_val,
            variable=variable,
            orient="horizontal"
        )
        slider.pack(side="left", fill="x", expand=True)
        
        # Value label
        value_label = ttk.Label(frame, width=5)
        value_label.pack(side="left")
        
        # Update label when slider moves
        def update_label(*args):
            value_label.config(text=f"{variable.get():.1f}")
        
        variable.trace_add("write", update_label)
        update_label()  # Initial value
    
    def browse_input(self):
        directory = filedialog.askdirectory()
        if directory:
            self.input_dir.set(directory)
    
    def browse_output(self):
        file_types = [
            ('TIFF files', '*.tiff;*.tif'),
            ('JPEG files', '*.jpg;*.jpeg'),
            ('PNG files', '*.png'),
            ('All files', '*.*')
        ]
        filename = filedialog.asksaveasfilename(
            defaultextension=".tif",
            filetypes=file_types
        )
        if filename:
            self.output_file.set(filename)
    
    def log(self, message):
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")
    
    def start_stacking(self):
        if not self.input_dir.get() or not self.output_file.get():
            messagebox.showerror("Error", "Please select both input directory and output file!")
            return
            
        # Start stacking in a separate thread
        self.stacking_thread = threading.Thread(target=self.stack_images)
        self.stacking_thread.start()
    
    def cancel_stacking(self):
        if hasattr(self, 'process'):
            self.process.terminate()
        self.status_var.set("Cancelled")
        self.progress_var.set(0)
    
    def stack_images(self):
        input_path = Path(self.input_dir.get())
        output_file = Path(self.output_file.get())
        
        # Get list of image files
        image_files = [f for f in input_path.glob("*") 
                      if f.suffix.lower() in ('.jpg', '.jpeg', '.png', '.tif', '.tiff')]
        
        if not image_files:
            messagebox.showerror("Error", "No image files found in input directory!")
            return
        
        self.status_var.set("Stacking images...")
        self.log(f"Found {len(image_files)} images to process")
        
        # Build command
        cmd = [
            self.enfuse_tool,
            '--output', str(output_file),
            '--exposure-weight', str(self.exposure_weight.get()),
            '--saturation-weight', str(self.saturation_weight.get()),
            '--contrast-weight', str(self.contrast_weight.get()),
            '--contrast-window-size', str(self.contrast_window_size.get()),
            '--contrast-edge-scale', str(self.contrast_edge_scale.get()),
        ]
        
        if self.hard_mask.get():
            cmd.extend(['--hard-mask'])
        
        # Add input files
        cmd.extend(str(f) for f in image_files)
        
        try:
            self.log(f"Running command: {' '.join(cmd)}")
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Monitor process
            while True:
                output = self.process.stdout.readline()
                if output == '' and self.process.poll() is not None:
                    break
                if output:
                    self.log(output.strip())
                    # Try to parse progress information
                    if "%" in output:
                        try:
                            progress = float(re.search(r'(\d+)%', output).group(1))
                            self.progress_var.set(progress)
                        except:
                            pass
            
            rc = self.process.poll()
            if rc == 0:
                self.status_var.set("Focus stacking complete!")
                messagebox.showinfo("Success", "Focus stacking completed successfully!")
            else:
                error = self.process.stderr.read()
                self.log(f"Error: {error}")
                self.status_var.set("Error during focus stacking")
                messagebox.showerror("Error", f"Focus stacking failed with error code {rc}")
                
        except Exception as e:
            self.log(f"Error: {str(e)}")
            self.status_var.set("Error during focus stacking")
            messagebox.showerror("Error", str(e))
            
        finally:
            self.progress_var.set(0)

if __name__ == "__main__":
    root = tk.Tk()
    app = FocusStackGUI(root)
    root.mainloop()
