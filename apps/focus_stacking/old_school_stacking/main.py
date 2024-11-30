import os
from pathlib import Path
import numpy as np
import cv2
from typing import List, Tuple
from IPython.display import display, Image
import ipywidgets as widgets
import tifffile
from scipy import ndimage

class ImageProcessor:
    def __init__(self, preserve_quality=True, debug=False):
        self.preserve_quality = preserve_quality
        self.debug = debug
        
    def enhance_image(self, img: np.ndarray) -> np.ndarray:
        """
        Enhanced image processing with quality preservation.
        """
        # Store original dtype and range
        original_dtype = img.dtype
        dtype_max = 255 if original_dtype == np.uint8 else 65535
        
        # Convert to float for processing
        img_float = img.astype(np.float32) / dtype_max
        
        # Bilateral filter for edge-preserving smoothing
        if len(img_float.shape) == 3:
            denoised = np.zeros_like(img_float)
            for i in range(3):
                denoised[:,:,i] = cv2.bilateralFilter(
                    img_float[:,:,i], d=5, sigmaColor=0.1, sigmaSpace=5)
        else:
            denoised = cv2.bilateralFilter(img_float, d=5, sigmaColor=0.1, sigmaSpace=5)
        
        # Adaptive contrast enhancement
        if len(denoised.shape) == 3:
            lab = cv2.cvtColor((denoised * 255).astype(np.uint8), cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            l_clahe = clahe.apply(l)
            enhanced_lab = cv2.merge([l_clahe, a, b])
            enhanced = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
            enhanced = enhanced.astype(np.float32) / 255
        else:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply((denoised * 255).astype(np.uint8)).astype(np.float32) / 255
        
        # Edge enhancement using unsharp masking
        gaussian = ndimage.gaussian_filter(enhanced, sigma=1)
        unsharp_mask = enhanced - gaussian
        enhanced = enhanced + 0.5 * unsharp_mask
        
        # Clip values and convert back to original dtype
        enhanced = np.clip(enhanced * dtype_max, 0, dtype_max).astype(original_dtype)
        
        if self.debug:
            cv2.imwrite('debug_enhanced.tif', enhanced)
            
        return enhanced

    def align_image_pair(self, ref_img: np.ndarray, moving_img: np.ndarray) -> Tuple[np.ndarray, bool]:
        """
        Align a pair of images with improved feature matching.
        """
        # Convert to grayscale for feature detection
        ref_gray = cv2.cvtColor(ref_img, cv2.COLOR_BGR2GRAY) if len(ref_img.shape) == 3 else ref_img
        moving_gray = cv2.cvtColor(moving_img, cv2.COLOR_BGR2GRAY) if len(moving_img.shape) == 3 else moving_img
        
        # Multi-scale feature detection
        sift = cv2.SIFT_create(nfeatures=10000)
        kp1, des1 = sift.detectAndCompute(ref_gray, None)
        kp2, des2 = sift.detectAndCompute(moving_gray, None)
        
        if des1 is None or des2 is None:
            return None, False
            
        # Feature matching with ratio test
        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        search_params = dict(checks=50)
        flann = cv2.FlannBasedMatcher(index_params, search_params)
        
        matches = flann.knnMatch(des1, des2, k=2)
        good_matches = []
        for m, n in matches:
            if m.distance < 0.7 * n.distance:
                good_matches.append(m)
                
        if len(good_matches) < 10:
            return None, False
            
        # Get matching points
        src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        
        # Calculate homography with RANSAC
        H, mask = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 5.0)
        
        if H is None:
            return None, False
            
        # Warp image with border extension
        h, w = ref_img.shape[:2]
        aligned = cv2.warpPerspective(
            moving_img, H, (w, h),
            flags=cv2.INTER_LANCZOS4,
            borderMode=cv2.BORDER_REPLICATE
        )
        
        return aligned, True

    def blend_images(self, images: List[np.ndarray]) -> np.ndarray:
        """
        Blend aligned images using weighted fusion.
        """
        if not images:
            return None
            
        # Convert to float32 for processing
        imgs = [img.astype(np.float32) for img in images]
        weights = []
        
        for img in imgs:
            # Calculate weight map
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
            
            # Multiple focus measures
            lap = np.absolute(cv2.Laplacian(gray, cv2.CV_32F))
            sobel_x = np.absolute(cv2.Sobel(gray, cv2.CV_32F, 1, 0))
            sobel_y = np.absolute(cv2.Sobel(gray, cv2.CV_32F, 0, 1))
            
            # Combine measures
            weight = lap + 0.5 * (sobel_x + sobel_y)
            
            # Gaussian blur to reduce noise
            weight = cv2.GaussianBlur(weight, (3,3), 0)
            weights.append(weight)
            
        # Normalize weights
        weights = np.array(weights)
        weight_sum = np.sum(weights, axis=0)
        weights = np.divide(weights, weight_sum, where=weight_sum != 0)
        
        # Weighted blend
        result = np.zeros_like(imgs[0])
        for img, weight in zip(imgs, weights):
            weight = np.expand_dims(weight, -1) if len(img.shape) == 3 else weight
            result += img * weight
            
        return result.astype(images[0].dtype)

