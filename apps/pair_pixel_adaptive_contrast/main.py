import numpy as np
from scipy.ndimage import gaussian_filter
from typing import Tuple, Optional

class PPAHE:
    """
    Per-Pixel Adaptive Histogram Equalization (PPAHE)
    
    This technique creates dynamic neighborhood sizes for each pixel based on local
    image characteristics, then performs contrast-limited histogram equalization
    using these adaptive regions.
    """
    
    def __init__(
        self,
        min_window: int = 3,
        max_window: int = 65,
        clip_limit: float = 3.0,
        n_bins: int = 256
    ):
        """
        Initialize PPAHE parameters.
        
        Args:
            min_window: Minimum window size (must be odd)
            max_window: Maximum window size (must be odd)
            clip_limit: Similar to CLAHE's clip limit
            n_bins: Number of histogram bins
        """
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
        """
        Compute local variance and gradient magnitude to determine optimal
        window sizes for each pixel.
        """
        # Calculate local variance
        local_mean = gaussian_filter(image, sigma)
        local_sqr_mean = gaussian_filter(image ** 2, sigma)
        variance = local_sqr_mean - local_mean ** 2
        
        # Calculate gradient magnitude
        grad_x = np.gradient(image, axis=1)
        grad_y = np.gradient(image, axis=0)
        gradient_magnitude = np.sqrt(grad_x ** 2 + grad_y ** 2)
        
        return variance, gradient_magnitude
    
    def _determine_window_sizes(
        self,
        variance: np.ndarray,
        gradient_magnitude: np.ndarray
    ) -> np.ndarray:
        """
        Determine optimal window size for each pixel based on local statistics.
        """
        # Normalize both measures to [0, 1]
        norm_var = (variance - variance.min()) / (variance.max() - variance.min())
        norm_grad = (gradient_magnitude - gradient_magnitude.min()) / \
                   (gradient_magnitude.max() - gradient_magnitude.min())
        
        # Combine measures (high variance or high gradient → smaller window)
        combined_measure = (norm_var + norm_grad) / 2
        
        # Map to window sizes (inverse relationship)
        window_range = self.max_window - self.min_window
        window_sizes = self.max_window - (combined_measure * window_range)
        
        # Ensure odd window sizes
        window_sizes = (np.round(window_sizes) // 2 * 2 + 1).astype(int)
        return np.clip(window_sizes, self.min_window, self.max_window)
    
    def _get_adaptive_neighborhood(
        self,
        image: np.ndarray,
        center_y: int,
        center_x: int,
        window_size: int
    ) -> np.ndarray:
        """
        Extract neighborhood around a pixel with padding for boundary cases.
        """
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
        """
        Perform contrast-limited histogram equalization on a neighborhood.
        """
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
            
        # Calculate CDF
        cdf = hist.cumsum()
        cdf = (cdf - cdf.min()) * 255 / (cdf.max() - cdf.min())
        
        # Map center pixel
        return int(np.interp(center_value, bins[:-1], cdf))
    
    def enhance(self, image: np.ndarray) -> np.ndarray:
        """
        Enhance image using Per-Pixel Adaptive Histogram Equalization.
        
        Args:
            image: Input image (grayscale, uint8)
            
        Returns:
            Enhanced image
        """
        if image.dtype != np.uint8:
            raise ValueError("Image must be uint8")
            
        # Compute local statistics
        variance, gradient = self._compute_local_statistics(image)
        
        # Determine window sizes
        window_sizes = self._determine_window_sizes(variance, gradient)
        
        # Initialize output
        enhanced = np.zeros_like(image)
        
        # Process each pixel
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
                
        return enhanced