import json
from pathlib import Path
import numpy as np

class ColorManager:
    def __init__(self, color_packs_dir: str = "assets/colorpacks"):
        # color_packs_dir はプロジェクトルートからの相対パスを期待
        self.color_packs_dir = Path(color_packs_dir)
        self.color_packs = {}  # {pack_name: {map_name: list_of_rgb_tuples, ...}}
        self.load_color_packs()

    def _generate_gradient_colors(self, gradient_points: list[dict], num_colors: int) -> list[tuple[int, int, int]]:
        if not gradient_points:
            # フォールバック: 黒のリストを返すか、エラーを発生させる
            print("ColorManager Warning: _generate_gradient_colors called with no gradient points.")
            return [(0, 0, 0)] * num_colors
        if num_colors <= 0:
            return []

        # ポイントを位置 (pos) でソート
        points = sorted(gradient_points, key=lambda p: p['pos'])

        # 出力用のカラーリスト
        output_colors = []

        # 各ポイントの位置と色値を抽出
        # 位置を 0 から num_colors-1 のインデックススケールに変換
        # ただし、np.interpはソートされたxpを期待するので、元の0-1スケールで良い
        positions = np.array([p['pos'] for p in points])

        colors_r = np.array([p['color'][0] for p in points])
        colors_g = np.array([p['color'][1] for p in points])
        colors_b = np.array([p['color'][2] for p in points])

        # 補間する新しい位置 (0.0 から 1.0 の範囲で均等に配置)
        target_positions = np.linspace(0.0, 1.0, num_colors)

        interp_r = np.interp(target_positions, positions, colors_r)
        interp_g = np.interp(target_positions, positions, colors_g)
        interp_b = np.interp(target_positions, positions, colors_b)

        for i in range(num_colors):
            output_colors.append(
                (int(round(np.clip(interp_r[i], 0, 255))), # np.clipで範囲内に収める
                 int(round(np.clip(interp_g[i], 0, 255))),
                 int(round(np.clip(interp_b[i], 0, 255))))
            )
        return output_colors

    def load_color_packs(self):
        self.color_packs.clear()

        # プロジェクトルートからの相対パスとして解決 (より堅牢な方法)
        # このファイル(color_manager.py)の場所からプロジェクトルートを推定するのは難しい場合がある。
        # main.pyなどでアプリケーションルートを決定し、それを基準に絶対パスを構成するのが望ましい。
        # ここでは、渡されたパスがプロジェクトルートからの相対パスであると仮定する。
        # もしカレントディレクトリがプロジェクトルートでない場合、このPath解決は期待通りに動かない可能性がある。
        # 簡単のため、ここでは Path.cwd() / self.color_packs_dir を使う。
        # より良いのは、アプリケーションの起動時にルートパスを決定し、それをベースパスとして渡すこと。

        # effective_packs_dir = self.color_packs_dir # このままだとカレントワーキングディレクトリに依存
        # 実行時のカレントディレクトリをプロジェクトルートと仮定した場合
        effective_packs_dir = Path.cwd() / self.color_packs_dir
        if not self.color_packs_dir.is_absolute(): # もし相対パスで与えられたらカレントディレクトリ基準
             effective_packs_dir = Path.cwd() / self.color_packs_dir
        else: # 絶対パスならそのまま
             effective_packs_dir = self.color_packs_dir


        print(f"ColorManager: Loading color packs from directory: {effective_packs_dir.resolve()}")
        if not effective_packs_dir.is_dir():
            print(f"ColorManager Error: Color pack directory not found: {effective_packs_dir.resolve()}")
            return

        for file_path in effective_packs_dir.glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                pack_name = data.get("pack_name")
                maps_data = data.get("maps")

                if not pack_name or not isinstance(maps_data, list):
                    print(f"ColorManager Warning: Invalid or incomplete format in file: {file_path.name}")
                    continue

                current_pack_maps = {}
                for map_entry in maps_data:
                    map_name = map_entry.get("map_name")
                    if not map_name:
                        print(f"ColorManager Warning: Map entry without name in {pack_name} from {file_path.name}")
                        continue

                    if "colors" in map_entry and isinstance(map_entry["colors"], list):
                        colors_list = [tuple(c) for c in map_entry["colors"] if isinstance(c, list) and len(c) == 3 and all(isinstance(x, int) for x in c)]
                        if colors_list: # Ensure not empty after validation
                           current_pack_maps[map_name] = colors_list
                        else:
                            print(f"ColorManager Warning: Invalid color format in '{pack_name}/{map_name}'.")
                    elif "gradient_points" in map_entry and "num_colors" in map_entry:
                        gradient_points = map_entry["gradient_points"]
                        num_colors = map_entry["num_colors"]
                        if isinstance(gradient_points, list) and isinstance(num_colors, int) and num_colors > 0:
                            colors_list = self._generate_gradient_colors(gradient_points, num_colors)
                            current_pack_maps[map_name] = colors_list
                        else:
                            print(f"ColorManager Warning: Invalid gradient definition in '{pack_name}/{map_name}'.")
                    else:
                        print(f"ColorManager Warning: No valid color definition found for '{pack_name}/{map_name}'.")

                if current_pack_maps:
                    if pack_name in self.color_packs:
                         print(f"ColorManager Warning: Color pack name '{pack_name}' is a duplicate. Merging maps or overwriting might occur.")
                    self.color_packs.setdefault(pack_name, {}).update(current_pack_maps)
                    print(f"ColorManager: Loaded color pack '{pack_name}' ({len(current_pack_maps)} maps) from {file_path.name}.")

            except json.JSONDecodeError as e:
                print(f"ColorManager Error: Failed to parse JSON from {file_path.name}: {e}")
            except Exception as e:
                print(f"ColorManager Error: Unexpected error processing file '{file_path.name}': {e}")

        if not self.color_packs:
            print("ColorManager: No valid color packs were loaded.")

    def get_available_color_pack_names(self) -> list[str]:
        return list(self.color_packs.keys())

    def get_color_maps_in_pack(self, pack_name: str) -> list[str]:
        return list(self.color_packs.get(pack_name, {}).keys())

    def get_color_map_data(self, pack_name: str, map_name: str) -> list[tuple[int, int, int]] | None:
        return self.color_packs.get(pack_name, {}).get(map_name)

