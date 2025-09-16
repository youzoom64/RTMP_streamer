"""画像合成エンジン - 3ストリーム配信対応"""
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
        
        # ベース画像を一度だけ生成
        self.base_image = self._create_base_image()
        
    def _create_base_image(self):
        """固定ベース画像（体・服・腕・眉のみ）"""
        base_size = (1082, 1650)
        canvas = Image.new("RGBA", base_size, (0, 0, 0, 0))
        
        # 1) 素体（最下層）
        body = (self.loader.find_layer_file("服装2/素体") or 
                self.loader.find_layer_file("素体"))
        if body:
            img = self.cache.get(body)
            canvas.alpha_composite(img, dest=(0, 0))
        
        # 2) 枝豆（任意）
        edamame = self.loader.find_layer_file("枝豆/枝豆通常")
        if edamame:
            img = self.cache.get(edamame)
            canvas.alpha_composite(img, dest=(0, 0))
        
        # 3) 服
        outfit = (self.loader.find_layer_file("服装1/いつもの服") or
                  self.loader.find_layer_file("服装1/制服"))
        if outfit:
            img = self.cache.get(outfit)
            canvas.alpha_composite(img, dest=(0, 0))
        
        # 4) 腕
        left_arm = (self.loader.find_layer_file("_服装1/!左腕/*基本*") or
                    self._find_by_keywords("左腕", "基本"))
        if left_arm:
            img = self.cache.get(left_arm)
            canvas.alpha_composite(img, dest=(0, 0))
            
        right_arm = (self.loader.find_layer_file("_服装1/!右腕/*基本*") or
                    self._find_by_keywords("右腕", "基本"))
        if right_arm:
            img = self.cache.get(right_arm)
            canvas.alpha_composite(img, dest=(0, 0))
        
        # 5) 眉
        brow = (self.loader.find_layer_file("眉/普通眉") or
                self.loader.find_layer_file("眉/怒り眉"))
        if brow:
            img = self.cache.get(brow)
            canvas.alpha_composite(img, dest=(0, 0))
        
        return canvas
    
    def get_base_image(self):
        """ベース画像取得（コピーを返す）"""
        return self.base_image.copy()
    
    def create_mouth_part(self, mouth: str):
        """口パーツ専用画像生成（透明背景）"""
        base_size = (1082, 1650)
        canvas = Image.new("RGBA", base_size, (0, 0, 0, 0))
        
        # 口パーツファイル検索
        mouth_patterns = [f"!口/_{mouth}_", f"!口/{mouth}"]
        
        mouth_mapping = {
            "むふ": ["!口/_むふ_"],
            "ほあー": ["!口/_ほあー_", "!口/_ほあ_", "!口/_ほー_"],
            "ほあ": ["!口/_ほあ_", "!口/_ほあー_"],
        }
        
        if mouth in mouth_mapping:
            mouth_patterns = mouth_mapping[mouth] + mouth_patterns
        
        mouth_file = None
        for pattern in mouth_patterns:
            mouth_file = self.loader.find_layer_file(pattern)
            if mouth_file:
                break
        
        if mouth_file:
            img = self.cache.get(mouth_file)
            canvas.alpha_composite(img, dest=(0, 0))
            trace_log(f"口パーツ生成: {mouth} -> {mouth_file}")
        else:
            trace_log(f"口パーツ未発見: {mouth}", "ERROR")
        
        return canvas
    
    def create_eyes_part(self, eyes: str):
        """目パーツ専用画像生成（透明背景）"""
        base_size = (1082, 1650)
        canvas = Image.new("RGBA", base_size, (0, 0, 0, 0))
        
        if eyes == "普通目":
            # 白目 + 黒目の組み合わせ
            eye_white = self.loader.find_layer_file("目/目セット/普通白目")
            if eye_white:
                img = self.cache.get(eye_white)
                canvas.alpha_composite(img, dest=(0, 0))
            
            eye_black = self.loader.find_layer_file("目/目セット/黒目/普通目")
            if eye_black:
                img = self.cache.get(eye_black)
                canvas.alpha_composite(img, dest=(0, 0))
        else:
            # 単一目ファイル
            eye_file = self.loader.find_layer_file(f"目/{eyes}")
            if eye_file:
                img = self.cache.get(eye_file)
                canvas.alpha_composite(img, dest=(0, 0))
        
        trace_log(f"目パーツ生成: {eyes}")
        return canvas
    
    def _find_by_keywords(self, *keywords):
        """キーワード検索のラッパー"""
        return self.loader.find_by_keywords(*keywords)