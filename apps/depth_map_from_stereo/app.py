# Save as reconstruction_pipeline.py
import os
import sys
import subprocess
import numpy as np
import cv2
from pathlib import Path
import json
import shutil
import logging
from dataclasses import dataclass, asdict
from typing import Tuple, Dict, Optional, List
import torch
from scipy.interpolate import griddata
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import open3d as o3d
from plyfile import PlyData
import matplotlib.pyplot as plt
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

@dataclass
class ReconstructionConfig:
    """Configuration settings for reconstruction pipeline."""
    workspace_path: str = "./reconstruction"
    grid_size: float = 1.0
    use_gpu: bool = torch.cuda.is_available()
    num_workers: int = os.cpu_count() or 1
    feature_matching_quality: str = "high"
    dense_reconstruction_quality: str = "high"
    min_point_density: float = 0.5
    outlier_removal_threshold: float = 2.0
    interpolation_method: str = "linear"
    save_intermediate: bool = True
    
    def to_dict(self) -> dict:
        return asdict(self)

class ReconstructionError(Exception):
    """Custom exception for reconstruction errors."""
    pass

class ImageProcessor:
    """Handles image preprocessing and validation."""
    
    @staticmethod
    def validate_and_preprocess(image_path: str) -> np.ndarray:
        """Validate and preprocess input image."""
        if not os.path.exists(image_path):
            raise ReconstructionError(f"Image not found: {image_path}")
            
        img = cv2.imread(image_path)
        if img is None:
            raise ReconstructionError(f"Failed to read image: {image_path}")
            
        # Check image size
        if img.shape[0] < 100 or img.shape[1] < 100:
            raise ReconstructionError("Image too small for reconstruction")
            
        # Basic preprocessing
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        equalized = cv2.equalizeHist(gray)
        denoised = cv2.fastNlMeansDenoising(equalized)
        
        return denoised

class PointCloudProcessor:
    """Handles point cloud processing and optimization."""
    
    @staticmethod
    def process_point_cloud(points: np.ndarray, config: ReconstructionConfig) -> np.ndarray:
        """Process and optimize point cloud data."""
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        
        # Remove outliers
        pcd, _ = pcd.remove_statistical_outlier(
            nb_neighbors=20,
            std_ratio=config.outlier_removal_threshold
        )
        
        # Estimate normals
        pcd.estimate_normals()
        
        # Optional: Optimize point cloud density
        if config.min_point_density > 0:
            pcd = pcd.voxel_down_sample(voxel_size=config.min_point_density)
        
        return np.asarray(pcd.points)

class DEMGenerator:
    """Handles DEM generation and interpolation."""
    
    @staticmethod
    def generate_dem(points: np.ndarray, config: ReconstructionConfig, device: torch.device) -> Tuple[np.ndarray, Dict]:
        """Generate DEM from point cloud data."""
        try:
            # Move computation to GPU if available
            if config.use_gpu:
                points_tensor = torch.from_numpy(points).to(device)
                dem, metadata = DEMGenerator._generate_dem_gpu(points_tensor, config)
            else:
                dem, metadata = DEMGenerator._generate_dem_cpu(points, config)
            
            # Validate DEM
            if np.isnan(dem).any():
                raise ReconstructionError("DEM contains invalid values")
            
            return dem, metadata
            
        except Exception as e:
            raise ReconstructionError(f"DEM generation failed: {str(e)}")
    
    @staticmethod
    def _generate_dem_gpu(points: torch.Tensor, config: ReconstructionConfig) -> Tuple[np.ndarray, Dict]:
        """GPU-accelerated DEM generation."""
        x_min, x_max = points[:, 0].min().item(), points[:, 0].max().item()
        y_min, y_max = points[:, 1].min().item(), points[:, 1].max().item()
        
        x_grid = torch.arange(x_min, x_max + config.grid_size, config.grid_size, device=points.device)
        y_grid = torch.arange(y_min, y_max + config.grid_size, config.grid_size, device=points.device)
        
        dem = torch.zeros((len(y_grid), len(x_grid)), device=points.device)
        dem_count = torch.zeros_like(dem)
        
        # Process in batches
        batch_size = 10000
        for i in range(0, len(points), batch_size):
            batch = points[i:i+batch_size]
            x_idx = ((batch[:, 0] - x_min) / config.grid_size).long()
            y_idx = ((batch[:, 1] - y_min) / config.grid_size).long()
            
            valid_points = (x_idx >= 0) & (x_idx < dem.shape[1]) & (y_idx >= 0) & (y_idx < dem.shape[0])
            x_idx = x_idx[valid_points]
            y_idx = y_idx[valid_points]
            z_values = batch[valid_points, 2]
            
            dem.index_put_((y_idx, x_idx), z_values, accumulate=True)
            dem_count.index_put_((y_idx, x_idx), torch.ones_like(z_values), accumulate=True)
        
        # Average and interpolate
        mask = dem_count > 0
        dem[mask] /= dem_count[mask]
        
        # Move to CPU for interpolation
        dem_np = dem.cpu().numpy()
        mask_np = mask.cpu().numpy()
        
        return DEMGenerator._interpolate_gaps(dem_np, mask_np, config), {
            "x_min": x_min,
            "x_max": x_max,
            "y_min": y_min,
            "y_max": y_max,
            "grid_size": config.grid_size,
            "processing": "gpu"
        }
    
    @staticmethod
    def _generate_dem_cpu(points: np.ndarray, config: ReconstructionConfig) -> Tuple[np.ndarray, Dict]:
        """CPU-based DEM generation."""
        x_min, x_max = points[:, 0].min(), points[:, 0].max()
        y_min, y_max = points[:, 1].min(), points[:, 1].max()
        
        x_grid = np.arange(x_min, x_max + config.grid_size, config.grid_size)
        y_grid = np.arange(y_min, y_max + config.grid_size, config.grid_size)
        
        dem = np.zeros((len(y_grid), len(x_grid)))
        dem_count = np.zeros_like(dem)
        
        # Process points in batches
        batch_size = 10000
        for i in tqdm(range(0, len(points), batch_size), desc="Generating DEM"):
            batch = points[i:i+batch_size]
            x_idx = ((batch[:, 0] - x_min) / config.grid_size).astype(int)
            y_idx = ((batch[:, 1] - y_min) / config.grid_size).astype(int)
            
            valid_points = (x_idx >= 0) & (x_idx < dem.shape[1]) & (y_idx >= 0) & (y_idx < dem.shape[0])
            x_idx = x_idx[valid_points]
            y_idx = y_idx[valid_points]
            z_values = batch[valid_points, 2]
            
            np.add.at(dem, (y_idx, x_idx), z_values)
            np.add.at(dem_count, (y_idx, x_idx), 1)
        
        mask = dem_count > 0
        dem[mask] /= dem_count[mask]
        
        return DEMGenerator._interpolate_gaps(dem, mask, config), {
            "x_min": x_min,
            "x_max": x_max,
            "y_min": y_min,
            "y_max": y_max,
            "grid_size": config.grid_size,
            "processing": "cpu"
        }
    
    @staticmethod
    def _interpolate_gaps(dem: np.ndarray, mask: np.ndarray, config: ReconstructionConfig) -> np.ndarray:
        """Interpolate empty cells in the DEM."""
        if not mask.all():
            y_coords, x_coords = np.where(mask)
            values = dem[mask]
            
            yi, xi = np.where(~mask)
            points_known = np.column_stack([x_coords, y_coords])
            points_unknown = np.column_stack([xi, yi])
            
            if len(points_unknown) > 0:
                interpolated = griddata(
                    points_known, values, points_unknown,
                    method=config.interpolation_method
                )
                dem[~mask] = interpolated
        
        return dem

