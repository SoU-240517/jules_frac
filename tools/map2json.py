#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MAP形式のカラーマップファイルをJSON形式に変換するツール

使用方法:
1. このスクリプトを.mapファイル（または.map形式の.txtファイル）が含まれるフォルダにコピー
2. スクリプトを実行
3. 同じディレクトリに新しいフォルダ(フォルダ名_json)が作成され、変換されたJSONファイルが保存される
"""

import os
import json
import re
from pathlib import Path


def rgb_to_hex(r, g, b):
    """RGB値を16進数カラーコードに変換"""
    return f"#{r:02x}{g:02x}{b:02x}"


def parse_map_file(file_path):
    """MAPファイルを解析してカラーリストを作成"""
    colors = []

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
        for line in file:
            line = line.strip()
            if not line:
                continue

            # 行からRGB値を抽出
            values = re.split(r'\s+', line)
            if len(values) >= 3:
                try:
                    r = int(values[0])
                    g = int(values[1])
                    b = int(values[2])
                    hex_color = rgb_to_hex(r, g, b)
                    colors.append(hex_color)
                except ValueError:
                    # RGB値の解析に失敗した場合はスキップ
                    pass

    return colors


def map_to_json(map_file_path, output_dir):
    """MAPファイルをJSONに変換して保存"""
    try:
        # ファイル名とカテゴリ(親フォルダ名)を取得
        file_path = Path(map_file_path)
        file_name = file_path.stem
        category = file_path.parent.name

        # MAPファイルを解析
        colors = parse_map_file(map_file_path)

        if not colors:
            print(f"警告: {file_name} からカラーデータを抽出できませんでした")
            return False

        # JSON構造を作成
        json_data = {
            "name": file_name,
            "category": category,
            "colors": colors
        }

        # 出力ファイルパス
        output_file = output_dir / f"{file_name}.json"

        # JSONファイルを保存
        with open(output_file, 'w', encoding='utf-8') as json_file:
            json.dump(json_data, json_file, indent=2)

        print(f"変換成功: {file_name}.map -> {file_name}.json")
        return True

    except Exception as e:
        print(f"エラー: {map_file_path} の変換中に問題が発生しました: {e}")
        return False


def main():
    # 現在のディレクトリ
    current_dir = Path('.')
    folder_name = current_dir.absolute().name

    # 出力ディレクトリを作成
    output_dir_name = f"{folder_name}_json"
    output_dir = current_dir / output_dir_name

    if not output_dir.exists():
        output_dir.mkdir()
        print(f"フォルダを作成しました: {output_dir_name}")

    # すべての.mapファイルと特定の.txtファイル（実際は.mapファイル）を検索
    map_files = list(current_dir.glob('*.map'))
    txt_map_files = list(current_dir.glob('*.txt'))

    # 両方のリストを結合
    all_map_files = map_files + txt_map_files

    if not all_map_files:
        print("警告: 変換対象のファイルが見つかりませんでした")
        return

    # 変換処理
    converted_count = 0
    for map_file in all_map_files:
        if map_to_json(map_file, output_dir):
            converted_count += 1

    print(f"\n変換完了: {converted_count}/{len(all_map_files)} ファイルを変換しました")
    print(f"変換されたファイルは {output_dir_name} フォルダに保存されました")


if __name__ == "__main__":
    main()
