# Save as colmap_integration.py
import subprocess
import os
import sqlite3
import numpy as np
from pathlib import Path
from typing import List, Tuple

class COLMAPRunner:
    """Handles COLMAP command execution and database interactions."""
    
    def __init__(self, workspace: Path, use_gpu: bool = True):
        self.workspace = workspace
        self.database_path = workspace / "database.db"
        self.image_path = workspace / "images"
        self.sparse_path = workspace / "sparse"
        self.dense_path = workspace / "dense"
        self.use_gpu = use_gpu

    def run_command(self, command: List[str], desc: str) -> None:
        """Execute COLMAP command with proper error handling."""
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"COLMAP {desc} failed: {e.stderr}")

    def feature_extraction(self) -> None:
        """Extract features from images."""
        command = [
            "colmap", "feature_extractor",
            "--database_path", str(self.database_path),
            "--image_path", str(self.image_path),
            "--ImageReader.single_camera", "1",
            "--SiftExtraction.use_gpu", str(int(self.use_gpu)),
            "--SiftExtraction.max_num_features", "8192",
            "--SiftExtraction.estimate_affine_shape", "1",
            "--SiftExtraction.domain_size_pooling", "1"
        ]
        self.run_command(command, "feature extraction")

    def feature_matching(self) -> None:
        """Match features between images."""
        command = [
            "colmap", "exhaustive_matcher",
            "--database_path", str(self.database_path),
            "--SiftMatching.use_gpu", str(int(self.use_gpu)),
            "--SiftMatching.guided_matching", "1",
            "--SiftMatching.max_num_trials", "50000",
            "--SiftMatching.confidence", "0.999",
            "--SiftMatching.max_error", "4"
        ]
        self.run_command(command, "feature matching")

    def sparse_reconstruction(self) -> None:
        """Run sparse reconstruction."""
        command = [
            "colmap", "mapper",
            "--database_path", str(self.database_path),
            "--image_path", str(self.image_path),
            "--output_path", str(self.sparse_path),
            "--Mapper.num_threads", "16",
            "--Mapper.init_min_tri_angle", "4",
            "--Mapper.multiple_models", "0",
            "--Mapper.extract_colors", "1"
        ]
        self.run_command(command, "sparse reconstruction")

    def dense_reconstruction(self) -> None:
        """Run dense reconstruction pipeline."""
        # Image undistortion
        command_undistort = [
            "colmap", "image_undistorter",
            "--image_path", str(self.image_path),
            "--input_path", str(self.sparse_path / "0"),
            "--output_path", str(self.dense_path),
            "--output_type", "COLMAP",
            "--max_image_size", "3200"
        ]
        self.run_command(command_undistort, "image undistortion")

        # Dense stereo
        command_stereo = [
            "colmap", "patch_match_stereo",
            "--workspace_path", str(self.dense_path),
            "--workspace_format", "COLMAP",
            "--PatchMatchStereo.gpu_index", "0" if self.use_gpu else "-1",
            "--PatchMatchStereo.depth_min", "0.1",
            "--PatchMatchStereo.depth_max", "100",
            "--PatchMatchStereo.window_radius", "5",
            "--PatchMatchStereo.window_step", "1",
            "--PatchMatchStereo.num_samples", "15",
            "--PatchMatchStereo.num_iterations", "5"
        ]
        self.run_command(command_stereo, "dense stereo")

        # Stereo fusion
        command_fusion = [
            "colmap", "stereo_fusion",
            "--workspace_path", str(self.dense_path),
            "--workspace_format", "COLMAP",
            "--input_type", "geometric",
            "--output_path", str(self.dense_path / "fused.ply"),
            "--StereoFusion.min_num_pixels", "3",
            "--StereoFusion.max_reproj_error", "2",
            "--StereoFusion.max_depth_error", "0.1",
            "--StereoFusion.max_normal_error", "10"
        ]
        self.run_command(command_fusion, "stereo fusion")

    def get_reconstruction_stats(self) -> dict:
        """Get statistics about the reconstruction."""
        stats = {}
        
        # Read database statistics
        with sqlite3.connect(str(self.database_path)) as conn:
            cur = conn.cursor()
            
            # Get keypoint statistics
            cur.execute("SELECT COUNT(*) FROM keypoints")
            stats['total_keypoints'] = cur.fetchone()[0]
            
            # Get match statistics
            cur.execute("SELECT COUNT(*) FROM matches")
            stats['total_matches'] = cur.fetchone()[0]
            
            # Get image statistics
            cur.execute("SELECT COUNT(*) FROM images")
            stats['total_images'] = cur.fetchone()[0]
        
        # Read point cloud statistics if available
        if (self.dense_path / "fused.ply").exists():
            from plyfile import PlyData
            ply_data = PlyData.read(str(self.dense_path / "fused.ply"))
            stats['dense_points'] = len(ply_data['vertex'])
        
        return stats