class AerialReconstructor:
    """Main class for aerial reconstruction pipeline."""
    
    def __init__(self, config: Optional[ReconstructionConfig] = None):
        self.config = config or ReconstructionConfig()
        self.workspace = Path(self.config.workspace_path)
        self.setup_workspace()
        self.device = torch.device("cuda" if self.config.use_gpu and torch.cuda.is_available() else "cpu")
        self.setup_logging()
    
    def setup_workspace(self):
        """Setup workspace directories."""
        dirs = [
            self.workspace,
            self.workspace / "images",
            self.workspace / "sparse",
            self.workspace / "dense",
            self.workspace / "results"
        ]
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def setup_logging(self):
        """Configure logging."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.workspace / "reconstruction.log"),
                logging.StreamHandler()
            ]
        )
    
    def process_images(self, image1_path: str, image2_path: str) -> Tuple[np.ndarray, Dict]:
        """Process images and generate DEM."""
        try:
            logging.info("Starting reconstruction pipeline...")
            
            # Validate and preprocess images
            img1 = ImageProcessor.validate_and_preprocess(image1_path)
            img2 = ImageProcessor.validate_and_preprocess(image2_path)
            
            # Save preprocessed images
            if self.config.save_intermediate:
                cv2.imwrite(str(self.workspace / "images" / "preprocessed_1.jpg"), img1)
                cv2.imwrite(str(self.workspace / "images" / "preprocessed_2.jpg"), img2)
            
            # Run COLMAP pipeline
            points = self.run_colmap_pipeline(img1, img2)
            
            # Process point cloud
            points = PointCloudProcessor.process_point_cloud(points, self.config)
            
            # Generate DEM
            dem, metadata = DEMGenerator.generate_dem(points, self.config, self.device)
            
            # Save results
            self.save_results(dem, metadata)
            
            logging.info("Reconstruction completed successfully")
            return dem, metadata
            
        except Exception as e:
            logging.error(f"Reconstruction failed: {str(e)}")
            raise
    
    def run_colmap_pipeline(self, img1: np.ndarray, img2: np.ndarray) -> np.ndarray:
        """Run COLMAP reconstruction pipeline."""
        # Implementation of COLMAP pipeline would go here
        # This is a placeholder that should be replaced with actual COLMAP integration
        raise NotImplementedError("COLMAP pipeline not implemented")
    
    def save_results(self, dem: np.ndarray, metadata: Dict):
        """Save reconstruction results."""
        results_dir = self.workspace / "results"
        
        # Save DEM as numpy array
        np.save(str(results_dir / "dem.npy"), dem)
        
        # Save metadata
        with open(str(results_dir / "metadata.json"), "w") as f:
            json.dump(metadata, f, indent=2)
        
        # Save visualization
        plt.figure(figsize=(10, 8))
        plt.imshow(dem, cmap='terrain')
        plt.colorbar(label='Elevation (m)')
        plt.title('Digital Elevation Model')
        plt.xlabel('X (m)')
        plt.ylabel('Y (m)')
        plt.savefig(str(results_dir / "dem_visualization.png"))
        plt.close()

# GUI implementation continues from the previous response...