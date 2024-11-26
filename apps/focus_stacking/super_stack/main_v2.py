import subprocess
import os
import glob
import concurrent.futures
from pathlib import Path
import cv2
import numpy as np
from tqdm import tqdm

class AerialStackProcessor:
    def __init__(self, input_dir, output_dir, work_dir=None):
        """
        Initialize the processor with directories for processing
        
        Args:
            input_dir: Directory containing input frames
            output_dir: Directory for final output
            work_dir: Directory for intermediate files (defaults to temp dir)
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.work_dir = Path(work_dir) if work_dir else Path("/tmp/aerial_stack")
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Parameters optimized for historical aerial footage
        self.align_params = {
            "ransac_thresh": 10.0,  # More tolerant of mismatches
            "match_conf": 0.3,      # Lower confidence for fuzzy matching
            "blend_strength": 5,    # Stronger blending for grain
        }
        
    def extract_frames(self, video_path):
        """Extract frames from video file"""
        cap = cv2.VideoCapture(str(video_path))
        frames = []
        
        with tqdm(desc="Extracting frames") as pbar:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                # Convert to grayscale for better feature matching
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                frames.append(gray)
                pbar.update(1)
                
        cap.release()
        return frames
    
    def align_frames(self, frames):
        """Align frames using OpenCV's ECC algorithm with custom parameters"""
        aligned = []
        warp_mode = cv2.MOTION_EUCLIDEAN
        warp_matrix = np.eye(2, 3, dtype=np.float32)
        
        # Use first frame as reference
        ref_frame = frames[0]
        criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 1000, 1e-7)
        
        with tqdm(total=len(frames), desc="Aligning frames") as pbar:
            for frame in frames:
                try:
                    # Use ECC algorithm optimized for historical footage
                    cc, warp_matrix = cv2.findTransformECC(
                        ref_frame, frame, warp_matrix, warp_mode, criteria,
                        inputMask=None,
                        gaussFiltSize=5  # Increased for noisy footage
                    )
                    
                    aligned_frame = cv2.warpAffine(
                        frame, warp_matrix, (frame.shape[1], frame.shape[0]),
                        flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP
                    )
                    aligned.append(aligned_frame)
                except cv2.error:
                    # Fall back to original frame if alignment fails
                    aligned.append(frame)
                    
                pbar.update(1)
                
        return aligned
    
    def focus_stack(self, aligned_frames):
        """Stack frames using Hugin's enfuse with custom parameters"""
        # Save aligned frames to temporary files
        temp_files = []
        for i, frame in enumerate(aligned_frames):
            temp_path = self.work_dir / f"aligned_{i:04d}.tiff"
            cv2.imwrite(str(temp_path), frame)
            temp_files.append(temp_path)
            
        output_path = self.output_dir / "stacked_result.tiff"
        
        # Build enfuse command with parameters for historical footage
        cmd = [
            "enfuse",
            "--exposure-weight=0",  # Focus only on sharpness
            "--saturation-weight=0",
            "--contrast-weight=1",
            "--hard-mask",  # Better for grainy footage
            "--contrast-window=9",  # Larger window for noise tolerance
            "--contrast-edge-scale=0.3",  # Reduced to handle grain
            "-o", str(output_path)
        ] + [str(f) for f in temp_files]
        
        subprocess.run(cmd, check=True)
        return output_path
    
    def clean_temp_files(self):
        """Remove temporary files"""
        for f in self.work_dir.glob("aligned_*.tiff"):
            f.unlink()
            
    def process(self, video_path):
        """Main processing pipeline"""
        try:
            print("Starting video processing pipeline...")
            
            # Extract frames
            frames = self.extract_frames(video_path)
            if not frames:
                raise ValueError("No frames extracted from video")
                
            # Align frames
            aligned = self.align_frames(frames)
            
            # Stack frames
            result_path = self.focus_stack(aligned)
            
            # Cleanup
            self.clean_temp_files()
            
            print(f"Processing complete. Result saved to: {result_path}")
            return result_path
            
        except Exception as e:
            print(f"Error during processing: {str(e)}")
            self.clean_temp_files()
            raise

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Process historical aerial footage")
    parser.add_argument("input_video", help="Input video file")
    parser.add_argument("output_dir", help="Output directory")
    parser.add_argument("--work-dir", help="Working directory for temporary files")
    args = parser.parse_args()
    
    processor = AerialStackProcessor(
        input_dir=os.path.dirname(args.input_video),
        output_dir=args.output_dir,
        work_dir=args.work_dir
    )
    processor.process(args.input_video)

if __name__ == "__main__":
    main()