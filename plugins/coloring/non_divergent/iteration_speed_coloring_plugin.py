import numpy as np
from plugins.base_coloring_plugin import ColoringAlgorithmPlugin
# 異なる実行コンテキストでの堅牢性のために、CustomLoggerのインポートにtry-exceptブロックを使用
try:
    from logger.custom_logger import CustomLogger
except ImportError:
    # CustomLoggerが見つからない場合の最小限のフォールバックロガー（例：分離テスト中）
    import logging
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
    CustomLogger = type("CustomLogger", (), {"log": lambda self, msg, level="INFO": logging.info(msg) if level == "INFO" else logging.warning(msg) if level == "WARNING" else logging.error(msg)})()

from numba import jit

logger = CustomLogger()

# @jit(nopython=True, cache=True)
def _apply_iteration_speed_coloring_jit(
    iterations: np.ndarray,
    max_iterations: int,
    img_array_rgb: np.ndarray, # RGB部分（高さx幅x3）のみを渡す
    color_map_array: np.ndarray | None, # カラーマップ用のNumPy配列、またはNone
    use_color_map: bool
) -> None:
    height, width = iterations.shape

    for r_idx in range(height):
        for c_idx in range(width):
            iters_val = iterations[r_idx, c_idx]

            diff: int
            if iters_val < 0:
                diff = 0
            else:
                # diff は max_iterations と iters_val の差。
                # iters_val が小さい (max_iterations よりずっと小さい) ほど diff は大きくなる。
                # iters_val が max_iterations に等しい場合、diff は 0 になる。
                diff = max_iterations - iters_val
                diff = max(0, min(diff, max_iterations))

            if not use_color_map: # グレースケール
                # ゼロ除算を防ぐためにmax_iterationsがゼロでないことを保証する
                # これは呼び出し元がmax_iterations >= 1と設定することで保証されるべき
                gray_val = int(255 * (diff / max_iterations))
                # diff が 0 (iters_val == max_iterations) の場合、gray_val は 0 (黒)。
                # diff が max_iterations (iters_val == 0) の場合、gray_val は 255 (白)。
                # Numbaは配列代入にリスト内包表記を直接使用するのが難しい
                img_array_rgb[r_idx, c_idx, 0] = gray_val
                img_array_rgb[r_idx, c_idx, 1] = gray_val
                img_array_rgb[r_idx, c_idx, 2] = gray_val
            else: # カラーマップを使用
                if color_map_array is not None: # use_color_mapがtrueの場合、常にtrueであるべき
                    num_colors = color_map_array.shape[0]
                    if num_colors == 0: # color_map_arrayが適切に渡されていれば発生しないはず
                        img_array_rgb[r_idx, c_idx, 0] = 0
                        img_array_rgb[r_idx, c_idx, 1] = 0
                        img_array_rgb[r_idx, c_idx, 2] = 0
                        continue

                    # Ensure max_iterations is not zero
                    color_idx = int((diff / max_iterations) * (num_colors - 1))
                    # diff が 0 (iters_val == max_iterations) の場合、color_idx は 0 (カラーマップの最初の色)。
                    # diff が max_iterations (iters_val == 0) の場合、color_idx は num_colors - 1 (カラーマップの最後の色)。
                    color_idx = max(0, min(color_idx, num_colors - 1))

                    img_array_rgb[r_idx, c_idx, 0] = color_map_array[color_idx, 0]
                    img_array_rgb[r_idx, c_idx, 1] = color_map_array[color_idx, 1]
                    img_array_rgb[r_idx, c_idx, 2] = color_map_array[color_idx, 2]
                # elseの場合: use_color_mapはtrueだがcolor_map_arrayがNone (設計上発生しないはず)


