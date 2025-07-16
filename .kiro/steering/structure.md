---
inclusion: always
---

# Project Structure

## Root Level
- `main.py` - Application entry point and initialization
- `settings.jsonc` - Main configuration file with app settings and presets
- `settings_manager.py` - Configuration management utility
- `requirements.txt` - Python dependencies

## Core Architecture (MVC Pattern)

### Models (`models/`)
- `fractal_engine.py` - Core fractal computation engine
- `colormap.py` - Color mapping and palette management

### Views (`views/`)
- `main_window.py` - Primary application window
- `render_area.py` - Fractal display widget
- `parameter_panel.py` - UI controls for fractal parameters
- `high_res_dialog.py` - High-resolution export dialog
- `style.qss` - Application stylesheet
- `colormap_editor/` - Color palette editing interface

### Controllers (`controllers/`)
- `fractal_controller.py` - Main application controller
- `fractal_renderer.py` - Rendering coordination and threading

## Plugin System (`plugins/`)
- `base_fractal_plugin.py` - Abstract base for fractal algorithms
- `base_coloring_plugin.py` - Abstract base for coloring schemes
- `plugin_manager.py` - Dynamic plugin loading and management
- `fractals/` - Fractal algorithm implementations
- `coloring/` - Coloring algorithm implementations
- `colorpacks/` - Predefined color palettes

## Supporting Modules

### Utilities (`utils/`)
- `numba_utils.py` - Numba JIT compilation utilities

### Coloring (`coloring/`)
- `color_manager.py` - Color processing and management

### Export (`export/`)
- `image_exporter.py` - High-resolution image export functionality

### Logging (`logger/`)
- `custom_logger.py` - Application logging system

## Naming Conventions
- **Files**: snake_case (e.g., `fractal_engine.py`)
- **Classes**: PascalCase (e.g., `FractalEngine`)
- **Methods/Variables**: snake_case (e.g., `render_fractal`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `MAX_ITERATIONS`)

## Plugin Development
- Fractal plugins inherit from `FractalPlugin`
- Coloring plugins inherit from `ColoringAlgorithmPlugin`
- Plugins are auto-discovered from their respective folders
- Each plugin must implement required abstract methods

## Configuration Hierarchy
1. Default values in code
2. `settings.jsonc` application settings
3. Runtime parameter changes
4. Preset overrides