# Update the reconstruction pipeline implementation in reconstruction_pipeline.py

def run_colmap_pipeline(self, img1: np.ndarray, img2: np.ndarray) -> np.ndarray:
    """Run COLMAP reconstruction pipeline."""
    try:
        # Initialize COLMAP runner
        colmap = COLMAPRunner(self.workspace, self.config.use_gpu)
        
        # Save images for COLMAP
        cv2.imwrite(str(self.workspace / "images" / "image1.jpg"), img1)
        cv2.imwrite(str(self.workspace / "images" / "image2.jpg"), img2)
        
        # Run COLMAP pipeline
        logging.info("Running feature extraction...")
        colmap.feature_extraction()
        
        logging.info("Running feature matching...")
        colmap.feature_matching()
        
        logging.info("Running sparse reconstruction...")
        colmap.sparse_reconstruction()
        
        logging.info("Running dense reconstruction...")
        colmap.dense_reconstruction()
        
        # Get reconstruction statistics
        stats = colmap.get_reconstruction_stats()
        logging.info(f"Reconstruction statistics: {stats}")
        
        # Read point cloud
        ply_path = self.workspace / "dense" / "fused.ply"
        if not ply_path.exists():
            raise RuntimeError("Dense reconstruction failed to produce point cloud")
            
        ply_data = PlyData.read(str(ply_path))
        points = np.vstack([
            ply_data['vertex']['x'],
            ply_data['vertex']['y'],
            ply_data['vertex']['z']
        ]).T
        
        return points
        
    except Exception as e:
        logging.error(f"COLMAP pipeline failed: {str(e)}")
        raise

# Add visualization tools (visualization.py)

class DEMVisualizer:
    """Advanced DEM visualization tools."""
    
    @staticmethod
    def create_shaded_relief(dem: np.ndarray, metadata: dict) -> np.ndarray:
        """Create shaded relief visualization."""
        dx, dy = np.gradient(dem)
        slope = np.pi/2.0 - np.arctan(np.sqrt(dx*dx + dy*dy))
        aspect = np.arctan2(-dx, dy)
        
        altitude = np.pi/4.0
        azimuth = np.pi/2.0
        
        shaded = np.sin(altitude) * np.sin(slope) + \
                 np.cos(altitude) * np.cos(slope) * \
                 np.cos(azimuth - aspect)
        
        return shaded

    @staticmethod
    def create_contour_plot(fig: Figure, dem: np.ndarray, metadata: dict) -> None:
        """Create contour plot visualization."""
        ax = fig.add_subplot(111)
        
        # Calculate contour levels
        levels = np.linspace(dem.min(), dem.max(), 20)
        
        # Create contour plot
        contour = ax.contour(dem, levels=levels, colors='black', alpha=0.5)
        filled = ax.contourf(dem, levels=levels, cmap='terrain')
        
        # Add labels
        ax.clabel(contour, inline=True, fontsize=8)
        fig.colorbar(filled, label='Elevation (m)')
        
        # Set labels and title
        ax.set_title('DEM Contour Map')
        ax.set_xlabel('X (m)')
        ax.set_ylabel('Y (m)')

    @staticmethod
    def create_3d_plot(fig: Figure, dem: np.ndarray, metadata: dict) -> None:
        """Create 3D surface plot."""
        ax = fig.add_subplot(111, projection='3d')
        
        # Create coordinate grids
        x = np.linspace(metadata['x_min'], metadata['x_max'], dem.shape[1])
        y = np.linspace(metadata['y_min'], metadata['y_max'], dem.shape[0])
        X, Y = np.meshgrid(x, y)
        
        # Create 3D surface plot
        surf = ax.plot_surface(X, Y, dem, cmap='terrain', linewidth=0)
        fig.colorbar(surf, label='Elevation (m)')
        
        ax.set_title('3D Terrain Model')
        ax.set_xlabel('X (m)')
        ax.set_ylabel('Y (m)')
        ax.set_zlabel('Elevation (m)')