class IterationSpeedColoringPlugin(ColoringAlgorithmPlugin):
    """
    非発散領域（内部）の点の 'iterations' 値に基づいて色を付けるプラグイン。

    動作原理:
    1. 各点 (ピクセル) の反復計算回数 `iters_val` を取得します。
    2. `max_iterations` (最大反復回数) と `iters_val` との差 `diff = max_iterations - iters_val` を計算します。
       - `iters_val` が小さいほど (つまり、`max_iterations` に達するずっと前に計算が完了したと仮定できる場合)、
         `diff` は大きくなります。
       - `iters_val` が `max_iterations` に等しい場合 (多くのフラクタル計算で非発散領域の点がこの値を持ちます)、
         `diff` は 0 になります。
    3. `diff` の値を正規化 (`diff / max_iterations`) し、それに基づいて色を決定します。
       - グレースケールの場合: `gray = 255 * (diff / max_iterations)`。`diff` が 0 なら黒、`max_iterations` なら白。
       - カラーマップ使用の場合: `color_index = (diff / max_iterations) * (num_colors - 1)`。
         `diff` が 0 ならカラーマップの最初の色、`max_iterations` なら最後の色。

    注意点:
    標準的なマンデルブロ集合やジュリア集合の計算では、非発散領域と判定された全ての点の `iters_val` は
    `max_iterations` となることが一般的です。その結果、これらの点では `diff` が 0 となり、
    このプラグインを使用すると非発散領域全体が単色（グレースケールでは黒、カラーマップ使用時は
    カラーマップの最初の色）で塗りつぶされることになります。
    非発散部で色のグラデーションを得るためには、`iters_val` が `max_iterations` 未満の値を持ちうるような
    特殊なフラクタル計算アルゴリズムや、あるいは `iterations` 配列にそのような情報が格納されている場合に限られます。
    一般的なケースで非発散部に豊かな色彩表現を求める場合は、`ComplexPotentialColoringPlugin` のような
    他のアルゴリズムの利用を検討してください。
    """

    @property
    def name(self) -> str:
        return "反復収束速度"

    @property
    def target_type(self) -> str:
        return "non_divergent"

    def get_parameters_definition(self) -> list:
        """現時点ではパラメータなし。"""
        return []

    def apply_coloring(
        self,
        fractal_data: dict,
        common_fractal_params: dict,
        algorithm_params: dict, # 現時点では未使用
        color_map_data: list[tuple[int, int, int]] | None
    ) -> np.ndarray:
        """
        収束速度に基づいてカラーリングを適用します。
        'iterations' 配列内の値を評価し、max_iterations との差 (diff) を計算します。
        diff が小さい (つまり iterations が max_iterations に近い) ほど、
        カラーマップの初期の色を使用します。
        """
        iterations = fractal_data.get('iterations')

        height_param = common_fractal_params.get('height')
        width_param = common_fractal_params.get('width')

        if iterations is None:
            logger.log("fractal_data に 'iterations' データが見つかりません。", level="ERROR")
            h = height_param if height_param is not None else 100 # デフォルトの高さ
            w = width_param if width_param is not None else 100   # デフォルトの幅
            return np.zeros((h, w, 4), dtype=np.uint8)

        # パラメータが見つからないか矛盾している場合、iterations配列から形状を決定する
        height, width = iterations.shape
        if height_param is not None and width_param is not None:
            if (height_param, width_param) != (height, width):
                logger.log(
                    f"形状が一致しません。common_fractal_params のピクセルサイズ: ({height_param}, {width_param}), "
                    f"iterations 配列の形状: ({height}, {width})。反復配列からの形状を使用します。",
                    level="WARNING"
                )
        # それ以外の場合、パラメータがNoneであれば、iterationsからの形状が既に設定されている。

        max_iterations = common_fractal_params.get('max_iterations', 100)
        if max_iterations <= 0: # ゼロ除算や無意味な動作を避ける
            max_iterations = 1 # 最小の正の値に設定する

        img_array = np.zeros((height, width, 4), dtype=np.uint8)
        img_array[:, :, 3] = 255  # アルファチャンネルを不透明に
        img_array_rgb = img_array[:, :, :3] # RGBチャンネルのビューをJIT関数に渡す

        use_color_map_flag = True
        color_map_np_array = None

        if not color_map_data or len(color_map_data) == 0:
            logger.log("apply_coloring: カラーマップが提供されていないか空です。グレースケールを使用します。", level="WARNING")
            use_color_map_flag = False
        else:
            try:
                # NumbaのためにタプルのリストをNumPy配列に変換する
                # 色が0-255の範囲であることを保証するためにdtypeをuint8にする
                color_map_np_array = np.array(color_map_data, dtype=np.uint8)
                if color_map_np_array.ndim != 2 or color_map_np_array.shape[1] != 3:
                    logger.log(f"apply_coloring: 無効なcolor_map_data構造です。Nx3を期待しましたが、形状 {color_map_np_array.shape} を受け取りました。グレースケールを使用します。", level="ERROR")
                    use_color_map_flag = False
                    color_map_np_array = None # 無効な場合はNoneであることを保証する
            except Exception as e:
                logger.log(f"apply_coloring: color_map_dataのNumPy配列への変換エラー: {e}。グレースケールを使用します。", level="ERROR")
                use_color_map_flag = False
                color_map_np_array = None

        _apply_iteration_speed_coloring_jit(
            iterations,
            max_iterations, # 既に1以上であることが保証されている
            img_array_rgb,
            color_map_np_array, # NumPy配列またはNoneを渡す
            use_color_map_flag
        )
        return img_array


