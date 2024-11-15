import cv2
import numpy as np
import os
import subprocess
import open3d as o3d
from pathlib import Path
import shutil

class VideoTo3DMesh:
    def __init__(self, video_path, output_dir, start_frame, end_frame):
        """
        Initialize the video to 3D mesh converter
        
        Args:
            video_path (str): Path to input video file
            output_dir (str): Directory to store output files
            start_frame (int): Starting frame number
            end_frame (int): Ending frame number
        """
        self.video_path = video_path
        self.output_dir = Path(output_dir)
        self.start_frame = start_frame
        self.end_frame = end_frame
        
        # Create output directories
        self.frames_dir = self.output_dir / "frames"
        self.colmap_dir = self.output_dir / "colmap"
        self.sparse_dir = self.colmap_dir / "sparse"
        self.dense_dir = self.colmap_dir / "dense"
        
        self._create_directories()

    def _create_directories(self):
        """Create necessary directories for processing"""
        for dir_path in [self.frames_dir, self.colmap_dir, self.sparse_dir, self.dense_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def extract_frames(self):
        """Extract frames from video between start_frame and end_frame"""
        cap = cv2.VideoCapture(self.video_path)
        frame_count = 0
        saved_count = 0
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            if self.start_frame <= frame_count <= self.end_frame:
                output_path = self.frames_dir / f"frame_{saved_count:06d}.jpg"
                cv2.imwrite(str(output_path), frame)
                saved_count += 1
                
            frame_count += 1
            if frame_count > self.end_frame:
                break
                
        cap.release()
        return saved_count

    def run_colmap(self):
        """Run COLMAP pipeline for 3D reconstruction"""
        # Feature extraction
        subprocess.run([
            "colmap", "feature_extractor",
            "--database_path", str(self.colmap_dir / "database.db"),
            "--image_path", str(self.frames_dir),
            "--ImageReader.single_camera", "1"
        ])

        # Feature matching
        subprocess.run([
            "colmap", "exhaustive_matcher",
            "--database_path", str(self.colmap_dir / "database.db")
        ])

        # Sparse reconstruction
        subprocess.run([
            "colmap", "mapper",
            "--database_path", str(self.colmap_dir / "database.db"),
            "--image_path", str(self.frames_dir),
            "--output_path", str(self.sparse_dir)
        ])

        # Dense reconstruction
        subprocess.run([
            "colmap", "image_undistorter",
            "--image_path", str(self.frames_dir),
            "--input_path", str(self.sparse_dir / "0"),
            "--output_path", str(self.dense_dir),
            "--output_type", "COLMAP"
        ])

        subprocess.run([
            "colmap", "patch_match_stereo",
            "--workspace_path", str(self.dense_dir)
        ])

        subprocess.run([
            "colmap", "stereo_fusion",
            "--workspace_path", str(self.dense_dir),
            "--output_path", str(self.dense_dir / "fused.ply")
        ])

    def create_mesh(self):
        """Create mesh from point cloud using Open3D"""
        # Load the point cloud
        pcd = o3d.io.read_point_cloud(str(self.dense_dir / "fused.ply"))
        
        # Estimate normals
        pcd.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30)
        )

        # Create mesh using Poisson reconstruction
        mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
            pcd, depth=9
        )
        
        # Remove low density vertices
        vertices_to_remove = densities < np.quantile(densities, 0.1)
        mesh.remove_vertices_by_mask(vertices_to_remove)
        
        # Save the final mesh
        o3d.io.write_triangle_mesh(
            str(self.output_dir / "final_mesh.ply"),
            mesh
        )

def process_video_to_mesh(video_path, output_dir, start_frame, end_frame):
    """
    Main function to process video into 3D mesh
    
    Args:
        video_path (str): Path to input video file
        output_dir (str): Directory to store output files
        start_frame (int): Starting frame number
        end_frame (int): Ending frame number
    """
    processor = VideoTo3DMesh(video_path, output_dir, start_frame, end_frame)
    
    print("Extracting frames...")
    num_frames = processor.extract_frames()
    print(f"Extracted {num_frames} frames")
    
    print("Running COLMAP reconstruction...")
    processor.run_colmap()
    
    print("Creating final mesh...")
    processor.create_mesh()
    
    print(f"Process complete! Final mesh saved to {output_dir}/final_mesh.ply")

# Example usage
if __name__ == "__main__":
    process_video_to_mesh(
        video_path="input_video.mp4",
        output_dir="output",
        start_frame=0,
        end_frame=100
    )