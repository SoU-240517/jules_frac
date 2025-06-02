import numpy as np
from numba import jit
import time # For performance testing in __main__

@jit(nopython=True, cache=True) # Numba JIT compiler, nopython mode, cache compilation
def _calculate_mandelbrot_point(c_real, c_imag, max_iters, escape_radius_sq):
    """
    Calculates Mandelbrot set for a given complex number c.
    Returns the number of iterations if it escapes, or max_iters if it does not.
    """
    z_real = 0.0
    z_imag = 0.0
    for i in range(max_iters):
        z_real_sq = z_real * z_real
        z_imag_sq = z_imag * z_imag
        if z_real_sq + z_imag_sq > escape_radius_sq:
            return i  # Escaped
        z_imag = 2.0 * z_real * z_imag + c_imag
        z_real = z_real_sq - z_imag_sq + c_real
    return max_iters  # Did not escape (or reached max_iters)

@jit(nopython=True, cache=True, parallel=True) # Enable parallel execution if Numba can optimize
def _compute_mandelbrot_grid(width_px, height_px, min_x, max_x, min_y, max_y, max_iters, escape_radius_sq):
    """
    Computes the Mandelbrot set for a grid of points.
    Returns a 2D NumPy array of escape times.
    """
    result = np.empty((height_px, width_px), dtype=np.int32)
    pixel_width_real = (max_x - min_x) / width_px
    pixel_height_imag = (max_y - min_y) / height_px

    for y_idx in range(height_px):
        c_imag = min_y + y_idx * pixel_height_imag
        for x_idx in range(width_px):
            c_real = min_x + x_idx * pixel_width_real
            result[y_idx, x_idx] = _calculate_mandelbrot_point(c_real, c_imag, max_iters, escape_radius_sq)
    return result

@jit(nopython=True, cache=True, parallel=True)
def _apply_grayscale_coloring(escape_times, max_iters):
    """
    Applies grayscale coloring to escape time data (Numba JIT compatible).
    Args:
        escape_times (numpy.ndarray): 2D array of escape times.
        max_iters (int): Maximum number of iterations.
    Returns:
        numpy.ndarray: 3D RGBA color data array (height, width, 4) of type uint8.
    """
    height, width = escape_times.shape
    colored_image = np.empty((height, width, 4), dtype=np.uint8)

    for y in range(height): # Numba can parallelize this outer loop
        for x in range(width):
            iters = escape_times[y, x]
            if iters == max_iters:  # Point is in the set
                colored_image[y, x, 0] = 0  # R
                colored_image[y, x, 1] = 0  # G
                colored_image[y, x, 2] = 0  # B
                colored_image[y, x, 3] = 255 # Alpha (opaque)
            else:
                # Grayscale mapping for points outside the set
                # A simple linear scaling: points that escape faster are darker.
                # Adjust the scaling factor for different visual effects.
                # color_val = int( (iters / max_iters) * 255 ) # Darker for faster escape

                # Brighter for faster escape (often preferred for Mandelbrot)
                # We use a slightly adjusted scale to make details more visible
                norm_iters = iters / max_iters
                # color_val = int(255 * (1.0 - norm_iters**0.25)) # sqrt or other non-linear scaling
                color_val = int(255 * (1.0 - norm_iters)) # Linear: faster escape = brighter
                color_val = max(0, min(255, color_val)) # Clamp to 0-255

                colored_image[y, x, 0] = np.uint8(color_val)  # R
                colored_image[y, x, 1] = np.uint8(color_val)  # G
                colored_image[y, x, 2] = np.uint8(color_val)  # B
                colored_image[y, x, 3] = 255 # Alpha (opaque)
    return colored_image

class FractalEngine:
    def __init__(self, image_width_px=800, image_height_px=600):
        self.max_iterations = 100
        self.center_real = -0.5
        self.center_imag = 0.0
        self.width = 3.0

        self.image_width_px = image_width_px
        self.image_height_px = image_height_px

        if self.image_width_px > 0 and self.image_height_px > 0 :
            self.height = (self.width * self.image_height_px) / self.image_width_px
        else:
            self.image_width_px = 800
            self.image_height_px = 600
            self.height = (self.width * self.image_height_px) / self.image_width_px
            print(f"Warning: Initial image dimensions were invalid, reset to {self.image_width_px}x{self.image_height_px}.")

        self.escape_radius = 2.0

    def update_image_size(self, image_width_px, image_height_px):
        if image_width_px <= 0 or image_height_px <= 0:
            print(f"Warning: Invalid image dimensions ({image_width_px}x{image_height_px}). Not updating.")
            return
        self.image_width_px = image_width_px
        self.image_height_px = image_height_px
        self.update_aspect_ratio()

    def update_aspect_ratio(self):
        if self.image_width_px > 0:
            self.height = (self.width * self.image_height_px) / self.image_width_px
        else:
            self.height = self.width
            print("Warning: image_width_px is zero, aspect ratio might be incorrect.")

    def set_parameters(self, center_real, center_imag, width, max_iterations=None):
        self.center_real = center_real
        self.center_imag = center_imag
        self.width = width
        if max_iterations is not None:
            self.max_iterations = max_iterations
        self.update_aspect_ratio()

    def compute_mandelbrot(self):
        if self.image_width_px <= 0 or self.image_height_px <= 0:
            print(f"Error: Cannot compute Mandelbrot with invalid image dimensions: "
                  f"{self.image_width_px}x{self.image_height_px}")
            return np.zeros((1, 1), dtype=np.int32)

        print(f"Mandelbrot computation started: "
              f"Size={self.image_width_px}x{self.image_height_px}, "
              f"Center=({self.center_real:.4f}, {self.center_imag:.4f}), "
              f"Width={self.width:.4e}, Height={self.height:.4e}, "
              f"Iterations={self.max_iterations}")

        min_x = self.center_real - self.width / 2.0
        max_x = self.center_real + self.width / 2.0
        min_y = self.center_imag - self.height / 2.0
        max_y = self.center_imag + self.height / 2.0
        escape_radius_sq = self.escape_radius * self.escape_radius

        mandelbrot_data = _compute_mandelbrot_grid(
            self.image_width_px, self.image_height_px,
            min_x, max_x, min_y, max_y,
            self.max_iterations, escape_radius_sq
        )

        print("Mandelbrot computation complete.")
        return mandelbrot_data

    def apply_basic_coloring(self, escape_times):
        """
        Applies basic grayscale coloring to the computed escape times.
        Args:
            escape_times (numpy.ndarray): Array of escape times from compute_mandelbrot.
        Returns:
            numpy.ndarray: RGBA color data array (height, width, 4) of type uint8.
        """
        print("Coloring process started...")
        if escape_times is None or escape_times.size == 0 :
             print("Warning: No escape time data to color. Returning blank image.")
             # Ensure height and width are positive, otherwise use a default small size
             h = self.image_height_px if self.image_height_px > 0 else 1
             w = self.image_width_px if self.image_width_px > 0 else 1
             return np.zeros((h, w, 4), dtype=np.uint8)

        # Call the Numba JIT-compiled grayscale coloring function
        colored_data = _apply_grayscale_coloring(escape_times, self.max_iterations)

        print("Coloring process complete.")
        return colored_data

