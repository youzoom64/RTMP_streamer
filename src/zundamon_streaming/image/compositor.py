"""画像合成エンジン"""
from PIL import Image
from typing import Dict
from .loader import PNGLoader
from .cache import ImageCache


import time
import threading

def trace_log(message, level="INFO"):
    timestamp = time.time()
    thread_id = threading.current_thread().ident
    print(f"[{timestamp:.3f}][{thread_id}][{level}] {message}")

class ImageCompositor:
    def __init__(self, layer_dir: str):
        self.layer_dir = layer_dir
        self.loader = PNGLoader(layer_dir)
        self.cache = ImageCache()
    
    def compose_expression(self, mouth: str, eyes: str) -> Image.Image:
        """表情に基づいて画像合成"""
        files = self._get_expression_files(mouth, eyes)
        
        
        # 実際のPNGサイズを使用
        base_size = (1082, 1650)  # position_map.jsonのcanvas_size
        
        canvas = Image.new("RGBA", base_size, (0, 0, 0, 0))
        
        # レイヤー重ね合わせ（辞書挿入順）
        for key in files:
            img = self.cache.get(files[key])
            canvas.alpha_composite(img, dest=(0, 0))
        
        return canvas
    
    def _get_expression_files(self, mouth: str, eyes: str) -> Dict[str, str]:
        """表情に対応するファイルパス群を取得"""
        files = {}
        
        # 1) 素体（最下層）
        body = (self.loader.find_layer_file("服装2/素体") or 
                self.loader.find_layer_file("素体"))
        if body:
            files["base_body"] = body
        
        # 2) 枝豆（任意）
        edamame = self.loader.find_layer_file("枝豆/枝豆通常")
        if edamame:
            files["base_edamame"] = edamame
        
        # 3) 服
        outfit = (self.loader.find_layer_file("服装1/いつもの服") or
                  self.loader.find_layer_file("服装1/制服"))
        if outfit:
            files["outfit"] = outfit
        
        # 4) 腕

        left_arm = (self.loader.find_layer_file("_服装1/!左腕/*基本*") or
                    self._find_by_keywords("左腕", "基本"))
                    
        right_arm = (self.loader.find_layer_file("_服装1/!右腕/*基本*") or
                    self._find_by_keywords("右腕", "基本"))
        if left_arm:
            files["arm_left"] = left_arm
        if right_arm:
            files["arm_right"] = right_arm
        
        # 5) 眉
        brow = (self.loader.find_layer_file("眉/普通眉") or
                self.loader.find_layer_file("眉/怒り眉"))
        if brow:
            files["brow"] = brow
        
        # 6) 目
        if eyes == "普通目":
            eye_white = self.loader.find_layer_file("目/目セット/普通白目")
            if eye_white:
                files["eye_white"] = eye_white
            eye_black = self.loader.find_layer_file("目/目セット/黒目/普通目")
            if eye_black:
                files["eye_black"] = eye_black
        else:
            eye_file = self.loader.find_layer_file(f"目/{eyes}")
            if eye_file:
                files["eyes"] = eye_file
        
        # 7) 口（実際のファイル構造に対応）
        mouth_file = None

        # 基本パターン
        mouth_patterns = [
            f"!口/_{mouth}_",
            f"!口/{mouth}",
        ]

        # 特別なマッピング（ファイル構造に基づく）
        mouth_mapping = {
            "むふ": ["!口/_むふ_"],
            "ほあー": ["!口/_ほあー_", "!口/_ほあ_", "!口/_ほー_"],
            "ほあ": ["!口/_ほあ_", "!口/_ほあー_"],
        }

        if mouth in mouth_mapping:
            mouth_patterns = mouth_mapping[mouth] + mouth_patterns
        else:
            mouth_patterns = [f"!口/_{mouth}_"] + mouth_patterns

        for pattern in mouth_patterns:
            mouth_file = self.loader.find_layer_file(pattern)
            if mouth_file:
                break

        if mouth_file:
            files["mouth"] = mouth_file
            # 口ファイルが変化した時だけログ
            if not hasattr(self, '_last_mouth_file') or self._last_mouth_file != mouth_file:
                print(f"[MOUTH_FILE] {mouth} -> {mouth_file}")
                self._last_mouth_file = mouth_file
        else:
            print(f"[MOUTH_ERROR] 口未発見: {mouth}")
            self._warn_once(f"missing:口/{mouth}", f"[WARN] 口ファイル未検出: 口/{mouth}")
        
        return files

    def _find_by_keywords(self, *keywords):
        """キーワード検索のラッパー"""
        return self.loader.find_by_keywords(*keywords)