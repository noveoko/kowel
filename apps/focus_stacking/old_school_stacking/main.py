import os
from pathlib import Path
import numpy as np
import cv2
from typing import List, Tuple
from IPython.display import display, Image
import ipywidgets as widgets
import tifffile

def enhance_image(img: np.ndarray) -> np.ndarray:
    """
    Enhance image quality with multiple preprocessing steps.
    """
    # Convert to 8-bit if needed
    if img.dtype != np.uint8:
        img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    
    # Denoise
    denoised = cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)
    
    # Convert to LAB color space for better contrast enhancement
    lab = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    
    # CLAHE on L channel
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    l_clahe = clahe.apply(l)
    
    # Merge channels back
    enhanced_lab = cv2.merge([l_clahe, a, b])
    enhanced = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
    
    # Sharpen
    kernel = np.array([[-1,-1,-1],
                      [-1, 9,-1],
                      [-1,-1,-1]])
    sharpened = cv2.filter2D(enhanced, -1, kernel)
    
    return sharpened

def load_images(directory: str) -> List[np.ndarray]:
    """Load and enhance all images from the specified directory."""
    image_extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp'}
    images = []
    
    for file in sorted(os.listdir(directory)):
        if Path(file).suffix.lower() in image_extensions:
            img_path = os.path.join(directory, file)
            
            try:
                if file.lower().endswith(('.tiff', '.tif')):
                    img = tifffile.imread(img_path)
                else:
                    img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)
                
                if img is None:
                    print(f"Failed to load {file}")
                    continue
                
                # Convert to BGR if grayscale
                if len(img.shape) == 2:
                    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
                elif img.shape[-1] == 4:
                    img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
                # Enhance image
                enhanced = enhance_image(img)
                images.append(enhanced)
                print(f"Loaded and enhanced: {file}")
                
            except Exception as e:
                print(f"Error processing {file}: {str(e)}")
                continue
    
    return images

def detect_and_match_features(img1: np.ndarray, img2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Detect and match features between two images using combination of detectors."""
    # Convert to grayscale
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    
    # Create detectors
    orb = cv2.ORB_create(nfeatures=10000, scaleFactor=1.2, nlevels=8)
    brisk = cv2.BRISK_create()
    
    # Detect keypoints and compute descriptors with both detectors
    kp1_orb, des1_orb = orb.detectAndCompute(gray1, None)
    kp2_orb, des2_orb = orb.detectAndCompute(gray2, None)
    kp1_brisk, des1_brisk = brisk.detectAndCompute(gray1, None)
    kp2_brisk, des2_brisk = brisk.detectAndCompute(gray2, None)
    
    if (des1_orb is None and des1_brisk is None) or (des2_orb is None and des2_brisk is None):
        return None, None
    
    matches = []
    
    # Match ORB features
    if des1_orb is not None and des2_orb is not None:
        bf_orb = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches_orb = bf_orb.match(des1_orb, des2_orb)
        matches.extend([(m, kp1_orb, kp2_orb) for m in matches_orb])
    
    # Match BRISK features
    if des1_brisk is not None and des2_brisk is not None:
        bf_brisk = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches_brisk = bf_brisk.match(des1_brisk, des2_brisk)
        matches.extend([(m, kp1_brisk, kp2_brisk) for m in matches_brisk])
    
    if not matches:
        return None, None
    
    # Sort matches by distance
    matches = sorted(matches, key=lambda x: x[0].distance)
    
    # Extract matched keypoints
    src_pts = np.float32([m[1][m[0].queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([m[2][m[0].trainIdx].pt for m in matches]).reshape(-1, 1, 2)
    
    return src_pts, dst_pts

def align_images(images: List[np.ndarray]) -> List[np.ndarray]:
    """Align all images to the first image using feature matching."""
    if not images:
        return []
    
    reference_img = images[0]
    aligned_images = [reference_img]
    
    for i, img in enumerate(images[1:], 1):
        print(f"Aligning image {i}/{len(images)-1}")
        
        src_pts, dst_pts = detect_and_match_features(reference_img, img)
        
        if src_pts is None or dst_pts is None or len(src_pts) < 4:
            print(f"Not enough matches in image {i}")
            continue
        
        # Find homography with RANSAC
        H, mask = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 5.0)
        
        if H is None:
            print(f"Could not find homography for image {i}")
            continue
        
        # Warp image with border extension
        h, w = reference_img.shape[:2]
        aligned = cv2.warpPerspective(img, H, (w, h), borderMode=cv2.BORDER_REPLICATE)
        aligned_images.append(aligned)
        print(f"Successfully aligned image {i}")
    
    return aligned_images

def focus_stack(images: List[np.ndarray]) -> np.ndarray:
    """Perform focus stacking with enhanced blending."""
    if not images:
        return None
    
    print("Starting focus stacking...")
    weights = []
    
    for i, img in enumerate(images):
        print(f"Processing image {i+1}/{len(images)}")
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Calculate weight map using multiple metrics
        lap = np.absolute(cv2.Laplacian(gray, cv2.CV_64F))
        sobel_x = np.absolute(cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3))
        sobel_y = np.absolute(cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3))
        
        # Combine metrics
        weight = lap + 0.5*(sobel_x + sobel_y)
        
        # Gaussian blur to reduce noise in weight map
        weight = cv2.GaussianBlur(weight, (3,3), 0)
        weights.append(weight)
    
    print("Computing weighted blend...")
    weights = np.array(weights)
    max_response = np.argmax(weights, axis=0)
    
    output = np.zeros_like(images[0])
    h, w = output.shape[:2]
    
    # Use integer indexing for the final image composition
    max_response = max_response.astype(np.int32)
    
    # Create blended output
    for y in range(h):
        for x in range(w):
            output[y, x] = images[max_response[y, x]][y, x]
    
    # Final enhancement
    output = enhance_image(output)
    
    return output

def process_images(directory: str, output_filename: str = 'result.jpg'):
    """Main processing function."""
    print("Loading and enhancing images...")
    images = load_images(directory)
    if not images:
        print("No valid images found")
        return
    
    print(f"Found {len(images)} images")
    aligned_images = align_images(images)
    
    if len(aligned_images) < 2:
        print("Failed to align images")
        return
    
    result = focus_stack(aligned_images)
    if result is None:
        print("Focus stacking failed")
        return
    
    # Save result
    if output_filename.lower().endswith(('.tiff', '.tif')):
        tifffile.imwrite(output_filename, result)
    else:
        cv2.imwrite(output_filename, result)
    print(f"Saved result to {output_filename}")
    
    # Display result
    rgb_result = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
    cv2.imwrite('temp_result.jpg', rgb_result)
    display(Image(filename='temp_result.jpg'))
    os.remove('temp_result.jpg')

# Create widget
dir_input = widgets.Text(
    value='',
    placeholder='Enter directory path',
    description='Directory:',
    style={'description_width': 'initial'}
)

def on_dir_enter(change):
    if change['type'] == 'submit':
        print(f"Processing directory: {change['new']}")
        process_images(change['new'])

dir_input.on_submit(on_dir_enter)
display(dir_input)