if __name__ == '__main__':
    import sys
    from pathlib import Path
    # plugins.base_coloring_pluginのようなインポートのためにプロジェクトルートがsys.pathに含まれていることを確認する
    # このスクリプトがplugins/coloring/non_divergent/にあることを前提としています
    project_root_candidate = Path(__file__).resolve().parents[3]
    # 構造が変更された場合、プロジェクトルートを見つけるためのより堅牢な方法が必要になるかもしれません
    # 現時点では、これは一般的な構造です: project_root/src/app/plugins/.... または project_root/plugins/...
    # 構造がproject_root/pluginsの場合、parents[2]
    # 構造がproject_root/src/pluginsの場合、parents[3]（ここでは'src'が'app'のようなものと仮定）
    # このテストコンテキストでは、pluginsディレクトリがproject_rootの直下にあると仮定しましょう
    project_root = project_root_candidate
    # 現在のproject_rootのサブディレクトリに'plugins'があるかどうかを確認し、なければ調整する。
    # このロジックは、このテストがどこから実行されるかによって、より洗練される必要があるかもしれません。
    # 現時点では、このパスが開発環境にとって正しいと仮定します。
    if (project_root / "plugins").is_dir() and (project_root / "logger").is_dir():
         if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
    else: # 上記の構造が見つからない場合のフォールバック（例：異なる深さから実行する場合）
        # 'plugins'と'logger'の両方を含むディレクトリを探す試み
        current_path = Path(__file__).resolve()
        for i in range(5): # 最大5レベル上までチェック
            p_root = current_path.parents[i]
            if (p_root / "plugins").is_dir() and (p_root / "logger").is_dir():
                if str(p_root) not in sys.path:
                    sys.path.insert(0, str(p_root))
                project_root = p_root
                break
        else:
            print("警告: sys.path変更のためのプロジェクトルートを確実には特定できませんでした。", file=sys.stderr)


    try:
        from plugins.base_coloring_plugin import ColoringAlgorithmPlugin
        # CustomLoggerが先頭でインポートされなかった場合、これはそのインポートまたはフォールバックを再トリガーします
        if 'CustomLogger' not in globals() or globals()['CustomLogger'] is None:
            from logger.custom_logger import CustomLogger as GlobalCustomLogger
            logger = GlobalCustomLogger()

    except ImportError as e:
        print(f"エラー: スタンドアロンテストのための依存関係をインポートできませんでした: {e}", file=sys.stderr)
        # インポートが失敗した場合の最小限のモックを定義する
        class ColoringAlgorithmPlugin: pass
        if 'logger' not in globals() or logger is None: # loggerがフォールバックでさえなかった場合
            import logging
            logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
            logger = type("CustomLogger", (), {"log": lambda self, msg, level="INFO": logging.info(msg)})()
        logger.log(f"テストセットアップ中のImportError: {e}", level="ERROR")


    logger.log("IterationSpeedColoringPlugin スタンドアロンテスト", level="INFO")

    plugin = IterationSpeedColoringPlugin()
    logger.log(f"プラグイン名: {plugin.name}")
    logger.log(f"ターゲットタイプ: {plugin.target_type}")
    assert plugin.target_type == "non_divergent", "ターゲットタイプのチェックに失敗しました"
    logger.log(f"パラメータ定義: {plugin.get_parameters_definition()}")

    # --- テストケース1: 基本的なグレースケールとカラーマップのテスト（以前と同様） ---
    logger.log("\n--- テストケース1: 基本機能 ---", level="INFO")
    height1, width1 = 4, 5
    test_iters1 = np.array([
        [0, 10, 20, 30, 50],    # 差分 (max_iters=50): 50, 40, 30, 20, 0
        [50, 40, 30, 20, 0],    # 差分: 0, 10, 20, 30, 50
        [25, 25, 25, 25, 25],   # 差分: 25, 25, 25, 25, 25
        [-1, 30, 50, 10, -1]    # 差分: 0, 20, 0, 40, 0
    ], dtype=np.int32)
    max_iters_test1 = 50
    test_fractal_data1 = {'iterations': test_iters1, 'last_zn_values': np.zeros_like(test_iters1, dtype=np.complex128)} # ダミーのlast_zn_valuesを追加
    test_common_params1 = {'max_iterations': max_iters_test1, 'height': height1, 'width': width1}
    test_algo_params1 = {}

    logger.log("Test 1.1: カラーマップなし (グレースケール)", level="INFO")
    img_no_map1 = plugin.apply_coloring(test_fractal_data1, test_common_params1, test_algo_params1, None)
    assert img_no_map1.shape == (height1, width1, 4), f"形状不一致: 期待値 ({height1},{width1},4), 実際 {img_no_map1.shape}"
    assert img_no_map1.dtype == np.uint8, "dtype不一致"
    # 期待されるグレー値 (diff = max_iters - iters, gray = 255 * diff / max_iters)
    expected_grays1 = np.array([[255,204,153,102,0], [0,51,102,153,255], [127,127,127,127,127], [0,102,0,204,0]], dtype=np.uint8)
    for r in range(height1):
        for c in range(width1):
            assert np.array_equal(img_no_map1[r,c,:3], [expected_grays1[r,c]]*3), f"P({r},{c}) グレー値 実際 {img_no_map1[r,c,:3]}, 期待値 {[expected_grays1[r,c]]*3}"
    logger.log("Test 1.1: グレースケールテスト合格", level="INFO")

    logger.log("Test 1.2: カラーマップあり", level="INFO")
    test_color_map1 = [(255,0,0), (0,255,0), (0,0,255), (255,255,0), (255,0,255)] # 赤,緑,青,黄,マゼンタ
    img_with_map1 = plugin.apply_coloring(test_fractal_data1, test_common_params1, test_algo_params1, test_color_map1)
    assert img_with_map1.shape == (height1, width1, 4)
    # 期待されるインデックス (idx = int((diff/max_iters)*(num_colors-1)))
    expected_indices_map1 = [[4,3,2,1,0], [0,0,1,2,4], [2,2,2,2,2], [0,1,0,3,0]]
    for r in range(height1):
        for c in range(width1):
            assert np.array_equal(img_with_map1[r,c,:3], test_color_map1[expected_indices_map1[r][c]]), f"P({r},{c}) 色 実際 {img_with_map1[r,c,:3]}, 期待値 {test_color_map1[expected_indices_map1[r][c]]}"
    logger.log("Test 1.2: カラーマップテスト合格", level="INFO")

    # --- テストケース2: max_iterationsのエッジケース ---
    logger.log("\n--- テストケース2: max_iterations エッジケース ---", level="INFO")
    height2, width2 = 1, 3
    max_iters_test2 = 1
    test_iters2 = np.array([[0, 1, -1]], dtype=np.int32) # 差分 (max_iters=1): 1, 0, 0
    test_fractal_data2 = {'iterations': test_iters2}
    test_common_params2 = {'max_iterations': max_iters_test2, 'height': height2, 'width': width2}

    logger.log("Test 2.1: max_iterations = 1 (グレースケール)", level="INFO")
    img_max_iter_1_gray = plugin.apply_coloring(test_fractal_data2, test_common_params2, test_algo_params1, None)
    assert img_max_iter_1_gray.shape == (height2,width2,4)
    # P(0,0): iters=0, diff=1. グレー値 = 255 * 1/1 = 255
    assert np.array_equal(img_max_iter_1_gray[0,0,:3], [255,255,255]), f"max_iter=1, P(0,0) グレー値 実際 {img_max_iter_1_gray[0,0,:3]}"
    # P(0,1): iters=1, diff=0. グレー値 = 255 * 0/1 = 0
    assert np.array_equal(img_max_iter_1_gray[0,1,:3], [0,0,0]), f"max_iter=1, P(0,1) グレー値 実際 {img_max_iter_1_gray[0,1,:3]}"
    # P(0,2): iters=-1, diff=0. グレー値 = 0
    assert np.array_equal(img_max_iter_1_gray[0,2,:3], [0,0,0]), f"max_iter=1, P(0,2) グレー値 実際 {img_max_iter_1_gray[0,2,:3]}"
    logger.log("Test 2.1: max_iterations=1 グレースケールテスト合格", level="INFO")

    logger.log("Test 2.2: max_iterations = 1 (カラーマップあり - 3色 赤,緑,青)", level="INFO")
    test_color_map2 = [(255,0,0), (0,255,0), (0,0,255)] # 赤,緑,青
    img_max_iter_1_map = plugin.apply_coloring(test_fractal_data2, test_common_params2, test_algo_params1, test_color_map2)
    # P(0,0): iters=0, diff=1. idx = int((1/1)*(2)) = 2 (青)
    assert np.array_equal(img_max_iter_1_map[0,0,:3], test_color_map2[2]), f"max_iter=1, P(0,0) 色 実際 {img_max_iter_1_map[0,0,:3]}"
    # P(0,1): iters=1, diff=0. idx = int((0/1)*(2)) = 0 (赤)
    assert np.array_equal(img_max_iter_1_map[0,1,:3], test_color_map2[0]), f"max_iter=1, P(0,1) 色 実際 {img_max_iter_1_map[0,1,:3]}"
    # P(0,2): iters=-1, diff=0. idx = 0 (赤)
    assert np.array_equal(img_max_iter_1_map[0,2,:3], test_color_map2[0]), f"max_iter=1, P(0,2) 色 実際 {img_max_iter_1_map[0,2,:3]}"
    logger.log("Test 2.2: max_iterations=1 カラーマップテスト合格", level="INFO")

    # --- テストケース3: iterations == max_iterations (この指標では非収束点) ---
    logger.log("\n--- テストケース3: iterations == max_iterations ---", level="INFO")
    height3, width3 = 1, 2
    max_iters_test3 = 30
    test_iters3 = np.array([[10, 30]], dtype=np.int32) # 差分 (max_iters=30): 20, 0
    test_fractal_data3 = {'iterations': test_iters3}
    test_common_params3 = {'max_iterations': max_iters_test3, 'height': height3, 'width': width3}

    logger.log("Test 3.1: iterations == max_iterations (グレースケール)", level="INFO")
    img_iter_eq_max_gray = plugin.apply_coloring(test_fractal_data3, test_common_params3, test_algo_params1, None)
    # P(0,0): iters=10, diff=20. グレー値 = 255 * 20/30 = 170
    assert np.array_equal(img_iter_eq_max_gray[0,0,:3], [170,170,170]), f"iter=max_iter, P(0,0) グレー値 実際 {img_iter_eq_max_gray[0,0,:3]}"
    # P(0,1): iters=30, diff=0. グレー値 = 0
    assert np.array_equal(img_iter_eq_max_gray[0,1,:3], [0,0,0]), f"iter=max_iter, P(0,1) グレー値 実際 {img_iter_eq_max_gray[0,1,:3]}"
    logger.log("Test 3.1: iterations == max_iterations グレースケールテスト合格", level="INFO")

    # --- テストケース4: 無効/欠損データ ---
    logger.log("\n--- テストケース4: 無効/欠損データ ---", level="INFO")
    logger.log("Test 4.1: 'iterations' データがない場合", level="INFO")
    img_no_iters = plugin.apply_coloring({}, test_common_params1, test_algo_params1, test_color_map1) # common_params1 は h/w を持つ
    assert img_no_iters.shape == (height1, width1, 4), f"iterationsなし 形状: 期待値 ({height1},{width1},4), 実際 {img_no_iters.shape}"
    assert np.all(img_no_iters == 0), "iterations が欠損している場合、画像はすべてゼロであるべき" # アルファも0
    logger.log("Test 4.1: Iterationsデータなしテスト合格", level="INFO")

    logger.log("Test 4.2: max_iterations = 0 (プラグインによって1に設定されます)", level="INFO")
    edge_common_params_zero = {'max_iterations': 0, 'height': 1, 'width': 1}
    edge_iters_zero = np.array([[0]], dtype=np.int32) # 差分は1になります (内部max_iters=1 - 0)
    img_edge_zero = plugin.apply_coloring({'iterations': edge_iters_zero}, edge_common_params_zero, test_algo_params1, test_color_map1)
    # max_iters=1, iters=0, diff=1. idx = int((1/1)*(4)) = 4 (test_color_map1のマゼンタ)
    assert np.array_equal(img_edge_zero[0,0,:3], test_color_map1[4]), "max_iterations=0 のテスト失敗"
    logger.log("Test 4.2: max_iterations=0 テスト合格", level="INFO")

    logger.log("\nIterationSpeedColoringPlugin スタンドアロンテスト完了", level="INFO")

    file_location_marker = Path(__file__).resolve().parent.name
    logger.log(f"このファイルは '{file_location_marker}' フォルダにあります。期待値: non_divergent", level="INFO")
    assert file_location_marker == "non_divergent", f"ファイル場所チェック: 期待値 'non_divergent', 実際 '{file_location_marker}'"
