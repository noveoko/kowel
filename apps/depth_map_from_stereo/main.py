import os
import sys
import subprocess
import numpy as np
import cv2
from pathlib import Path
import json
import shutil

class AerialReconstructor:
    def __init__(self, workspace_path="./reconstruction"):
        """Initialize the reconstruction pipeline with a workspace directory."""
        self.workspace = Path(workspace_path)
        self.database_path = self.workspace / "database.db"
        self.image_path = self.workspace / "images"
        self.sparse_path = self.workspace / "sparse"
        self.dense_path = self.workspace / "dense"
        
        # Create necessary directories
        self._setup_workspace()
        
    def _setup_workspace(self):
        """Create the workspace directory structure."""
        dirs = [self.workspace, self.image_path, self.sparse_path, self.dense_path]
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)

    def _copy_images(self, image1_path, image2_path):
        """Copy input images to the workspace."""
        # Copy and rename images to ensure consistent naming
        shutil.copy2(image1_path, self.image_path / "image1.jpg")
        shutil.copy2(image2_path, self.image_path / "image2.jpg")

    def _run_colmap_feature_extractor(self):
        """Extract features from images using COLMAP."""
        cmd = [
            "colmap", "feature_extractor",
            "--database_path", str(self.database_path),
            "--image_path", str(self.image_path),
            "--ImageReader.single_camera", "1",
            "--SiftExtraction.use_gpu", "1"
        ]
        subprocess.run(cmd, check=True)

    def _run_colmap_matcher(self):
        """Match features between images using COLMAP."""
        cmd = [
            "colmap", "exhaustive_matcher",
            "--database_path", str(self.database_path),
            "--SiftMatching.use_gpu", "1"
        ]
        subprocess.run(cmd, check=True)

    def _run_colmap_mapper(self):
        """Run the COLMAP mapper to create sparse reconstruction."""
        cmd = [
            "colmap", "mapper",
            "--database_path", str(self.database_path),
            "--image_path", str(self.image_path),
            "--output_path", str(self.sparse_path)
        ]
        subprocess.run(cmd, check=True)

    def _run_colmap_dense(self):
        """Run dense reconstruction to generate depth maps and point cloud."""
        # Image undistorter
        cmd_undistort = [
            "colmap", "image_undistorter",
            "--image_path", str(self.image_path),
            "--input_path", str(self.sparse_path / "0"),
            "--output_path", str(self.dense_path),
            "--output_type", "COLMAP"
        ]
        subprocess.run(cmd_undistort, check=True)

        # Dense stereo
        cmd_stereo = [
            "colmap", "patch_match_stereo",
            "--workspace_path", str(self.dense_path),
            "--workspace_format", "COLMAP"
        ]
        subprocess.run(cmd_stereo, check=True)

        # Stereo fusion
        cmd_fusion = [
            "colmap", "stereo_fusion",
            "--workspace_path", str(self.dense_path),
            "--workspace_format", "COLMAP",
            "--input_type", "geometric",
            "--output_path", str(self.dense_path / "fused.ply")
        ]
        subprocess.run(cmd_fusion, check=True)

    def _generate_dem(self):
        """Convert dense point cloud to DEM."""
        # Read the PLY file
        from plyfile import PlyData
        ply_data = PlyData.read(str(self.dense_path / "fused.ply"))
        
        # Extract points and create grid
        points = np.vstack([
            ply_data['vertex']['x'],
            ply_data['vertex']['y'],
            ply_data['vertex']['z']
        ]).T
        
        # Create a regular grid
        grid_size = 1.0  # 1 meter grid cells
        x_min, x_max = points[:, 0].min(), points[:, 0].max()
        y_min, y_max = points[:, 1].min(), points[:, 1].max()
        
        x_grid = np.arange(x_min, x_max + grid_size, grid_size)
        y_grid = np.arange(y_min, y_max + grid_size, grid_size)
        
        # Initialize DEM grid
        dem = np.zeros((len(y_grid), len(x_grid)))
        dem_count = np.zeros_like(dem)
        
        # Fill DEM grid
        for point in points:
            x_idx = int((point[0] - x_min) / grid_size)
            y_idx = int((point[1] - y_min) / grid_size)
            if 0 <= x_idx < dem.shape[1] and 0 <= y_idx < dem.shape[0]:
                dem[y_idx, x_idx] += point[2]
                dem_count[y_idx, x_idx] += 1
        
        # Average heights and handle empty cells
        mask = dem_count > 0
        dem[mask] /= dem_count[mask]
        
        # Interpolate empty cells
        from scipy.interpolate import griddata
        y_coords, x_coords = np.where(mask)
        values = dem[mask]
        
        yi, xi = np.where(~mask)
        points_known = np.column_stack([x_coords, y_coords])
        points_unknown = np.column_stack([xi, yi])
        
        if len(points_unknown) > 0:
            interpolated = griddata(points_known, values, points_unknown, method='linear')
            dem[~mask] = interpolated
        
        # Save DEM
        np.save(str(self.workspace / "dem.npy"), dem)
        
        # Save metadata
        metadata = {
            "x_min": float(x_min),
            "x_max": float(x_max),
            "y_min": float(y_min),
            "y_max": float(y_max),
            "grid_size": float(grid_size)
        }
        with open(str(self.workspace / "dem_metadata.json"), "w") as f:
            json.dump(metadata, f)
        
        return dem, metadata

    def process_images(self, image1_path, image2_path):
        """Process two aerial images to create a DEM."""
        try:
            # Copy images to workspace
            self._copy_images(image1_path, image2_path)
            
            # Run COLMAP pipeline
            print("Extracting features...")
            self._run_colmap_feature_extractor()
            
            print("Matching features...")
            self._run_colmap_matcher()
            
            print("Creating sparse reconstruction...")
            self._run_colmap_mapper()
            
            print("Creating dense reconstruction...")
            self._run_colmap_dense()
            
            print("Generating DEM...")
            dem, metadata = self._generate_dem()
            
            print(f"Reconstruction complete. Results saved in {self.workspace}")
            return dem, metadata
            
        except subprocess.CalledProcessError as e:
            print(f"Error during COLMAP processing: {e}")
            raise
        except Exception as e:
            print(f"Error during processing: {e}")
            raise

def main():
    if len(sys.argv) != 3:
        print("Usage: python script.py aerial_photo_1 aerial_photo_2")
        sys.exit(1)
    
    image1_path = sys.argv[1]
    image2_path = sys.argv[2]
    
    # Check if images exist
    if not os.path.exists(image1_path) or not os.path.exists(image2_path):
        print("One or both input images do not exist!")
        sys.exit(1)
    
    # Create reconstructor and process images
    reconstructor = AerialReconstructor()
    try:
        dem, metadata = reconstructor.process_images(image1_path, image2_path)
        print("DEM generation successful!")
        print(f"DEM shape: {dem.shape}")
        print(f"Metadata: {metadata}")
    except Exception as e:
        print(f"Error during reconstruction: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()