#!/usr/bin/env python3
"""
カラーマップデータ変換スクリプト

機能:
1. Perceptually_Uniform_Sequential形式 -> default形式への変換
2. Qualitative形式の整形（colorsを5個ずつ改行、typeを前に移動）
"""

import json
import sys
from pathlib import Path


def convert_sequential_to_default(input_file, output_file):
    """
    Perceptually_Uniform_Sequential形式をdefault形式に変換

    Args:
        input_file (str): 入力ファイルパス
        output_file (str): 出力ファイルパス
    """
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 変換済みデータの構造を準備
        converted_data = {
            "pack_name": data["pack_name"],
            "maps": []
        }

        # 各マップを変換
        for map_data in data["maps"]:
            converted_map = {
                "map_name": map_data["map_name"],
                "type": map_data["type"],
                "gradient_points": map_data["gradient_points"],
                "num_colors": map_data["num_colors"]
            }
            converted_data["maps"].append(converted_map)

        # 出力ファイルに書き込み
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(converted_data, f, ensure_ascii=False, indent=4)

        print(f"✓ Sequential -> Default変換完了: {input_file} -> {output_file}")

    except FileNotFoundError:
        print(f"エラー: ファイル '{input_file}' が見つかりません")
    except json.JSONDecodeError:
        print(f"エラー: '{input_file}' のJSONが無効です")
    except Exception as e:
        print(f"エラー: {e}")


def format_qualitative_data(input_file, output_file):
    """
    Qualitative形式のデータを整形
    - colorsを5個ずつ改行
    - typeをcolorsの前に移動

    Args:
        input_file (str): 入力ファイルパス
        output_file (str): 出力ファイルパス
    """
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 各マップを整形
        for map_data in data["maps"]:
            if "colors" in map_data and "type" in map_data:
                # typeをcolorsの前に移動（辞書の順序を制御）
                colors = map_data.pop("colors")
                map_type = map_data.pop("type")

                # 新しい順序で再構築
                new_map_data = {"map_name": map_data["map_name"]}
                new_map_data["type"] = map_type
                new_map_data["colors"] = colors

                # 元のmap_dataを更新
                map_data.clear()
                map_data.update(new_map_data)

        # カスタムJSONエンコーダーを使用してcolorsを5個ずつ改行
        formatted_json = format_json_with_color_breaks(data)

        # 出力ファイルに書き込み
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(formatted_json)

        print(f"✓ Qualitative形式整形完了: {input_file} -> {output_file}")

    except FileNotFoundError:
        print(f"エラー: ファイル '{input_file}' が見つかりません")
    except json.JSONDecodeError:
        print(f"エラー: '{input_file}' のJSONが無効です")
    except Exception as e:
        print(f"エラー: {e}")


def format_json_with_color_breaks(data):
    """
    JSONのcolors配列を5個ずつ改行してフォーマット

    Args:
        data (dict): JSONデータ

    Returns:
        str: フォーマット済みJSON文字列
    """
    # まず通常のJSONとして出力
    json_str = json.dumps(data, ensure_ascii=False, indent=4)

    # colors配列の部分を5個ずつ改行に変換
    lines = json_str.split('\n')
    formatted_lines = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # colors配列の開始を検出
        if '"colors": [' in line:
            formatted_lines.append(line)
            i += 1

            # 配列の要素を収集
            colors = []
            indent_level = len(line) - len(line.lstrip())

            while i < len(lines) and not lines[i].strip().startswith(']'):
                color_line = lines[i].strip()
                if color_line and not color_line.startswith(']'):
                    # カンマを削除してカラー値を取得
                    color_value = color_line.rstrip(',')
                    colors.append(color_value)
                i += 1

            # 5個ずつ改行してフォーマット
            for j in range(0, len(colors), 5):
                chunk = colors[j:j+5]
                if j + 5 < len(colors):
                    # 最後のチャンク以外はカンマを付ける
                    formatted_line = ' ' * (indent_level + 4) + ', '.join(chunk) + ','
                else:
                    # 最後のチャンクはカンマなし
                    formatted_line = ' ' * (indent_level + 4) + ', '.join(chunk)
                formatted_lines.append(formatted_line)

            # 配列の閉じ括弧を追加
            if i < len(lines):
                formatted_lines.append(lines[i])
        else:
            formatted_lines.append(line)

        i += 1

    return '\n'.join(formatted_lines)


def main():
    """メイン関数"""
    if len(sys.argv) < 3:
        print("使用方法:")
        print("  python colormap_converter.py sequential <input_file> <output_file>")
        print("  python colormap_converter.py qualitative <input_file> <output_file>")
        print()
        print("例:")
        print("  python colormap_converter.py sequential Perceptually_Uniform_Sequential.json converted_default.json")
        print("  python colormap_converter.py qualitative Qualitative.json formatted_qualitative.json")
        return

    mode = sys.argv[1].lower()

    if mode == "sequential":
        if len(sys.argv) != 4:
            print("エラー: sequential モードには入力ファイルと出力ファイルが必要です")
            return
        input_file = sys.argv[2]
        output_file = sys.argv[3]
        convert_sequential_to_default(input_file, output_file)

    elif mode == "qualitative":
        if len(sys.argv) != 4:
            print("エラー: qualitative モードには入力ファイルと出力ファイルが必要です")
            return
        input_file = sys.argv[2]
        output_file = sys.argv[3]
        format_qualitative_data(input_file, output_file)

    else:
        print("エラー: 無効なモードです。'sequential' または 'qualitative' を指定してください")


if __name__ == "__main__":
    main()
