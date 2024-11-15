import numpy as np
import cv2
import torch
import torch.nn as nn
import torchvision.transforms as transforms
import torchvision.models as models
from PIL import Image
import matplotlib.pyplot as plt

class CrossPerspectiveMatcher:
    def __init__(self):
        # Initialize SIFT detector
        self.sift = cv2.SIFT_create()
        
        # Load pretrained ResNet model for feature extraction
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = models.resnet50(pretrained=True)
        self.model = nn.Sequential(*list(self.model.children())[:-1])  # Remove classification layer
        self.model.to(self.device)
        self.model.eval()
        
        # Define image transforms
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                               std=[0.229, 0.224, 0.225])
        ])
    
    def extract_deep_features(self, image):
        """Extract deep features using ResNet"""
        img = self.transform(Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)))
        img = img.unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            features = self.model(img)
        
        return features.cpu().numpy().reshape(-1)
    
    def find_sift_correspondences(self, img1, img2):
        """Find corresponding points using SIFT"""
        # Convert images to grayscale
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        
        # Detect keypoints and compute descriptors
        keypoints1, descriptors1 = self.sift.detectAndCompute(gray1, None)
        keypoints2, descriptors2 = self.sift.detectAndCompute(gray2, None)
        
        # Match features using FLANN
        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        search_params = dict(checks=50)
        flann = cv2.FlannBasedMatcher(index_params, search_params)
        
        matches = flann.knnMatch(descriptors1, descriptors2, k=2)
        
        # Apply ratio test
        good_matches = []
        for m, n in matches:
            if m.distance < 0.7 * n.distance:
                good_matches.append(m)
        
        return keypoints1, keypoints2, good_matches
    
    def compute_similarity_score(self, features1, features2):
        """Compute cosine similarity between deep features"""
        return np.dot(features1, features2) / (np.linalg.norm(features1) * np.linalg.norm(features2))
    
    def find_correspondences(self, aerial_photo, street_view_photo):
        """Main method to find correspondences between aerial and street view images"""
        # Extract deep features
        aerial_features = self.extract_deep_features(aerial_photo)
        street_features = self.extract_deep_features(street_view_photo)
        
        # Compute similarity score
        similarity = self.compute_similarity_score(aerial_features, street_features)
        
        # Find SIFT correspondences
        kp1, kp2, matches = self.find_sift_correspondences(aerial_photo, street_view_photo)
        
        # Visualize matches
        result_img = self.visualize_matches(aerial_photo, street_view_photo, kp1, kp2, matches)
        
        return {
            'similarity_score': similarity,
            'num_matches': len(matches),
            'visualization': result_img,
            'keypoints_aerial': kp1,
            'keypoints_street': kp2,
            'matches': matches
        }
    
    def visualize_matches(self, img1, img2, kp1, kp2, matches):
        """Visualize matching points between images"""
        match_img = cv2.drawMatches(img1, kp1, img2, kp2, matches, None,
                                  flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
        return match_img

def main():
    # Example usage
    matcher = CrossPerspectiveMatcher()
    
    # Load images
    aerial_photo = cv2.imread('aerial_photo.jpg')
    street_view_photo = cv2.imread('street_view_photo.jpg')
    
    if aerial_photo is None or street_view_photo is None:
        raise ValueError("Could not load one or both images")
    
    # Find correspondences
    results = matcher.find_correspondences(aerial_photo, street_view_photo)
    
    # Print results
    print(f"Similarity Score: {results['similarity_score']:.4f}")
    print(f"Number of matching points: {results['num_matches']}")
    
    # Display visualization
    plt.figure(figsize=(15, 5))
    plt.imshow(cv2.cvtColor(results['visualization'], cv2.COLOR_BGR2RGB))
    plt.title('Matching Points Between Aerial and Street View Images')
    plt.axis('off')
    plt.show()

if __name__ == "__main__":
    main()