import torch
import torch.nn as nn
import torchvision.transforms as T
from PIL import Image
import numpy as np
import cv2
import easyocr
from pytesseract import image_to_data, Output
import pytesseract

def remove_text(image_array):
    # Convert to BGR for text detection
    bgr = cv2.cvtColor(image_array, cv2.COLOR_GRAY2BGR)
    
    # Use both EasyOCR and Tesseract for better coverage
    # EasyOCR detection
    reader = easyocr.Reader(['en'])
    results = reader.readtext(bgr, min_size=10, width_ths=0.5, contrast_ths=0.1)
    
    # Create mask
    mask = np.zeros(image_array.shape, dtype=np.uint8)
    
    # Add EasyOCR detections to mask
    for bbox, text, conf in results:
        if conf > 0.3:  # Lower confidence threshold
            points = np.array(bbox, np.int32)
            cv2.fillPoly(mask, [points], (255))
    
    # Add Tesseract detections to mask
    tess_data = pytesseract.image_to_data(image_array, output_type=Output.DICT)
    n_boxes = len(tess_data['text'])
    for i in range(n_boxes):
        if float(tess_data['conf'][i]) > 30:  # Filter confidence
            x, y, w, h = tess_data['left'][i], tess_data['top'][i], \
                        tess_data['width'][i], tess_data['height'][i]
            cv2.rectangle(mask, (x, y), (x + w, y + h), (255), -1)
    
    # Expand mask
    kernel = np.ones((7,7), np.uint8)  # Larger kernel
    mask = cv2.dilate(mask, kernel, iterations=2)
    
    # Multiple inpainting passes
    result = image_array.copy()
    for _ in range(2):  # Multiple passes
        result = cv2.inpaint(result, mask, 5, cv2.INPAINT_TELEA)
        result = cv2.inpaint(result, mask, 5, cv2.INPAINT_NS)  # Second algorithm
    
    return result

def dehaze_image(img):
    img_np = np.array(img)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    dark = cv2.erode(img_np, kernel)
    A = np.max(dark)
    transmission = 1 - 0.95 * dark / A
    transmission = cv2.GaussianBlur(transmission, (15, 15), 0)
    result = (img_np.astype(np.float32) - A) / np.maximum(transmission, 0.1) + A
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))

def enhance_image(image_path, output_path):
    image = Image.open(image_path).convert('L')
    img_array = np.array(image)
    
    # Remove text first
    img_array = remove_text(img_array)
    
    # Enhancement pipeline
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(img_array)
    
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    enhanced = cv2.filter2D(enhanced, -1, kernel)
    
    enhanced = Image.fromarray(enhanced)
    width, height = enhanced.size
    enhanced = enhanced.resize((width*2, height*2), Image.LANCZOS)
    defogged = dehaze_image(enhanced)
    
    p2, p98 = np.percentile(img_array, (2, 98))
    img_array = np.clip((defogged - p2) * 255.0 / (p98 - p2), 0, 255).astype(np.uint8)
    
    img_array = cv2.fastNlMeansDenoising(img_array)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(16,16))
    final = clahe.apply(img_array)
    
    Image.fromarray(final).save(output_path, quality=95)

if __name__ == "__main__":
    enhance_image("/content/1915.jpg", "/content/enhanced_photo.jpg")
