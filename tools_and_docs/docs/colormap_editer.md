# カラーマップエディタの概要

## 1. 目的
ユーザーが直感的な操作でオリジナルのカラーマップやカラーパックを作成・編集できるようにする。これにより、フラクタル画像の色彩表現の自由度を向上させる。

## 2. UI構成案
- **メインウィンドウ**:
  - **メニューバー**:
    - `ファイル`: `開く`, `上書き保存`, `名前を付けて保存`, `終了`
    - `編集`: `元に戻す`, `やり直し`
  - **左パネル (カラーパック管理)**:
    - 現在読み込んでいるカラーパック名を表示。
    - カラーパック内のカラーマップリストを一覧表示 (リスト形式)。
    - `追加`, `削除`, `名前変更` ボタンを配置。
  - **中央パネル (カラーマップ編集)**:
    - **グラデーションプレビュー**: 選択中のカラーマップのグラデーションを大きく表示。
    - **ノードエディタ**: グラデーションの下にノードを配置したUI。
      - 各ノードは色と位置を持つ。
      - 背景にはスケール (0.0 ~ 1.0) を表示。
  - **右パネル (ツール & 設定)**:
    - **ノード情報**: 選択中ノードの色 (RGB/HSV値) と位置 (0.0-1.0) を表示・編集。
    - **カラーピッカー**: ノードの色を視覚的に選択。
    - **ユーティリティ**:
      - `ランダム生成`: ノード数を指定してカラーマップを自動生成。
      - `画像から抽出`: 画像ファイルを読み込み、カラーマップを自動生成。

## 3. 機能詳細
### カラーパックの管理
- **読み込み**: JSON形式のカラーパックファイル (`.json`) を読み込む。
- **保存**: 編集したカラーパックをJSON形式で保存する。
- **新規作成**: 空のカラーパックを作成する。

### カラーマップの編集
- **リスト操作**: 左パネルでカラーマップを選択、追加、削除、名前変更を行う。
- **プレビュー**: 中央パネルで選択中のカラーマップのプレビューをリアルタイムに確認できる。

### ノード編集
- **ノードの追加**: ノードエディタの何もない領域をダブルクリック。
- **ノードの削除**: ノードを右クリックし、コンテキストメニューから `削除` を選択。
- **ノードの移動**: ノードを左右にドラッグアンドドロップ。ノードの位置 (0.0-1.0) が変更される。
- **ノードの色の変更**: ノードを左クリックで選択する。選択されたノードの色が右パネルのカラーピッカーに表示され、そこで直接色の編集を行う。

### 高度な機能
- **ランダム生成**:
  - 一度に生成するカラーマップの数を指定 (最小1, 最大50, デフォルト10)。
  - 各カラーマップのノード数 (2〜256) を指定。
  - ランダムな色と位置でノードを配置し、指定した数の新しいカラーマップを作成する。
- **画像から抽出**:
  - ユーザーが画像ファイルを選択。
  - 画像内で使用されている色を分析 (k-meansクラスタリング等) し、主要な色を抽出。
  - 抽出した色でノードを構成し、新しいカラーマップを作成する。色数 (2〜256) は指定可能。

## 4. データ構造 (JSON)
既存のカラーパックの形式に準拠する。カラーマップにはグラデーションを定義するタイプと、色のリストを直接定義するタイプの2種類が存在する。

```json
{
  "pack_name": "パック名",
  "maps": [
    // グラデーションタイプ
    {
      "map_name": "グラデーションマップ名",
      "type": "gradient",
      "gradient_points": [
        {"pos": 0.0, "color": [255, 0, 0, 255]},
        {"pos": 0.5, "color": [0, 255, 0, 255]},
        {"pos": 1.0, "color": [0, 0, 255, 255]}
      ],
      "num_colors": 256
    },
    // ディスクリート (個別色) タイプ
    {
      "map_name": "ディスクリートマップ名",
      "colors": [
        [255, 0, 0, 255],
        [0, 255, 0, 255],
        [0, 0, 255, 255]
      ]
    }
  ]
}
```

- **pack_name**: カラーパック全体の名前。
- **maps**: カラーマップのリスト。
- **map_name**: 各カラーマップの名前。
- **type**: (グラデーションの場合) `gradient` を指定。
- **gradient_points**: (グラデーションの場合) ノードのリスト。各ノードは位置 (`pos`) と色 (`color`) を持つ。
  - **pos**: 0.0 から 1.0 の範囲。
  - **color**: RGBA値の配列。
- **num_colors**: (グラデーションの場合) グラデーションから生成する色の総数。
- **colors**: (ディスクリートの場合) RGBA値の配列のリスト。

## 5. 課題と対策
- **課題**: グラデーションを定義するノード数が多くなりすぎると、手作業での編集が非現実的になる。
- **対策**: 編集モードを動的に切り替えることで対応する。

  1. **ノード編集モード (上限30個)**
     - **対象**: 新規作成、または既存マップのノード数が30個以下の場合。
     - **UI**: グラデーションプレビューの下にノードエディタを表示する。
     - **操作**: ユーザーはキーとなるノード（最大30個）を直接操作して、全体のグラデーションを設計する。

  2. **ダイレクト編集モード (30個超の場合)**
     - **対象**: 読み込んだマップのノード数が30個を超える高密度データの場合。
     - **UI**: 複雑化を避けるため、ノードエディタは非表示にする。
     - **操作**: ユーザーはグラデーションプレビュー上を直接クリックする。クリックした点の色がカラーピッカーに表示され、その一点の色を直接編集・微調整できる。