def process_directory(directory: str, output_filename: str = 'result.tif', debug: bool = False):
    """
    Process all images in a directory with quality preservation.
    """
    processor = ImageProcessor(preserve_quality=True, debug=debug)
    
    # Load images
    image_files = sorted([f for f in os.listdir(directory) if f.lower().endswith(
        ('.tif', '.tiff', '.png', '.jpg', '.jpeg', '.bmp'))])
    
    if not image_files:
        print("No images found in directory")
        return
        
    images = []
    for f in image_files:
        path = os.path.join(directory, f)
        try:
            if f.lower().endswith(('.tif', '.tiff')):
                img = tifffile.imread(path)
            else:
                img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
                
            if img is not None:
                # Convert to BGR if needed
                if len(img.shape) == 2:
                    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
                elif img.shape[-1] == 4:
                    img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                    
                # Enhance image
                img = processor.enhance_image(img)
                images.append(img)
                print(f"Processed: {f}")
        except Exception as e:
            print(f"Error processing {f}: {str(e)}")
            
    if not images:
        print("No valid images could be processed")
        return
        
    # Align images
    print("\nAligning images...")
    reference = images[0]
    aligned_images = [reference]
    
    for i, img in enumerate(images[1:], 1):
        print(f"Aligning image {i}/{len(images)-1}")
        aligned, success = processor.align_image_pair(reference, img)
        if success:
            aligned_images.append(aligned)
            if debug:
                cv2.imwrite(f'debug_aligned_{i}.tif', aligned)
        else:
            print(f"Failed to align image {i}")
            
    if len(aligned_images) < 2:
        print("Insufficient aligned images for blending")
        return
        
    # Blend images
    print("\nBlending images...")
    result = processor.blend_images(aligned_images)
    
    # Save result
    if result is not None:
        # Save in high quality
        if output_filename.lower().endswith(('.tif', '.tiff')):
            tifffile.imwrite(output_filename, result)
        else:
            cv2.imwrite(output_filename, result, [cv2.IMWRITE_JPEG_QUALITY, 100])
        print(f"\nSaved result to {output_filename}")
        
        # Display result
        rgb_result = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
        cv2.imwrite('temp_display.jpg', cv2.cvtColor(rgb_result, cv2.COLOR_RGB2BGR))
        display(Image(filename='temp_display.jpg'))
        os.remove('temp_display.jpg')
    else:
        print("Failed to generate result")

# Create widgets
dir_input = widgets.Text(
    value='',
    placeholder='Enter directory path',
    description='Directory:',
    style={'description_width': 'initial'}
)

debug_checkbox = widgets.Checkbox(
    value=False,
    description='Debug mode',
    indent=False
)

output_filename = widgets.Text(
    value='result.tif',
    placeholder='Enter output filename',
    description='Output:',
    style={'description_width': 'initial'}
)

def on_process(b):
    process_directory(dir_input.value, output_filename.value, debug_checkbox.value)

process_button = widgets.Button(description='Process Images')
process_button.on_click(on_process)

# Display widgets
display(widgets.VBox([dir_input, output_filename, debug_checkbox, process_button]))
