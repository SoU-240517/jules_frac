# このファイルは空でも構いません。
# Pythonに対して 'plugins' ディレクトリがパッケージであることを示します。

# 基本プラグインクラスを簡単にアクセスできるようにする
from .base_fractal_plugin import FractalPlugin
from .base_coloring_plugin import ColoringAlgorithmPlugin

__all__ = ['FractalPlugin', 'ColoringAlgorithmPlugin']
