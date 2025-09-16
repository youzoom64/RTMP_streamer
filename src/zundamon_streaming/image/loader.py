"""PNG画像検索・インデックス"""
import os
import re
from typing import Dict, List, Optional
from ..utils.normalize import normalize_key

def build_png_index(root_dir: str) -> Dict[str, List[str]]:
    """root_dir 以下のPNGを正規化キー→相対パス(複数)の辞書に"""
    index = {}
    for r, _, files in os.walk(root_dir):
        for f in files:
            if not f.lower().endswith(".png"):
                continue
            full = os.path.join(r, f)
            rel = os.path.relpath(full, root_dir).replace("\\", "/")
            base = os.path.splitext(f)[0]

            def _clean(s):
                s = re.sub(r"_pos_\d+_\d+_\d+_\d+", "", s)
                s = "/".join(p.lstrip("_") for p in s.split("/"))
                return s

            rel_clean = _clean(rel)
            base_clean = _clean(base)
            parts = rel_clean.split("/")

            keys = set()
            keys.add(normalize_key(rel_clean))   
            keys.add(normalize_key(base_clean))  
            for k in range(1, 5):                
                tail = "/".join(parts[-k:])
                keys.add(normalize_key(tail))
            for p in parts:                      
                keys.add(normalize_key(p))

            for k in keys:
                index.setdefault(k, []).append(rel)
    return index

class PNGLoader:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.png_index = build_png_index(root_dir)
        self._warned_once = set()
    
    def find_layer_file(self, layer_path: str) -> Optional[str]:
        """ファイル検索"""
        # 直接パス検索
        direct_patterns = [
            layer_path,
            f"_{layer_path}",  # _服装1 対応
            layer_path.replace("服装1", "_服装1"),  # 服装1 -> _服装1
            layer_path.replace("左腕", "!左腕"),    # 左腕 -> !左腕
            layer_path.replace("右腕", "!右腕"),    # 右腕 -> !右腕
        ]
        
        for pattern in direct_patterns:
            # パターンに一致するファイルを直接検索
            result = self._find_files_matching_pattern(pattern)
            if result:
                return result
        
        # 通常の正規化検索
        keys_to_try = [
            layer_path,
            layer_path.replace("!", "").replace("*", ""),
            layer_path.split("/")[-1],
        ]
        
        for k in keys_to_try:
            nk = normalize_key(k)
            hits = self.png_index.get(nk)
            if hits:
                return os.path.join(self.root_dir, hits[0])
        
        self._warn_once(f"missing:{layer_path}", f"[WARN] ファイル未検出: {layer_path}")
        return None
    
    def _find_files_matching_pattern(self, pattern: str) -> Optional[str]:
        """パターンマッチングでファイル検索"""
        for rel_path, file_list in self.png_index.items():
            for file_path in file_list:
                if pattern in file_path:
                    return os.path.join(self.root_dir, file_path)
        return None
    
    def _warn_once(self, key: str, msg: str):
        if key in self._warned_once:
            return
        print(msg)
        self._warned_once.add(key)

    def find_by_keywords(self, *keywords):
        """AND検索：全キーワードを含むキーのうち最も具体的なもの"""
        wants = [normalize_key(w) for w in keywords if w]
        best = None
        for k, rels in self.png_index.items():
            if all(w in k for w in wants):
                score = len(k)
                cand = os.path.join(self.root_dir, rels[0])
                if (best is None) or (score > best[0]):
                    best = (score, cand)
        return best[1] if best else None