if __name__ == '__main__':
    # Create temporary directory and files for testing
    # This assumes the script is run from a location where it can create "temp_color_packs"
    temp_dir = Path("temp_color_packs_test")
    temp_dir.mkdir(exist_ok=True)

    default_pack_content = {
        "pack_name": "デフォルトテスト",
        "maps": [
            {"map_name": "グレースケール16", "type": "gradient",
             "gradient_points": [{"pos":0.0,"color":[0,0,0]}, {"pos":1.0,"color":[240,240,240]}], "num_colors": 16},
            {"map_name": "RGB固定", "colors": [[255,0,0],[0,255,0],[0,0,255]]}
        ]
    }
    with open(temp_dir / "default_test.json", "w", encoding="utf-8") as f:
        json.dump(default_pack_content, f, indent=4)

    custom_pack_content = {
        "pack_name": "カスタムテスト",
        "maps": [
            {"map_name": "火山", "type": "gradient", "gradient_points": [
                {"pos":0.0, "color":[10,0,0]}, {"pos":0.5, "color":[255,0,0]},
                {"pos":0.75, "color":[255,255,0]}, {"pos":1.0, "color":[255,255,255]}
            ], "num_colors": 256}
        ]
    }
    with open(temp_dir / "custom_test.json", "w", encoding="utf-8") as f:
        json.dump(custom_pack_content, f, indent=4)

    print(f"ColorManager test: Using temporary directory '{temp_dir.resolve()}'")
    manager = ColorManager(color_packs_dir=str(temp_dir)) # Pass the temp dir path

    pack_names = manager.get_available_color_pack_names()
    print(f"\nAvailable color packs: {pack_names}")
    assert "デフォルトテスト" in pack_names
    assert "カスタムテスト" in pack_names

    if pack_names:
        first_pack_name = "デフォルトテスト"
        map_names = manager.get_color_maps_in_pack(first_pack_name)
        print(f"\nColor maps in '{first_pack_name}': {map_names}")
        assert "グレースケール16" in map_names
        assert "RGB固定" in map_names

        if map_names:
            map_name_gradient = "グレースケール16"
            map_data_gradient = manager.get_color_map_data(first_pack_name, map_name_gradient)
            if map_data_gradient:
                print(f"  '{first_pack_name}/{map_name_gradient}' first 3 colors: {map_data_gradient[:3]}")
                print(f"  '{first_pack_name}/{map_name_gradient}' number of colors: {len(map_data_gradient)}")
                assert len(map_data_gradient) == 16
                assert map_data_gradient[0] == (0,0,0)
                assert map_data_gradient[-1] == (240,240,240)

            map_name_fixed = "RGB固定"
            map_data_fixed = manager.get_color_map_data(first_pack_name, map_name_fixed)
            if map_data_fixed:
                print(f"  '{first_pack_name}/{map_name_fixed}' colors: {map_data_fixed}")
                assert len(map_data_fixed) == 3
                assert map_data_fixed[0] == (255,0,0)

    # Clean up temporary directory
    import shutil
    try:
        shutil.rmtree(temp_dir)
        print(f"\nCleaned up temporary directory: {temp_dir}")
    except Exception as e:
        print(f"\nError cleaning up temporary directory {temp_dir}: {e}")

    print("\nColorManager test finished.")
