# OPTIMIZED

import io
import time
from typing import Tuple, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import threading

import numpy as np
from scipy.ndimage import gaussian_filter
from PIL import Image
import cv2
from IPython.display import display, clear_output, HTML
import ipywidgets as widgets
from tqdm.notebook import tqdm
from joblib import Parallel, delayed
import base64
import io
import time
from typing import Tuple, Optional

import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter
from PIL import Image
import cv2
from IPython.display import display, clear_output
import ipywidgets as widgets
from tqdm.notebook import tqdm

class PPAHE:
    def __init__(
        self,
        min_window: int = 3,
        max_window: int = 65,
        clip_limit: float = 3.0,
        n_bins: int = 256
    ):
        if min_window % 2 == 0 or max_window % 2 == 0:
            raise ValueError("Window sizes must be odd numbers")

        self.min_window = min_window
        self.max_window = max_window
        self.clip_limit = clip_limit
        self.n_bins = n_bins

    def _compute_local_statistics(
        self,
        image: np.ndarray,
        sigma: float = 2.0
    ) -> Tuple[np.ndarray, np.ndarray]:
        local_mean = gaussian_filter(image, sigma)
        local_sqr_mean = gaussian_filter(image ** 2, sigma)
        variance = local_sqr_mean - local_mean ** 2

        grad_x = np.gradient(image, axis=1)
        grad_y = np.gradient(image, axis=0)
        gradient_magnitude = np.sqrt(grad_x ** 2 + grad_y ** 2)

        return variance, gradient_magnitude

    def _determine_window_sizes(
        self,
        variance: np.ndarray,
        gradient_magnitude: np.ndarray
    ) -> np.ndarray:
        # Add small epsilon to avoid division by zero
        eps = 1e-8
        norm_var = (variance - variance.min()) / (variance.max() - variance.min() + eps)
        norm_grad = (gradient_magnitude - gradient_magnitude.min()) / \
                   (gradient_magnitude.max() - gradient_magnitude.min() + eps)

        combined_measure = (norm_var + norm_grad) / 2
        window_range = self.max_window - self.min_window
        window_sizes = self.max_window - (combined_measure * window_range)

        window_sizes = (np.round(window_sizes) // 2 * 2 + 1).astype(int)
        return np.clip(window_sizes, self.min_window, self.max_window)

    def _get_adaptive_neighborhood(
        self,
        image: np.ndarray,
        center_y: int,
        center_x: int,
        window_size: int
    ) -> np.ndarray:
        half_window = window_size // 2
        padded = np.pad(image, half_window, mode='reflect')
        y_start = center_y
        x_start = center_x
        return padded[
            y_start:y_start + window_size,
            x_start:x_start + window_size
        ]

    def _equalize_neighborhood(
        self,
        neighborhood: np.ndarray,
        center_value: int
    ) -> int:
        hist, bins = np.histogram(neighborhood, self.n_bins, range=(0, 255))

        # Apply clip limit
        clip_height = int((neighborhood.size * self.clip_limit) / self.n_bins)
        excess = hist - clip_height
        hist = np.minimum(hist, clip_height)

        # Redistribute excess
        while excess.sum() > 0:
            redistrib_amt = excess.sum() // self.n_bins
            if redistrib_amt == 0:
                break
            hist += redistrib_amt
            hist = np.minimum(hist, clip_height)
            excess = hist - clip_height

        # Calculate CDF with handling for uniform regions
        cdf = hist.cumsum()
        cdf_min = cdf.min()
        cdf_max = cdf.max()

        # Handle uniform regions
        if cdf_max == cdf_min:
            return center_value  # Return original value for uniform regions

        # Normal CDF transformation
        cdf_normalized = (cdf - cdf_min) * 255 / (cdf_max - cdf_min)

        # Map center pixel
        return int(np.interp(center_value, bins[:-1], cdf_normalized))

    def enhance(self, image: np.ndarray, progress_callback=None) -> np.ndarray:
        if image.dtype != np.uint8:
            raise ValueError("Image must be uint8")

        variance, gradient = self._compute_local_statistics(image)
        window_sizes = self._determine_window_sizes(variance, gradient)
        enhanced = np.zeros_like(image)

        total_pixels = image.shape[0] * image.shape[1]

        with tqdm(total=total_pixels, desc="Enhancing image") as pbar:
            for y in range(image.shape[0]):
                for x in range(image.shape[1]):
                    window_size = window_sizes[y, x]
                    neighborhood = self._get_adaptive_neighborhood(
                        image, y, x, window_size
                    )
                    enhanced[y, x] = self._equalize_neighborhood(
                        neighborhood,
                        image[y, x]
                    )
                    pbar.update(1)

        return enhanced
        
@dataclass
class WindowCache:
    """Cache for window sizes and padded image data"""
    sizes: np.ndarray
    padded_image: np.ndarray
    cache_key: str = ""

class OptimizedPPAHE:
    def __init__(
        self,
        min_window: int = 3,
        max_window: int = 65,
        clip_limit: float = 3.0,
        n_bins: int = 256,
        n_jobs: int = -1  # Use all available cores
    ):
        if min_window % 2 == 0 or max_window % 2 == 0:
            raise ValueError("Window sizes must be odd numbers")
            
        self.min_window = min_window
        self.max_window = max_window
        self.clip_limit = clip_limit
        self.n_bins = n_bins
        self.n_jobs = n_jobs
        self.window_cache = None
        
    def _compute_local_statistics(
        self,
        image: np.ndarray,
        sigma: float = 2.0
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Vectorized computation of local statistics"""
        # Compute gradients for entire image at once
        grad_y, grad_x = np.gradient(image)
        gradient_magnitude = np.sqrt(grad_x ** 2 + grad_y ** 2)
        
        # Compute variance using vectorized operations
        local_mean = gaussian_filter(image, sigma)
        local_sqr_mean = gaussian_filter(image ** 2, sigma)
        variance = local_sqr_mean - local_mean ** 2
        
        return variance, gradient_magnitude

    def _determine_window_sizes(
        self,
        variance: np.ndarray,
        gradient_magnitude: np.ndarray
    ) -> WindowCache:
        """Compute and cache window sizes"""
        eps = 1e-8
        
        # Normalize using vectorized operations
        norm_var = (variance - variance.min()) / (variance.max() - variance.min() + eps)
        norm_grad = (gradient_magnitude - gradient_magnitude.min()) / \
                   (gradient_magnitude.max() - gradient_magnitude.min() + eps)
        
        # Compute window sizes
        combined_measure = (norm_var + norm_grad) / 2
        window_range = self.max_window - self.min_window
        window_sizes = self.max_window - (combined_measure * window_range)
        window_sizes = (np.round(window_sizes) // 2 * 2 + 1).astype(np.int32)
        window_sizes = np.clip(window_sizes, self.min_window, self.max_window)
        
        # Create padded image
        max_padding = self.max_window // 2
        padded_image = np.pad(image, max_padding, mode='reflect')
        
        # Create cache
        return WindowCache(sizes=window_sizes, padded_image=padded_image)

    def _equalize_neighborhood_optimized(
        self,
        neighborhood: np.ndarray,
        center_value: int,
        clip_limit: float,
        neighborhood_size: int
    ) -> int:
        """Optimized neighborhood equalization"""
        # Pre-allocate histogram array
        hist = np.zeros(256, dtype=np.int32)
        
        # Compute histogram directly
        np.add.at(hist, neighborhood.ravel(), 1)
        
        # Apply clip limit efficiently
        clip_height = int((neighborhood_size * clip_limit) / 256)
        excess = np.sum(np.maximum(hist - clip_height, 0))
        
        if excess > 0:
            # Redistribute excess in one step
            redistribution = excess // 256
            leftover = excess % 256
            
            hist = np.minimum(hist, clip_height)
            hist += redistribution
            
            if leftover > 0:
                # Distribute leftover uniformly
                hist[:leftover] += 1
        
        # Compute CDF efficiently
        cdf = hist.cumsum()
        
        # Handle uniform regions
        cdf_min = cdf[0]
        cdf_max = cdf[-1]
        if cdf_max == cdf_min:
            return center_value
        
        # Normalize CDF
        cdf_normalized = ((cdf - cdf_min) * 255) / (cdf_max - cdf_min)
        
        # Map pixel value
        return int(cdf_normalized[center_value])

    def _process_row(
        self,
        y: int,
        image: np.ndarray,
        cache: WindowCache,
        pbar=None
    ) -> np.ndarray:
        """Process a single row of the image"""
        row_result = np.zeros(image.shape[1], dtype=np.uint8)
        max_padding = self.max_window // 2
        
        for x in range(image.shape[1]):
            window_size = cache.sizes[y, x]
            half_window = window_size // 2
            
            # Direct slice from padded image
            y_start = y + max_padding - half_window
            y_end = y + max_padding + half_window + 1
            x_start = x + max_padding - half_window
            x_end = x + max_padding + half_window + 1
            
            neighborhood = cache.padded_image[y_start:y_end, x_start:x_end]
            
            row_result[x] = self._equalize_neighborhood_optimized(
                neighborhood,
                image[y, x],
                self.clip_limit,
                window_size * window_size
            )
            
            if pbar:
                pbar.update(1)
                
        return row_result

    def enhance(self, image: np.ndarray) -> np.ndarray:
        """Enhanced image using parallel processing"""
        if image.dtype != np.uint8:
            raise ValueError("Image must be uint8")
        
        # Compute statistics and cache window sizes
        variance, gradient = self._compute_local_statistics(image)
        self.window_cache = self._determine_window_sizes(variance, gradient)
        
        # Initialize progress bar
        total_pixels = image.shape[0] * image.shape[1]
        pbar = tqdm(total=total_pixels, desc="Enhancing image")
        
        # Process rows in parallel
        with Parallel(n_jobs=self.n_jobs) as parallel:
            enhanced_rows = parallel(
                delayed(self._process_row)(
                    y, image, self.window_cache, pbar
                )
                for y in range(image.shape[0])
            )
        
        pbar.close()
        return np.array(enhanced_rows, dtype=np.uint8)

class PPAHENotebook:
    def __init__(self):
        self.image = None
        self.enhanced = None
        self.ppahe = OptimizedPPAHE()  # Use optimized version
        self.output = widgets.Output()
        self.create_widgets()

    def create_widgets(self):
        # Previous widgets remain the same
        self.file_upload = widgets.FileUpload(
            accept='.png,.jpg,.jpeg,.tiff',
            multiple=False,
            description='Upload Image'
        )
        self.file_upload.observe(self.on_upload_change, names='value')

        self.min_window = widgets.IntSlider(
            value=3,
            min=3,
            max=31,
            step=2,
            description='Min Window:',
            continuous_update=False
        )

        self.max_window = widgets.IntSlider(
            value=65,
            min=33,
            max=129,
            step=2,
            description='Max Window:',
            continuous_update=False
        )

        self.clip_limit = widgets.FloatSlider(
            value=3.0,
            min=1.0,
            max=5.0,
            step=0.1,
            description='Clip Limit:',
            continuous_update=False
        )

        # Enhance button
        self.enhance_button = widgets.Button(
            description='Enhance Image',
            button_style='primary'
        )
        self.enhance_button.on_click(self.on_enhance_click)

        # Download button (new)
        self.download_button = widgets.Button(
            description='Download Enhanced Image',
            button_style='success',
            disabled=True  # Initially disabled
        )
        self.download_button.on_click(self.on_download_click)

        # Status label
        self.status_label = widgets.Label(value='')

        # Display widgets
        display(widgets.VBox([
            self.file_upload,
            self.min_window,
            self.max_window,
            self.clip_limit,
            widgets.HBox([self.enhance_button, self.download_button]),  # Buttons side by side
            self.status_label,
            self.output
        ]))

    def on_upload_change(self, change):
        if len(change.new) > 0:
            # Get the first (and only) file
            file_name = list(change.new.keys())[0]
            content = change.new[file_name]['content']

            # Convert uploaded content to image
            image = Image.open(io.BytesIO(content))
            # Convert to grayscale numpy array
            self.image = np.array(image.convert('L'))

            # Display original image
            with self.output:
                clear_output(wait=True)
                plt.figure(figsize=(10, 5))
                plt.imshow(self.image, cmap='gray')
                plt.title('Original Image')
                plt.axis('off')
                plt.show()

            self.status_label.value = f'Image loaded: {file_name}'

    def on_enhance_click(self, b):
        if self.image is None:
            self.status_label.value = "Please upload an image first!"
            return

        self.status_label.value = "Processing... (this may take a few minutes)"

        try:
            # Update PPAHE parameters and process image
            self.ppahe = PPAHE(
                min_window=self.min_window.value,
                max_window=self.max_window.value,
                clip_limit=self.clip_limit.value
            )

            self.enhanced = self.ppahe.enhance(self.image)

            # Display results
            with self.output:
                clear_output(wait=True)
                fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5))

                ax1.imshow(self.image, cmap='gray')
                ax1.set_title('Original Image')
                ax1.axis('off')

                ax2.imshow(self.enhanced, cmap='gray')
                ax2.set_title('Enhanced Image')
                ax2.axis('off')

                fig.tight_layout()
                plt.show()

                # Show histograms
                fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 3))

                ax1.hist(self.image.ravel(), 256, [0, 256], color='gray', alpha=0.7)
                ax1.set_title('Original Histogram')

                ax2.hist(self.enhanced.ravel(), 256, [0, 256], color='blue', alpha=0.7)
                ax2.set_title('Enhanced Histogram')

                fig.tight_layout()
                plt.show()

            # Enable download button after successful enhancement
            self.download_button.disabled = False
            self.status_label.value = "Enhancement complete! You can now download the image."

        except Exception as e:
            self.status_label.value = f"Error during enhancement: {str(e)}"
            self.download_button.disabled = True

    def on_download_click(self, b):
        """Handle download button click"""
        if self.enhanced is not None:
            try:
                # Create a temporary file in memory
                output = io.BytesIO()
                # Save the enhanced image as PNG
                Image.fromarray(self.enhanced).save(output, format='PNG')

                # Create download link
                from IPython.display import display, HTML
                import base64

                image_base64 = base64.b64encode(output.getvalue()).decode()
                download_link = f'<a download="enhanced_image.png" href="data:image/png;base64,{image_base64}">Click here to download if download doesn\'t start automatically</a>'

                # Create automatic download using JavaScript
                js_code = f"""
                <script>
                    var link = document.createElement('a');
                    link.href = 'data:image/png;base64,{image_base64}';
                    link.download = 'enhanced_image.png';
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                </script>
                """

                with self.output:
                    display(HTML(download_link + js_code))

                self.status_label.value = "Download started!"

            except Exception as e:
                self.status_label.value = f"Error during download: {str(e)}"
        else:
            self.status_label.value = "No enhanced image available for download"

# Usage
if __name__ == "__main__":
    app = PPAHENotebook()
