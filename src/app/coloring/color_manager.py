import json
from pathlib import Path
import numpy as np

class ColorManager:
    """カラーパックとカラーマップを管理するクラス。"""
    def __init__(self, color_packs_dir: str = "assets/colorpacks"):
        # color_packs_dir はプロジェクトルートからの相対パスを想定
        self.color_packs_dir = Path(color_packs_dir)
        self.color_packs = {}  # {パック名: {マップ名: RGBタプルのリスト, ...}}
        self.load_color_packs()

    def _generate_gradient_colors(self, gradient_points: list[dict], num_colors: int) -> list[tuple[int, int, int]]:
        """指定されたグラデーションポイントと色数に基づいてグラデーションカラーを生成する。"""
        if not gradient_points:
            # フォールバック: 黒のリストを返すか、エラーを発生させる
            print("ColorManager 警告: _generate_gradient_colors がグラデーションポイントなしで呼び出されました。")
            return [(0, 0, 0)] * num_colors
        if num_colors <= 0:
            return []

        # ポイントを位置 (pos) でソートする
        points = sorted(gradient_points, key=lambda p: p['pos'])

        # 出力用のカラーリスト
        output_colors = []

        # 各ポイントの位置と色値を抽出する
        # np.interpはソートされたxpを期待するため、元の0-1スケールを使用する
        positions = np.array([p['pos'] for p in points])

        colors_r = np.array([p['color'][0] for p in points])
        colors_g = np.array([p['color'][1] for p in points])
        colors_b = np.array([p['color'][2] for p in points])

        # 補間する新しい位置 (0.0 から 1.0 の範囲で均等に配置する)
        target_positions = np.linspace(0.0, 1.0, num_colors)

        interp_r = np.interp(target_positions, positions, colors_r)
        interp_g = np.interp(target_positions, positions, colors_g)
        interp_b = np.interp(target_positions, positions, colors_b)

        for i in range(num_colors):
            output_colors.append(
                (int(round(np.clip(interp_r[i], 0, 255))), # np.clipで値を0-255の範囲に収める
                 int(round(np.clip(interp_g[i], 0, 255))),
                 int(round(np.clip(interp_b[i], 0, 255))))
            )
        return output_colors

    def load_color_packs(self):
        self.color_packs.clear()

        # プロジェクトルートからの相対パスとして解決する (より堅牢な方法が望ましい)
        # このファイル(color_manager.py)の場所からプロジェクトルートを推定するのは困難な場合がある。
        # main.pyなどでアプリケーションのルートディレクトリを決定し、
        # それを基準に絶対パスを構成するのがより望ましいアプローチである。
        # ここでは、渡されたパスがプロジェクトルートからの相対パスであると仮定する。
        # カレントワーキングディレクトリがプロジェクトルートでない場合、
        # このPath解決は期待通りに動作しない可能性がある。
        # 簡単のため、ここでは Path.cwd() / self.color_packs_dir を使用する。
        # より良い方法は、アプリケーション起動時にルートパスを決定し、それをベースパスとして渡すことである。

        # effective_packs_dir = self.color_packs_dir # このままではカレントワーキングディレクトリに依存する
        # 実行時のカレントディレクトリがプロジェクトルートであると仮定した場合
        effective_packs_dir = Path.cwd() / self.color_packs_dir
        if not self.color_packs_dir.is_absolute(): # 相対パスで与えられた場合はカレントディレクトリを基準とする
             effective_packs_dir = Path.cwd() / self.color_packs_dir
        else: # 絶対パスの場合はそのまま使用する
             effective_packs_dir = self.color_packs_dir


        print(f"ColorManager: ディレクトリからカラーパックを読み込み中: {effective_packs_dir.resolve()}")
        if not effective_packs_dir.is_dir():
            print(f"ColorManager エラー: カラーパックディレクトリが見つかりません: {effective_packs_dir.resolve()}")
            return

        for file_path in effective_packs_dir.glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                pack_name = data.get("pack_name")
                maps_data = data.get("maps")

                if not pack_name or not isinstance(maps_data, list):
                    print(f"ColorManager 警告: ファイル形式が無効または不完全です: {file_path.name}")
                    continue

                current_pack_maps = {}
                for map_entry in maps_data:
                    map_name = map_entry.get("map_name")
                    if not map_name:
                        print(f"ColorManager 警告: {pack_name} ({file_path.name}由来) に名前のないマップエントリがあります。")
                        continue

                    if "colors" in map_entry and isinstance(map_entry["colors"], list):
                        colors_list = [tuple(c) for c in map_entry["colors"] if isinstance(c, list) and len(c) == 3 and all(isinstance(x, int) for x in c)]
                        if colors_list: # 検証後に空でないことを確認
                           current_pack_maps[map_name] = colors_list
                        else:
                            print(f"ColorManager 警告: '{pack_name}/{map_name}' のカラーフォーマットが無効です。")
                    elif "gradient_points" in map_entry and "num_colors" in map_entry:
                        gradient_points = map_entry["gradient_points"]
                        num_colors = map_entry["num_colors"]
                        if isinstance(gradient_points, list) and isinstance(num_colors, int) and num_colors > 0:
                            colors_list = self._generate_gradient_colors(gradient_points, num_colors)
                            current_pack_maps[map_name] = colors_list
                        else:
                            print(f"ColorManager 警告: '{pack_name}/{map_name}' のグラデーション定義が無効です。")
                    else:
                        print(f"ColorManager 警告: '{pack_name}/{map_name}' に有効なカラー定義が見つかりません。")

                if current_pack_maps:
                    if pack_name in self.color_packs:
                         print(f"ColorManager 警告: カラーパック名 '{pack_name}' は重複しています。マップのマージまたは上書きが発生する可能性があります。")
                    self.color_packs.setdefault(pack_name, {}).update(current_pack_maps)
                    print(f"ColorManager: カラーパック '{pack_name}' ({len(current_pack_maps)} マップ) を {file_path.name} から読み込みました。")

            except json.JSONDecodeError as e:
                print(f"ColorManager エラー: {file_path.name} からのJSON解析に失敗しました: {e}")
            except Exception as e:
                print(f"ColorManager エラー: ファイル '{file_path.name}' の処理中に予期せぬエラーが発生しました: {e}")

        if not self.color_packs:
            print("ColorManager: 有効なカラーパックは読み込まれませんでした。")

    def get_available_color_pack_names(self) -> list[str]:
        """利用可能なすべてのカラーパック名のリストを返す。"""
        return list(self.color_packs.keys())

    def get_color_maps_in_pack(self, pack_name: str) -> list[str]:
        """指定されたカラーパック内のすべてのカラーマップ名のリストを返す。"""
        return list(self.color_packs.get(pack_name, {}).keys())

    def get_color_map_data(self, pack_name: str, map_name: str) -> list[tuple[int, int, int]] | None:
        """指定されたカラーパックとマップ名に対応するカラーデータのリスト (RGBタプルのリスト) を返す。"""
        return self.color_packs.get(pack_name, {}).get(map_name)

