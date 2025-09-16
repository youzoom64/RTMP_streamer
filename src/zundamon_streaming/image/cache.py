"""画像キャッシュ管理"""
from PIL import Image
from typing import Dict

class ImageCache:
    def __init__(self):
        self._cache: Dict[str, Image.Image] = {}
    
    def get(self, path: str) -> Image.Image:
        """キャッシュから画像取得、なければ読み込み"""
        if path not in self._cache:
            self._cache[path] = Image.open(path).convert("RGBA")
        return self._cache[path]
    
    def clear(self):
        """キャッシュクリア"""
        self._cache.clear()