class VisualizationTab(QWidget):
    """Extended visualization tab for the GUI."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the visualization interface."""
        layout = QVBoxLayout(self)
        
        # Create visualization type selector
        vis_group = QGroupBox("Visualization Type")
        vis_layout = QHBoxLayout()
        
        self.vis_combo = QComboBox()
        self.vis_combo.addItems(['Shaded Relief', 'Contour Map', '3D Surface'])
        self.vis_combo.currentTextChanged.connect(self.update_visualization)
        vis_layout.addWidget(QLabel("Type:"))
        vis_layout.addWidget(self.vis_combo)
        
        vis_group.setLayout(vis_layout)
        layout.addWidget(vis_group)
        
        # Create matplotlib figure
        self.figure = Figure(figsize=(10, 8))
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        
        # Add export button
        self.export_button = QPushButton("Export Visualization")
        self.export_button.clicked.connect(self.export_visualization)
        layout.addWidget(self.export_button)
        
        self.dem_data = None
        self.metadata = None
        
    def set_data(self, dem: np.ndarray, metadata: dict):
        """Set the DEM data and update visualization."""
        self.dem_data = dem
        self.metadata = metadata
        self.update_visualization()
        
    def update_visualization(self):
        """Update the current visualization."""
        if self.dem_data is None:
            return
            
        self.figure.clear()
        
        vis_type = self.vis_combo.currentText()
        if vis_type == 'Shaded Relief':
            shaded = DEMVisualizer.create_shaded_relief(self.dem_data, self.metadata)
            ax = self.figure.add_subplot(111)
            im = ax.imshow(shaded, cmap='gist_earth')
            self.figure.colorbar(im, label='Elevation (m)')
            ax.set_title('Shaded Relief Map')
            
        elif vis_type == 'Contour Map':
            DEMVisualizer.create_contour_plot(self.figure, self.dem_data, self.metadata)
            
        elif vis_type == '3D Surface':
            DEMVisualizer.create_3d_plot(self.figure, self.dem_data, self.metadata)
        
        self.canvas.draw()
        
    def export_visualization(self):
        """Export the current visualization."""
        if self.dem_data is None:
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Visualization",
            "",
            "PNG Files (*.png);;PDF Files (*.pdf);;SVG Files (*.svg)"
        )
        
        if file_path:
            self.figure.savefig(file_path, dpi=300, bbox_inches='tight')
            QMessageBox.information(self, "Success", "Visualization exported successfully!")

# Update the main window to include the new visualization tab
class MainWindow(QMainWindow):
    def _create_ui(self):
        # ... (previous UI setup code) ...
        
        # Add visualization tab
        self.vis_tab = VisualizationTab()
        tab_widget.addTab(self.vis_tab, "Visualization")
        
        # ... (rest of the UI setup code) ...
        
    def _process_complete(self, result: Tuple[np.ndarray, dict]):
        # ... (previous completion code) ...
        
        # Update visualization tab
        self.vis_tab.set_data(dem, metadata)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())