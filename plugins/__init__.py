# This file can be empty.
# It tells Python that the 'plugins' directory is a package.

# Make base plugin classes easily accessible
from .base_fractal_plugin import FractalPlugin
from .base_coloring_plugin import ColoringAlgorithmPlugin

__all__ = ['FractalPlugin', 'ColoringAlgorithmPlugin']
