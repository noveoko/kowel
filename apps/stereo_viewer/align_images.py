import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
import os
from pathlib import Path
import matplotlib.pyplot as plt

class StereoImageAligner:
    def __init__(self):
        self.left_img = None
        self.right_img = None
        self.aligned_left = None
        self.aligned_right = None
        self.sift = cv2.SIFT_create()
        
    def load_images(self, left_path, right_path):
        """Load images in both BGR (for OpenCV) and RGB (for display) formats."""
        self.left_img = cv2.imread(left_path)
        self.right_img = cv2.imread(right_path)
        if self.left_img is None or self.right_img is None:
            raise ValueError("Failed to load one or both images")
            
        # Store RGB versions for display
        self.left_rgb = cv2.cvtColor(self.left_img, cv2.COLOR_BGR2RGB)
        self.right_rgb = cv2.cvtColor(self.right_img, cv2.COLOR_BGR2RGB)
        
    def detect_features(self):
        """Detect SIFT features in both images."""
        gray_left = cv2.cvtColor(self.left_img, cv2.COLOR_BGR2GRAY)
        gray_right = cv2.cvtColor(self.right_img, cv2.COLOR_BGR2GRAY)
        
        kp_left, desc_left = self.sift.detectAndCompute(gray_left, None)
        kp_right, desc_right = self.sift.detectAndCompute(gray_right, None)
        
        return kp_left, desc_left, kp_right, desc_right
        
    def match_features(self, desc_left, desc_right):
        """Match features between images using FLANN."""
        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        search_params = dict(checks=50)
        
        flann = cv2.FlannBasedMatcher(index_params, search_params)
        matches = flann.knnMatch(desc_left, desc_right, k=2)
        
        # Apply ratio test
        good_matches = []
        for m, n in matches:
            if m.distance < 0.7 * n.distance:
                good_matches.append(m)
                
        return good_matches
        
    def align_images(self):
        """Align images using feature matching and homography."""
        # Detect features
        kp_left, desc_left, kp_right, desc_right = self.detect_features()
        
        # Match features
        good_matches = self.match_features(desc_left, desc_right)
        
        if len(good_matches) < 4:
            raise ValueError("Not enough matching features found")
            
        # Get matching points
        src_pts = np.float32([kp_left[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp_right[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        
        # Calculate homography
        H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        
        # Warp left image to align with right image
        height, width = self.right_img.shape[:2]
        self.aligned_left = cv2.warpPerspective(self.left_img, H, (width, height))
        self.aligned_right = self.right_img.copy()
        
        # Convert to RGB for display
        self.aligned_left_rgb = cv2.cvtColor(self.aligned_left, cv2.COLOR_BGR2RGB)
        self.aligned_right_rgb = cv2.cvtColor(self.aligned_right, cv2.COLOR_BGR2RGB)
        
    def find_optimal_crop(self):
        """Find the optimal crop region that contains valid image data in both images."""
        # Create masks for valid (non-black) regions
        gray_left = cv2.cvtColor(self.aligned_left, cv2.COLOR_BGR2GRAY)
        gray_right = cv2.cvtColor(self.aligned_right, cv2.COLOR_BGR2GRAY)
        
        mask_left = gray_left > 0
        mask_right = gray_right > 0
        
        # Find common valid region
        common_mask = mask_left & mask_right
        
        # Find bounding box of common region
        rows = np.any(common_mask, axis=1)
        cols = np.any(common_mask, axis=0)
        ymin, ymax = np.where(rows)[0][[0, -1]]
        xmin, xmax = np.where(cols)[0][[0, -1]]
        
        return (xmin, ymin, xmax, ymax)
        
    def crop_aligned_images(self):
        """Crop both images to the optimal region."""
        xmin, ymin, xmax, ymax = self.find_optimal_crop()
        
        self.aligned_left = self.aligned_left[ymin:ymax, xmin:xmax]
        self.aligned_right = self.aligned_right[ymin:ymax, xmin:xmax]
        
        # Update RGB versions
        self.aligned_left_rgb = cv2.cvtColor(self.aligned_left, cv2.COLOR_BGR2RGB)
        self.aligned_right_rgb = cv2.cvtColor(self.aligned_right, cv2.COLOR_BGR2RGB)
        
    def save_aligned_images(self, left_output_path, right_output_path):
        """Save the aligned and cropped images."""
        cv2.imwrite(left_output_path, self.aligned_left)
        cv2.imwrite(right_output_path, self.aligned_right)

class AlignerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Stereo Image Alignment Tool")
        self.aligner = StereoImageAligner()
        self.create_widgets()
        
    def create_widgets(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Input frame
        input_frame = ttk.LabelFrame(main_frame, text="Input Images", padding="5")
        input_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(input_frame, text="Load Left Image", command=self.load_left).pack(side=tk.LEFT, padx=5)
        ttk.Button(input_frame, text="Load Right Image", command=self.load_right).pack(side=tk.LEFT, padx=5)
        ttk.Button(input_frame, text="Align Images", command=self.align_images).pack(side=tk.LEFT, padx=5)
        ttk.Button(input_frame, text="Save Aligned Images", command=self.save_images).pack(side=tk.LEFT, padx=5)
        
        # Preview frame
        preview_frame = ttk.LabelFrame(main_frame, text="Preview", padding="5")
        preview_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create canvas for image preview
        self.canvas = tk.Canvas(preview_frame)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Status bar
        self.status_var = tk.StringVar(value="Load left and right images to begin")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var)
        status_bar.pack(fill=tk.X, pady=(5, 0))
        
    def load_left(self):
        path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp")])
        if path:
            self.left_path = path
            self.status_var.set("Left image loaded")
            self.update_preview()
            
    def load_right(self):
        path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp")])
        if path:
            self.right_path = path
            self.status_var.set("Right image loaded")
            self.update_preview()
            
    def align_images(self):
        if not hasattr(self, 'left_path') or not hasattr(self, 'right_path'):
            self.status_var.set("Please load both images first")
            return
            
        try:
            self.status_var.set("Aligning images...")
            self.root.update()
            
            # Load and align images
            self.aligner.load_images(self.left_path, self.right_path)
            self.aligner.align_images()
            self.aligner.crop_aligned_images()
            
            self.status_var.set("Images aligned successfully")
            self.update_preview(show_aligned=True)
            
        except Exception as e:
            self.status_var.set(f"Error during alignment: {str(e)}")
            
    def save_images(self):
        if not hasattr(self.aligner, 'aligned_left') or not hasattr(self.aligner, 'aligned_right'):
            self.status_var.set("Please align images first")
            return
            
        # Get directory for saving
        save_dir = filedialog.askdirectory(title="Select directory to save aligned images")
        if save_dir:
            try:
                # Generate output paths
                base_left = Path(self.left_path).stem
                base_right = Path(self.right_path).stem
                left_output = os.path.join(save_dir, f"{base_left}_aligned.png")
                right_output = os.path.join(save_dir, f"{base_right}_aligned.png")
                
                # Save images
                self.aligner.save_aligned_images(left_output, right_output)
                self.status_var.set("Images saved successfully")
                
            except Exception as e:
                self.status_var.set(f"Error saving images: {str(e)}")
                
    def update_preview(self, show_aligned=False):
        try:
            if show_aligned and hasattr(self.aligner, 'aligned_left_rgb'):
                left_img = self.aligner.aligned_left_rgb
                right_img = self.aligner.aligned_right_rgb
            elif hasattr(self.aligner, 'left_rgb'):
                left_img = self.aligner.left_rgb
                right_img = self.aligner.right_rgb
            else:
                return
                
            # Create side-by-side preview
            height = min(left_img.shape[0], right_img.shape[0])
            width = min(left_img.shape[1], right_img.shape[1])
            
            # Resize images to same size
            left_img = cv2.resize(left_img, (width, height))
            right_img = cv2.resize(right_img, (width, height))
            
            # Combine images
            combined = np.hstack((left_img, right_img))
            
            # Convert to PhotoImage
            combined_img = Image.fromarray(combined)
            
            # Resize for display if too large
            display_width = 1000  # Maximum display width
            if combined_img.width > display_width:
                ratio = display_width / combined_img.width
                display_height = int(combined_img.height * ratio)
                combined_img = combined_img.resize((display_width, display_height))
                
            self.photo = ImageTk.PhotoImage(combined_img)
            
            # Update canvas
            self.canvas.delete("all")
            self.canvas.config(width=combined_img.width, height=combined_img.height)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
            
        except Exception as e:
            self.status_var.set(f"Error updating preview: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = AlignerGUI(root)
    root.mainloop()