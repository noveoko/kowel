import cv2
import numpy as np
import torch
from ultralytics import YOLO
import argparse
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load YOLOv8 model
model = YOLO('yolov8n.pt')  # Using yolov8n.pt as default model

def detect_objects(image, confidence_threshold=0.5):
    """
    Detect objects in an image using YOLOv8.
    
    Args:
        image: Input image
        confidence_threshold: Minimum confidence score for detections
    
    Returns:
        numpy.ndarray: Array of detections [x1, y1, x2, y2, confidence, class]
    """
    results = model(image)[0]  # Get first image results
    detections = []
    
    for det in results.boxes.data.cpu().numpy():
        if det[4] > confidence_threshold:  # Check confidence threshold
            detections.append(det)
    
    return np.array(detections) if detections else np.array([])

def calculate_centroid(detections):
    """
    Calculate the centroid of detected objects.
    
    Args:
        detections: Array of object detections
    
    Returns:
        numpy.ndarray: Centroid coordinates [x, y] or None if no detections
    """
    if len(detections) == 0:
        return None
    
    x_centers = (detections[:, 0] + detections[:, 2]) / 2
    y_centers = (detections[:, 1] + detections[:, 3]) / 2
    return np.mean(np.column_stack((x_centers, y_centers)), axis=0)

def align_images(images, confidence_threshold=0.5):
    """
    Align multiple images based on detected object centroids.
    
    Args:
        images: List of input images
        confidence_threshold: Minimum confidence score for detections
    
    Returns:
        list: Aligned images
    """
    logger.info("Starting image alignment...")
    
    ref_detections = detect_objects(images[0], confidence_threshold)
    ref_centroid = calculate_centroid(ref_detections)
    
    if ref_centroid is None:
        raise ValueError("No reliable objects detected in the reference image.")
    
    aligned_images = []
    for i, img in enumerate(images):
        logger.info(f"Aligning image {i+1}/{len(images)}")
        detections = detect_objects(img, confidence_threshold)
        centroid = calculate_centroid(detections)
        
        if centroid is None:
            raise ValueError(f"No reliable objects detected in image {i+1}")
        
        translation = ref_centroid - centroid
        M = np.float32([[1, 0, translation[0]], [0, 1, translation[1]]])
        aligned_img = cv2.warpAffine(img, M, (img.shape[1], img.shape[0]))
        aligned_images.append(aligned_img)
    
    return aligned_images

def generate_focus_map(image, kernel_size=5):
    """
    Generate a focus map using Laplacian operator.
    
    Args:
        image: Input image
        kernel_size: Size of the Gaussian kernel for noise reduction
    
    Returns:
        numpy.ndarray: Focus map
    """
    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(image, (kernel_size, kernel_size), 0)
    
    # Calculate Laplacian
    laplacian = cv2.Laplacian(blurred, cv2.CV_64F)
    
    # Take absolute value and convert to uint8
    focus_map = cv2.convertScaleAbs(laplacian)
    
    # Enhance contrast of the focus map
    focus_map = cv2.normalize(focus_map, None, 0, 255, cv2.NORM_MINMAX)
    
    return focus_map

def focus_stacking(images, block_size=8):
    """
    Perform focus stacking on aligned images.
    
    Args:
        images: List of aligned images
        block_size: Size of blocks for local contrast analysis
    
    Returns:
        numpy.ndarray: Focus-stacked image
    """
    logger.info("Starting focus stacking...")
    
    if not images:
        raise ValueError("No images provided for focus stacking")
    
    # Convert images to grayscale for focus map generation
    gray_images = [cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) for img in images]
    
    # Generate focus maps
    focus_maps = [generate_focus_map(img) for img in gray_images]
    
    # Initialize result
    height, width = images[0].shape[:2]
    result = np.zeros_like(images[0], dtype=np.float64)
    weights = np.zeros((height, width), dtype=np.float64)
    
    # Process image blocks
    for y in range(0, height, block_size):
        for x in range(0, width, block_size):
            # Define block region
            y_end = min(y + block_size, height)
            x_end = min(x + block_size, width)
            
            # Find the image with maximum focus for this block
            max_focus = -np.inf
            best_image = None
            
            for img, focus_map in zip(images, focus_maps):
                focus_val = np.mean(focus_map[y:y_end, x:x_end])
                if focus_val > max_focus:
                    max_focus = focus_val
                    best_image = img
            
            # Add the best block to the result
            result[y:y_end, x:x_end] = best_image[y:y_end, x:x_end]
            weights[y:y_end, x:x_end] = 1
    
    # Normalize result
    result = np.clip(result / np.maximum(weights[:, :, np.newaxis], 1), 0, 255).astype(np.uint8)
    
    return result

def main():
    """Main function to process images and create focus-stacked result."""
    parser = argparse.ArgumentParser(description='Focus stacking with object detection and alignment')
    parser.add_argument('input_dir', type=str, help='Directory containing input images')
    parser.add_argument('--output', type=str, default='focus_stacked.jpg', help='Output image path')
    parser.add_argument('--confidence', type=float, default=0.5, help='Confidence threshold for object detection')
    parser.add_argument('--block-size', type=int, default=8, help='Block size for focus stacking')
    args = parser.parse_args()
    
    try:
        # Get all image files from input directory
        image_paths = list(Path(args.input_dir).glob('*.[jJ][pP][gG]'))
        image_paths.extend(Path(args.input_dir).glob('*.[pP][nN][gG]'))
        
        if not image_paths:
            raise ValueError(f"No images found in {args.input_dir}")
        
        logger.info(f"Found {len(image_paths)} images")
        
        # Load images
        images = []
        for path in image_paths:
            img = cv2.imread(str(path))
            if img is None:
                raise ValueError(f"Could not load image: {path}")
            images.append(img)
        
        # Align images
        aligned_images = align_images(images, args.confidence)
        
        # Perform focus stacking
        stacked_image = focus_stacking(aligned_images, args.block_size)
        
        # Save result
        cv2.imwrite(args.output, stacked_image)
        logger.info(f"Focus-stacked image saved as '{args.output}'")
        
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        raise

if __name__ == "__main__":
    main()