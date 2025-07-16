import json
from pathlib import Path

# パスの定義
project_root = Path(__file__).resolve().parent.parent.parent
preset_path = project_root / 'resources/preset/preset_record.json'
settings_path = project_root / 'settings.jsonc'

# プリセットの読み込み
with open(preset_path, 'r', encoding='utf-8') as f:
    presets = json.load(f)

# settings.jsonc の読み込み
if settings_path.exists():
    with open(settings_path, 'r', encoding='utf-8') as f:
        import re
        content = f.read()
        # コメント除去（// ...）
        content = re.sub(r"//.*", "", content)
        settings = json.loads(content)
else:
    settings = {}

# presets サブキーに反映
settings['presets'] = presets

# 保存
with open(settings_path, 'w', encoding='utf-8') as f:
    json.dump(settings, f, indent=4, ensure_ascii=False)

print(f"プリセットを settings.jsonc に適用しました（{len(presets)} 件）。")
