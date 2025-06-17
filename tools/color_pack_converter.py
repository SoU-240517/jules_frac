import json
import argparse
import sys
import glob
from pathlib import Path

def hex_to_rgb(hex_color: str) -> list[int] | None:
    """
    16進数カラーコード文字列 (#RRGGBB) をRGB値のリスト ([R, G, B]) に変換します。
    変換に失敗した場合は None を返します。
    """
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        try:
            return [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]
        except ValueError:
            return None
    return None

def convert_files_to_pack(input_patterns: list[str], output_file: str, pack_name: str, use_gradient: bool, num_points: int):
    """
    指定されたファイルパターンに一致する複数のカラーファイルを読み込み、
    一つのカラーパックJSONファイルに変換して保存します。
    """
    input_files = []
    for pattern in input_patterns:
        matched_files = glob.glob(pattern, recursive=True)
        if not matched_files:
            print(f"警告: パターン '{pattern}' に一致するファイルが見つかりませんでした。")
        input_files.extend(matched_files)

    if not input_files:
        print("エラー: 有効な入力ファイルが一つも見つかりませんでした。プログラムを終了します。")
        sys.exit(1)

    unique_files = sorted(list(set(input_files)))
    print(f"合計 {len(unique_files)} 個のファイルが見つかりました。処理を開始します...")

    output_data = {"pack_name": pack_name, "maps": []}

    for file_path_str in unique_files:
        file_path = Path(file_path_str)
        print(f"  - 処理中: {file_path.name}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            map_name, hex_colors = data.get("name"), data.get("colors")
            if not map_name or not isinstance(hex_colors, list):
                print(f"    警告: '{file_path.name}' は期待される形式ではありません。スキップします。")
                continue

            valid_rgb_colors = [rgb for rgb in (hex_to_rgb(hc) for hc in hex_colors) if rgb is not None]
            if not valid_rgb_colors:
                print(f"    警告: '{file_path.name}' から有効な色を読み込めませんでした。マップをスキップします。")
                continue

            num_colors = len(valid_rgb_colors)

            # <<< 修正箇所 >>>
            # --gradient フラグがあり、色数が指定ポイント数より多い場合に変換
            if use_gradient and num_colors > num_points and num_points >= 2:
                print(f"    -> グラデーション形式に変換します ({num_points} ポイント)。")
                gradient_points = []
                # 等間隔で色をサンプリングする
                for i in range(num_points):
                    # 元のリストでのインデックスを計算
                    raw_idx = i * (num_colors - 1) / (num_points - 1)
                    index = int(round(raw_idx))
                    # インデックスがリストの範囲を超えないようにする
                    index = min(index, num_colors - 1)

                    # 直前のポイントと同じインデックスならスキップ (色数が少ない場合に発生)
                    if i > 0 and index == gradient_points[-1]['_index']:
                        continue

                    pos = index / (num_colors - 1)
                    point = {"pos": round(pos, 5), "color": valid_rgb_colors[index], "_index": index}
                    gradient_points.append(point)

                # 後処理でヘルパーキーを削除
                for p in gradient_points:
                    del p['_index']

                new_map = {
                    "map_name": map_name,
                    "type": "gradient",
                    "gradient_points": gradient_points,
                    "num_colors": num_colors
                }
            else: # グラデーション化しない場合 (従来通り)
                if use_gradient:
                    print(f"    -> 色数が少ないため、通常形式で出力します。")
                new_map = {"map_name": map_name, "colors": valid_rgb_colors}

            output_data["maps"].append(new_map)

        except Exception as e:
            print(f"    エラー: '{file_path.name}' の処理中に予期せぬエラーが発生しました: {e}")

    if not output_data["maps"]:
        print("\n有効なカラーマップが一つも作成されませんでした。出力ファイルは生成されません。")
        return

    # ファイル書き出し処理
    try:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('{\n')
            f.write(f'    "pack_name": {json.dumps(output_data["pack_name"], ensure_ascii=False)},\n')
            f.write('    "maps": [\n')

            num_maps = len(output_data["maps"])
            for map_index, map_data in enumerate(output_data["maps"]):
                f.write('        {\n')
                keys = list(map_data.keys())
                for i, key in enumerate(keys):
                    f.write(f'            "{key}": ')
                    if key == "colors":
                        f.write('[\n')
                        colors = map_data[key]
                        num_colors = len(colors)
                        indent_str = ' ' * 16
                        for j, color in enumerate(colors):
                            if j % 5 == 0: f.write(indent_str)
                            f.write(f'[{color[0]},{color[1]},{color[2]}]')
                            if j < num_colors - 1: f.write(',')
                            if (j + 1) % 5 == 0 and j < num_colors - 1: f.write('\n')
                        f.write('\n' + ' ' * 12 + ']')
                    elif key == "gradient_points":
                        f.write('[\n')
                        points = map_data[key]
                        num_points = len(points)
                        for j, point in enumerate(points):
                            f.write(' ' * 16 + json.dumps(point))
                            if j < num_points - 1: f.write(',')
                            f.write('\n')
                        f.write(' ' * 12 + ']')
                    else:
                        f.write(json.dumps(map_data[key], ensure_ascii=False))

                    if i < len(keys) - 1: f.write(',')
                    f.write('\n')

                f.write('        }')
                if map_index < num_maps - 1: f.write(',\n')
                else: f.write('\n')
            f.write('    ]\n')
            f.write('}\n')
        print(f"\n✅ 成功: カラーパック '{pack_name}' を '{output_path}' に保存しました。")
    except Exception as e:
        print(f"\n❌ エラー: 出力ファイル '{output_file}' の書き込みに失敗しました: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="複数のカラー定義JSONファイルを一つのカラーパックJSONファイルに変換します。",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("input_patterns", metavar="INPUT_PATTERN", nargs='+', help="変換元のJSONファイルのパスまたはglobパターン。")
    parser.add_argument("-o", "--output", required=True, help="出力するカラーパックJSONファイルのパス。")
    parser.add_argument("-n", "--name", required=True, help="生成するカラーパックの名前 (pack_name)。")
    # <<< 修正箇所 >>>
    parser.add_argument("-g", "--gradient", action="store_true", help="色数が多いマップをグラデーション形式に変換してデータ量を削減します。")
    parser.add_argument("--points", type=int, default=8, help="グラデーション変換時に抽出する中間色の数 (デフォルト: 8)")

    args = parser.parse_args()
    if args.points < 2:
        print("エラー: --pointsには2以上の値を指定してください。")
        sys.exit(1)

    convert_files_to_pack(args.input_patterns, args.output, args.name, args.gradient, args.points)

if __name__ == "__main__":
    main()