if __name__ == '__main__':
    print("Running FractalEngine standalone test with coloring...")
    engine = FractalEngine(image_width_px=300, image_height_px=200) # Initial small size

    print("\nTesting with specific parameters (includes Numba JIT compilation time for coloring on first run):")
    engine.set_parameters(center_real=-0.745, center_imag=0.113, width=0.005, max_iterations=300)

    start_time = time.time()
    mandel_data = engine.compute_mandelbrot()
    mandel_end_time = time.time()
    colored_image = engine.apply_basic_coloring(mandel_data)
    coloring_end_time = time.time()

    print(f"Mandelbrot calculation time: {mandel_end_time - start_time:.4f} seconds")
    print(f"Coloring time: {coloring_end_time - mandel_end_time:.4f} seconds")
    print(f"Total time (computation + coloring): {coloring_end_time - start_time:.4f} seconds")
    print(f"Escape time data shape: {mandel_data.shape}, dtype: {mandel_data.dtype}")
    print(f"Colored image data shape: {colored_image.shape}, dtype: {colored_image.dtype}")

    # Test with larger dimensions and different parameters
    print("\nTesting with larger image (600x400, 500 iterations):")
    engine.update_image_size(600, 400)
    engine.set_parameters(center_real=-0.743643887037151, center_imag=0.131825904205330, width=0.002, max_iterations=500) # Seahorse

    start_time_large = time.time()
    mandel_data_large = engine.compute_mandelbrot()
    mandel_end_time_large = time.time()
    colored_image_large = engine.apply_basic_coloring(mandel_data_large)
    coloring_end_time_large = time.time()

    print(f"Mandelbrot calculation time (large): {mandel_end_time_large - start_time_large:.4f} seconds")
    print(f"Coloring time (large): {coloring_end_time_large - mandel_end_time_large:.4f} seconds")
    print(f"Total time (large): {coloring_end_time_large - start_time_large:.4f} seconds")

    try:
        import matplotlib.pyplot as plt
        print("\nPlotting results (Escape Times and Grayscale Colored Image)...")
        fig, axes = plt.subplots(1, 2, figsize=(13, 6))

        # Plot escape times
        im1 = axes[0].imshow(mandel_data_large, cmap='magma',
                             extent=(engine.center_real - engine.width/2, engine.center_real + engine.width/2,
                                     engine.center_imag - engine.height/2, engine.center_imag + engine.height/2),
                             origin='lower')
        axes[0].set_title(f"Escape Times (Numba)\nIter: {engine.max_iterations}")
        axes[0].set_xlabel("Real")
        axes[0].set_ylabel("Imaginary")
        fig.colorbar(im1, ax=axes[0], label="Iterations", fraction=0.046, pad=0.04)

        # Plot colored image
        axes[1].imshow(colored_image_large,
                       extent=(engine.center_real - engine.width/2, engine.center_real + engine.width/2,
                               engine.center_imag - engine.height/2, engine.center_imag + engine.height/2),
                       origin='lower')
        axes[1].set_title(f"Grayscale Colored (Numba)\nView: {engine.image_width_px}x{engine.image_height_px}px")
        axes[1].set_xlabel("Real")
        axes[1].set_ylabel("Imaginary")

        plt.suptitle(f"Mandelbrot: Center({engine.center_real:.4f}, {engine.center_imag:.4f}), Width:{engine.width:.2e}", fontsize=14)
        plt.tight_layout(rect=[0, 0, 1, 0.96]) # Adjust layout to make space for suptitle
        plt.show()
    except ImportError:
        print("matplotlib is not installed. Skipping plot.")
    except Exception as e:
        print(f"An error occurred during plotting: {e}")

    print("\nFractalEngine standalone test with coloring finished.")
