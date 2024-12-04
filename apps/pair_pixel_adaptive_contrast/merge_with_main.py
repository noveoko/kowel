import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import numpy as np
import cv2
from typing import Optional
import time
from pathlib import Path

# Import our PPAHE class from previous artifact
class PPAHE:
    # [Previous PPAHE implementation remains exactly the same]
    # Note: Full implementation omitted for brevity but would be included here

class PPAHEApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PPAHE Image Enhancement")
        
        # State variables
        self.original_image: Optional[np.ndarray] = None
        self.enhanced_image: Optional[np.ndarray] = None
        self.ppahe = PPAHE()
        
        self.create_gui()
        
    def create_gui(self):
        # Create main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Create image frames
        self.image_frame = ttk.Frame(main_frame)
        self.image_frame.grid(row=0, column=0, columnspan=2, pady=10)
        
        # Create image labels
        self.original_label = ttk.Label(self.image_frame, text="Original Image")
        self.original_label.grid(row=0, column=0, padx=5)
        
        self.enhanced_label = ttk.Label(self.image_frame, text="Enhanced Image")
        self.enhanced_label.grid(row=0, column=1, padx=5)
        
        # Create image display areas
        self.original_display = ttk.Label(self.image_frame)
        self.original_display.grid(row=1, column=0, padx=5)
        
        self.enhanced_display = ttk.Label(self.image_frame)
        self.enhanced_display.grid(row=1, column=1, padx=5)
        
        # Controls frame
        controls_frame = ttk.LabelFrame(main_frame, text="Controls", padding="5")
        controls_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        # Parameter controls
        ttk.Label(controls_frame, text="Min Window Size:").grid(row=0, column=0, padx=5, pady=5)
        self.min_window_var = tk.StringVar(value="3")
        min_window_entry = ttk.Entry(controls_frame, textvariable=self.min_window_var, width=10)
        min_window_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(controls_frame, text="Max Window Size:").grid(row=0, column=2, padx=5, pady=5)
        self.max_window_var = tk.StringVar(value="65")
        max_window_entry = ttk.Entry(controls_frame, textvariable=self.max_window_var, width=10)
        max_window_entry.grid(row=0, column=3, padx=5, pady=5)
        
        ttk.Label(controls_frame, text="Clip Limit:").grid(row=1, column=0, padx=5, pady=5)
        self.clip_limit_var = tk.StringVar(value="3.0")
        clip_limit_entry = ttk.Entry(controls_frame, textvariable=self.clip_limit_var, width=10)
        clip_limit_entry.grid(row=1, column=1, padx=5, pady=5)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            controls_frame,
            variable=self.progress_var,
            maximum=100
        )
        self.progress_bar.grid(row=2, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=10)
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        ttk.Button(
            buttons_frame,
            text="Load Image",
            command=self.load_image
        ).grid(row=0, column=0, padx=5)
        
        ttk.Button(
            buttons_frame,
            text="Enhance",
            command=self.enhance_image
        ).grid(row=0, column=1, padx=5)
        
        ttk.Button(
            buttons_frame,
            text="Save Enhanced",
            command=self.save_enhanced
        ).grid(row=0, column=2, padx=5)
        
    def load_image(self):
        file_path = filedialog.askopenfilename(
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.tiff"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            # Load and convert image to grayscale
            self.original_image = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
            if self.original_image is None:
                messagebox.showerror("Error", "Failed to load image")
                return
                
            self.display_image(self.original_image, self.original_display)
            self.enhanced_image = None
            self.enhanced_display.configure(image='')
            
    def enhance_image(self):
        if self.original_image is None:
            messagebox.showwarning("Warning", "Please load an image first")
            return
            
        try:
            # Update PPAHE parameters
            self.ppahe = PPAHE(
                min_window=int(self.min_window_var.get()),
                max_window=int(self.max_window_var.get()),
                clip_limit=float(self.clip_limit_var.get())
            )
            
            # Process image
            start_time = time.time()
            self.enhanced_image = self.ppahe.enhance(self.original_image)
            processing_time = time.time() - start_time
            
            # Display result
            self.display_image(self.enhanced_image, self.enhanced_display)
            
            messagebox.showinfo(
                "Success",
                f"Enhancement completed in {processing_time:.2f} seconds"
            )
            
        except Exception as e:
            messagebox.showerror("Error", f"Enhancement failed: {str(e)}")
            
    def save_enhanced(self):
        if self.enhanced_image is None:
            messagebox.showwarning("Warning", "No enhanced image to save")
            return
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG files", "*.png"),
                ("JPEG files", "*.jpg"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            try:
                cv2.imwrite(file_path, self.enhanced_image)
                messagebox.showinfo("Success", "Image saved successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save image: {str(e)}")
                
    def display_image(self, img: np.ndarray, label: ttk.Label):
        # Resize image if too large while maintaining aspect ratio
        max_size = 400
        height, width = img.shape
        scale = min(max_size/width, max_size/height)
        
        if scale < 1:
            new_width = int(width * scale)
            new_height = int(height * scale)
            img = cv2.resize(img, (new_width, new_height))
            
        # Convert to PhotoImage
        img_pil = Image.fromarray(img)
        img_tk = ImageTk.PhotoImage(img_pil)
        
        # Update label
        label.configure(image=img_tk)
        label.image = img_tk  # Keep a reference

if __name__ == "__main__":
    root = tk.Tk()
    app = PPAHEApp(root)
    root.mainloop()