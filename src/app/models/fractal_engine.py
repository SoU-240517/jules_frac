import numpy as np

class FractalEngine:
    def __init__(self, image_width_px=800, image_height_px=600):
        self.max_iterations = 100
        self.center_real = -0.5
        self.center_imag = 0.0
        self.width = 3.0  # Real width of the complex plane to view

        self.image_width_px = image_width_px
        self.image_height_px = image_height_px
        # Calculate the height of the complex plane view to maintain aspect ratio
        if self.image_width_px > 0:
            self.height = (self.width * self.image_height_px) / self.image_width_px
        else:
            self.height = self.width # Default or fallback

        self.escape_radius = 2.0  # Standard escape radius for Mandelbrot set

    def update_image_size(self, image_width_px, image_height_px):
        """Updates the pixel dimensions of the image and recalculates the complex plane height."""
        if image_width_px <= 0 or image_height_px <= 0:
            # Potentially raise an error or handle as appropriate
            print(f"Warning: Invalid image dimensions ({image_width_px}x{image_height_px}). Not updating.")
            return

        self.image_width_px = image_width_px
        self.image_height_px = image_height_px
        self.update_aspect_ratio()

    def update_aspect_ratio(self):
        """Recalculates the height of the complex plane view based on current width and pixel dimensions."""
        if self.image_width_px > 0:
            self.height = (self.width * self.image_height_px) / self.image_width_px
        else:
            # This case should ideally be prevented by checks in update_image_size
            self.height = self.width
            print("Warning: image_width_px is zero, aspect ratio might be incorrect.")


    def set_parameters(self, center_real, center_imag, width, max_iterations=None):
        """Sets the core parameters for the fractal generation."""
        self.center_real = center_real
        self.center_imag = center_imag
        self.width = width
        if max_iterations is not None:
            self.max_iterations = max_iterations
        self.update_aspect_ratio() # Recalculate height as width might have changed

    def compute_mandelbrot(self):
        """
        Placeholder for the actual Mandelbrot computation.
        Returns a 2D NumPy array of zeros with the current image dimensions.
        """
        print(f"Placeholder: Mandelbrot computation (size: {self.image_width_px}x{self.image_height_px}, "
              f"center: ({self.center_real}, {self.center_imag}), width: {self.width}, "
              f"iter: {self.max_iterations})")
        return np.zeros((self.image_height_px, self.image_width_px), dtype=np.int32)

if __name__ == '__main__':
    # Simple test for the FractalEngine
    engine = FractalEngine(image_width_px=800, image_height_px=600)
    print(f"Initial parameters: center=({engine.center_real}, {engine.center_imag}), "
          f"width={engine.width}, height={engine.height}, max_iter={engine.max_iterations}")

    engine.set_parameters(center_real=-0.7, center_imag=0.3, width=2.0, max_iterations=200)
    print(f"Updated parameters: center=({engine.center_real}, {engine.center_imag}), "
          f"width={engine.width}, height={engine.height}, max_iter={engine.max_iterations}")

    dummy_data = engine.compute_mandelbrot()
    print(f"Dummy data shape: {dummy_data.shape}")

    engine.update_image_size(image_width_px=1024, image_height_px=768)
    print(f"After image size update: image_width_px={engine.image_width_px}, "
          f"image_height_px={engine.image_height_px}, height={engine.height}")

    dummy_data_resized = engine.compute_mandelbrot()
    print(f"Resized dummy data shape: {dummy_data_resized.shape}")

    # Test edge case for image size update
    engine.update_image_size(0, 0) # Should print a warning
    print(f"After invalid image size update attempt: height={engine.height}")

    engine = FractalEngine(image_width_px=0, image_height_px=0) # Test constructor with invalid size
    print(f"Engine with initial invalid size: width={engine.width}, height={engine.height}")
