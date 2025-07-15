
from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class ColorStop:
    """グラデーションの色と位置を表すデータクラス"""
    pos: float
    color: List[int]  # [R, G, B, A]

@dataclass
class Colormap:
    """単一のカラーマップを表すデータクラス"""
    map_name: str
    map_type: str  # "gradient" or "indexed"
    num_colors: int = 256
    gradient_points: List[ColorStop] = field(default_factory=list)
    colors: List[List[int]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Colormap':
        """辞書からColormapオブジェクトを生成"""
        points = [ColorStop(**p) for p in data.get("gradient_points", [])]
        return cls(
            map_name=data.get("map_name", "Unnamed"),
            map_type=data.get("type", "gradient"),
            num_colors=data.get("num_colors", 256),
            gradient_points=points,
            colors=data.get("colors", [])
        )

    def to_dict(self) -> Dict[str, Any]:
        """Colormapオブジェクトを辞書に変換"""
        data = {
            "map_name": self.map_name,
            "type": self.map_type,
        }
        if self.map_type == "gradient":
            data["gradient_points"] = [{"pos": p.pos, "color": p.color} for p in self.gradient_points]
            data["num_colors"] = self.num_colors
        else: # indexed
            data["colors"] = self.colors
        
        return data

@dataclass
class ColorPack:
    """カラーマップのコレクション（パック）を表すデータクラス"""
    pack_name: str
    maps: List[Colormap] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ColorPack':
        """辞書からColorPackオブジェクトを生成"""
        maps = [Colormap.from_dict(m) for m in data.get("maps", [])]
        return cls(
            pack_name=data.get("pack_name", "Unnamed Pack"),
            maps=maps
        )

    def to_dict(self) -> Dict[str, Any]:
        """ColorPackオブジェクトを辞書に変換"""
        return {
            "pack_name": self.pack_name,
            "maps": [m.to_dict() for m in self.maps]
        }
