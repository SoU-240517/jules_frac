---
inclusion: always
---

# Technology Stack

## Core Technologies
- **Python 3.x** - Primary language
- **PyQt6** - GUI framework for desktop application
- **NumPy** - Numerical computations and array operations
- **Numba** - JIT compilation for performance-critical fractal calculations
- **Matplotlib** - Color mapping and visualization utilities
- **Pillow (PIL)** - Image processing and export
- **scikit-learn** - Advanced mathematical operations

## Architecture Pattern
- **MVC (Model-View-Controller)** - Clear separation of concerns
- **Plugin System** - Extensible fractal and coloring algorithms
- **Signal-Slot Pattern** - PyQt6 event handling and component communication

## Configuration
- **JSONC format** - Settings stored in `settings.jsonc` with comments support
- **Dynamic plugin loading** - Runtime discovery and instantiation of plugins
- **Preset system** - Save/load complete application states

## Performance Optimization
- **Numba JIT compilation** - Critical fractal calculation functions are compiled
- **Configurable caching** - Numba cache management through settings
- **Multi-threading** - Background rendering using QThreadPool

## Common Commands
```bash
# Install dependencies
pip install -r requirements.txt

# Run application
python main.py

# Clear Numba cache (if needed)
# Handled automatically through app settings
```

## Development Notes
- Use `@numba.jit` decorators for performance-critical mathematical functions
- Follow PyQt6 signal-slot patterns for UI communication
- Plugin classes must inherit from base abstract classes
- Japanese comments and UI elements are part of the codebase