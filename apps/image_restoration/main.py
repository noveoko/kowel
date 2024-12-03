import torch
import torch.nn as nn
import torchvision.transforms as T
from PIL import Image
import numpy as np
import cv2
import easyocr
from basicsr.archs.rrdbnet_arch import RRDBNet
from basicsr.utils.download_util import load_file_from_url

# [Previous ContrastEnhancer class remains the same]

def remove_text(image):
    reader = easyocr.Reader(['en'])
    results = reader.readtext(np.array(image))
    
    mask = np.zeros(np.array(image).shape, dtype=np.uint8)
    for bbox, text, conf in results:
        if conf > 0.5:
            points = np.array(bbox, np.int32)
            cv2.fillPoly(mask, [points], (255))
            
    kernel = np.ones((5,5), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)
    result = cv2.inpaint(np.array(image), mask, 3, cv2.INPAINT_TELEA)
    return Image.fromarray(result)

def setup_real_esrgan():
    model = RRDBNet(num_in_ch=1, num_out_ch=1, num_feat=64, num_block=23, num_grow_ch=32)
    model_path = load_file_from_url(
        'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth',
        model_dir='weights'
    )
    loadnet = torch.load(model_path)
    model.load_state_dict(loadnet['params_ema'])
    model.eval()
    return model

def super_resolve(image, model):
    transform = T.ToTensor()
    img_tensor = transform(image).unsqueeze(0)
    with torch.no_grad():
        output = model(img_tensor)
    return T.ToPILImage()(output.squeeze())

def enhance_image(image_path, output_path, model_path=None):
    image = Image.open(image_path).convert('L')
    transform = T.Compose([T.ToTensor()])
    img_tensor = transform(image).unsqueeze(0)
    
    model = ContrastEnhancer()
    if model_path:
        model.load_state_dict(torch.load(model_path, 
                            map_location=torch.device('cpu' if not torch.cuda.is_available() else 'cuda')))
    
    model.eval()
    with torch.no_grad():
        enhanced = model(img_tensor)
    
    enhanced = enhanced.squeeze().numpy()
    enhanced = (enhanced * 255).astype(np.uint8)
    enhanced_image = Image.fromarray(enhanced)
    
    enhanced_array = np.array(enhanced_image)
    p2, p98 = np.percentile(enhanced_array, (2, 98))
    enhanced_array = np.clip((enhanced_array - p2) * 255.0 / (p98 - p2), 0, 255).astype(np.uint8)
    enhanced_image = Image.fromarray(enhanced_array)
    
    defogged = dehaze_image(enhanced_image)
    no_text = remove_text(defogged)
    final_image = super_resolve(no_text, sr_model)
    final_image.save(output_path)

if __name__ == "__main__":
    enhance_image("old_photo.jpg", "enhanced_photo.jpg")