if __name__ == '__main__':
    # テスト用の一時ディレクトリとファイルを作成する
    # このスクリプトは "temp_color_packs" を作成できる場所から実行されることを想定している
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

    print(f"ColorManager テスト: 一時ディレクトリ '{temp_dir.resolve()}' を使用中")
    manager = ColorManager(color_packs_dir=str(temp_dir)) # 一時ディレクトリのパスを渡す

    pack_names = manager.get_available_color_pack_names()
    print(f"\n利用可能なカラーパック: {pack_names}")
    assert "デフォルトテスト" in pack_names
    assert "カスタムテスト" in pack_names

    if pack_names:
        first_pack_name = "デフォルトテスト"
        map_names = manager.get_color_maps_in_pack(first_pack_name)
        print(f"\n'{first_pack_name}' 内のカラーマップ: {map_names}")
        assert "グレースケール16" in map_names
        assert "RGB固定" in map_names

        if map_names:
            map_name_gradient = "グレースケール16"
            map_data_gradient = manager.get_color_map_data(first_pack_name, map_name_gradient)
            if map_data_gradient:
                print(f"  '{first_pack_name}/{map_name_gradient}' 最初の3色: {map_data_gradient[:3]}")
                print(f"  '{first_pack_name}/{map_name_gradient}' 色数: {len(map_data_gradient)}")
                assert len(map_data_gradient) == 16
                assert map_data_gradient[0] == (0,0,0)
                assert map_data_gradient[-1] == (240,240,240)

            map_name_fixed = "RGB固定"
            map_data_fixed = manager.get_color_map_data(first_pack_name, map_name_fixed)
            if map_data_fixed:
                print(f"  '{first_pack_name}/{map_name_fixed}' カラー: {map_data_fixed}")
                assert len(map_data_fixed) == 3
                assert map_data_fixed[0] == (255,0,0)

    # 一時ディレクトリをクリーンアップ
    import shutil
    try:
        shutil.rmtree(temp_dir)
        print(f"\n一時ディレクトリをクリーンアップしました: {temp_dir}")
    except Exception as e:
        print(f"\n一時ディレクトリ {temp_dir} のクリーンアップ中にエラーが発生しました: {e}")

    print("\nColorManager テスト終了。")
