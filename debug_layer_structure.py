# debug_layer_structure.py
import os
import json

def debug_layer_structure(layer_dir="zundamon"):
    """レイヤー構造をデバッグ"""
    
    # 1. position_map.json の内容確認
    map_file = os.path.join(layer_dir, "position_map.json")
    if os.path.exists(map_file):
        with open(map_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print("=== position_map.json のレイヤー一覧 ===")
        for layer_path in list(data.get('layers', {}).keys())[:10]:  # 最初の10個
            print(f"  {layer_path}")
        print(f"  ... 他{len(data.get('layers', {}))-10}個")
    
    # 2. 実際のファイル構造確認
    print("\n=== 実際のファイル構造 ===")
    for root, dirs, files in os.walk(layer_dir):
        level = root.replace(layer_dir, '').count(os.sep)
        indent = ' ' * 2 * level
        relative_path = os.path.relpath(root, layer_dir)
        print(f"{indent}{os.path.basename(root)}/")
        
        # PNGファイルのみ表示
        png_files = [f for f in files if f.endswith('.png')]
        sub_indent = ' ' * 2 * (level + 1)
        for png_file in png_files[:3]:  # 最初の3個のみ
            print(f"{sub_indent}{png_file}")
        if len(png_files) > 3:
            print(f"{sub_indent}... 他{len(png_files)-3}個")
    
    # 3. 特定レイヤーの検索テスト
    print("\n=== 検索テスト ===")
    test_paths = [
        "枝豆/枝豆通常",
        "服装1/いつもの服", 
        "口/むふ",
        "目/目セット/黒目/普通目"
    ]
    
    for test_path in test_paths:
        print(f"検索: {test_path}")
        found_file = find_layer_file_debug(layer_dir, test_path)
        if found_file:
            print(f"  → 発見: {found_file}")
        else:
            print(f"  → 見つからず")

def find_layer_file_debug(layer_dir, layer_path):
    """デバッグ用ファイル検索"""
    path_parts = layer_path.split('/')
    
    current_path = layer_dir
    for part in path_parts[:-1]:
        current_path = os.path.join(current_path, part)
        print(f"    パス確認: {current_path} → {'存在' if os.path.exists(current_path) else '存在しない'}")
    
    if not os.path.exists(current_path):
        return None
    
    layer_name = path_parts[-1]
    print(f"    ファイル検索: {layer_name}で始まるPNG")
    
    try:
        for filename in os.listdir(current_path):
            print(f"      チェック: {filename}")
            if filename.startswith(layer_name) and filename.endswith('.png'):
                return os.path.join(current_path, filename)
    except Exception as e:
        print(f"    エラー: {e}")
    
    return None

if __name__ == "__main__":
    debug_layer_structure()