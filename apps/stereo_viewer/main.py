import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import os
from tkinter import font
import tkinter.dnd as dnd

class DragDropFrame(tk.Frame):
    def __init__(self, master, text, callback):
        super().__init__(master, relief="groove", borderwidth=2)
        self.callback = callback
        
        # Configure style
        self.configure(bg="#f0f0f0")
        self.label = tk.Label(
            self, 
            text=text,
            bg="#f0f0f0",
            font=('Arial', 12)
        )
        self.label.pack(expand=True, fill='both', padx=20, pady=20)
        
        # Bind drag and drop events
        self.drop_target = dnd.DropTarget(self, {
            'text/uri-list': lambda event: self.handle_drop(event),
            'DND_Files': lambda event: self.handle_drop(event)
        })
        
        # Bind click event
        self.bind("<Button-1>", lambda e: self.callback())
        self.label.bind("<Button-1>", lambda e: self.callback())
    
    def handle_drop(self, event):
        filepath = event.data.strip()
        if filepath.startswith('{'):  # Windows fix
            filepath = filepath[1:-1]
        self.callback(filepath)
        
    def highlight(self, highlight=True):
        self.configure(bg="#e0e0e0" if highlight else "#f0f0f0")
        self.label.configure(bg="#e0e0e0" if highlight else "#f0f0f0")

class StereoImageViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("3D Image Creator")
        self.root.geometry("1200x800")
        self.root.configure(bg='white')
        
        # Image holders
        self.left_image = None
        self.right_image = None
        self.preview_photo = None
        
        # Create GUI elements
        self.create_widgets()
        
        # Target dimensions
        self.target_width = 1920
        self.target_height = 1080
        
        # Bind keyboard shortcuts
        self.root.bind('<Control-s>', lambda e: self.save_stereo())
        self.root.bind('<Control-g>', lambda e: self.generate_stereo())
        
    def create_widgets(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top frame for image selection
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Create drag & drop frames
        self.left_frame = DragDropFrame(
            top_frame,
            "Drop Left Image Here\nor Click to Browse",
            self.load_left_image
        )
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        self.right_frame = DragDropFrame(
            top_frame,
            "Drop Right Image Here\nor Click to Browse",
            self.load_right_image
        )
        self.right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        # Preview frame
        preview_container = ttk.LabelFrame(main_frame, text="Preview", padding="5")
        preview_container.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.preview_label = ttk.Label(preview_container)
        self.preview_label.pack(fill=tk.BOTH, expand=True)
        
        # Bottom controls frame
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Status label with better styling
        self.status_label = ttk.Label(
            controls_frame,
            text="Drop or select left and right images to begin",
            font=('Arial', 10)
        )
        self.status_label.pack(side=tk.LEFT)
        
        # Buttons with icons (you can add icons later)
        ttk.Button(
            controls_frame,
            text="Generate 3D View (Ctrl+G)",
            command=self.generate_stereo
        ).pack(side=tk.RIGHT, padx=5)
        
        ttk.Button(
            controls_frame,
            text="Save (Ctrl+S)",
            command=self.save_stereo
        ).pack(side=tk.RIGHT, padx=5)
        
    def load_image(self, path):
        try:
            return Image.open(path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image: {str(e)}")
            return None
            
    def load_left_image(self, path=None):
        if path is None:
            path = filedialog.askopenfilename(
                filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp")]
            )
        if path:
            self.left_image = self.load_image(path)
            if self.left_image:
                self.left_frame.label.configure(
                    text=f"Left Image: {os.path.basename(path)}"
                )
                self.update_status()
                self.auto_generate_preview()
    
    def load_right_image(self, path=None):
        if path is None:
            path = filedialog.askopenfilename(
                filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp")]
            )
        if path:
            self.right_image = self.load_image(path)
            if self.right_image:
                self.right_frame.label.configure(
                    text=f"Right Image: {os.path.basename(path)}"
                )
                self.update_status()
                self.auto_generate_preview()
    
    def update_status(self):
        if self.left_image and self.right_image:
            self.status_label.configure(
                text="Ready to generate 3D view! Press Ctrl+G or click Generate"
            )
        elif self.left_image:
            self.status_label.configure(text="Now select the right image...")
        elif self.right_image:
            self.status_label.configure(text="Now select the left image...")
    
    def auto_generate_preview(self):
        if self.left_image and self.right_image:
            self.generate_stereo()
    
    def generate_stereo(self):
        if not self.left_image or not self.right_image:
            messagebox.showinfo(
                "Missing Images",
                "Please load both left and right images first"
            )
            return
        
        # Calculate dimensions
        single_width = self.target_width // 2
        aspect_ratio = self.left_image.height / self.left_image.width
        new_height = int(single_width * aspect_ratio)
        
        # Resize images
        left_resized = self.left_image.resize(
            (single_width, new_height),
            Image.Resampling.LANCZOS
        )
        right_resized = self.right_image.resize(
            (single_width, new_height),
            Image.Resampling.LANCZOS
        )
        
        # Create combined image
        self.combined = Image.new('RGB', (self.target_width, new_height))
        self.combined.paste(left_resized, (0, 0))
        self.combined.paste(right_resized, (single_width, 0))
        
        # Show preview
        self.update_preview()
        self.status_label.configure(
            text="3D view generated! Press Ctrl+S to save..."
        )
    
    def update_preview(self):
        if not hasattr(self, 'combined'):
            return
            
        # Calculate preview size maintaining aspect ratio
        preview_width = 1000  # Maximum preview width
        preview_height = int(
            preview_width * self.combined.height / self.combined.width
        )
        
        # Resize for preview
        preview = self.combined.resize(
            (preview_width, preview_height),
            Image.Resampling.LANCZOS
        )
        self.preview_photo = ImageTk.PhotoImage(preview)
        self.preview_label.configure(image=self.preview_photo)
    
    def save_stereo(self):
        if not hasattr(self, 'combined'):
            messagebox.showinfo(
                "Generate First",
                "Please generate the 3D view before saving"
            )
            return
            
        save_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png")],
            title="Save 3D Image"
        )
        
        if save_path:
            try:
                self.combined.save(save_path, "PNG")
                self.status_label.configure(
                    text=f"Saved successfully to {os.path.basename(save_path)}"
                )
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = StereoImageViewer(root)
    root.mainloop()