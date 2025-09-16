"""文字列正規化ユーティリティ"""
import re
import unicodedata

def normalize_key(s: str) -> str:
    """表記ゆれ正規化：NFKC、記号/不可視除去、_pos_座標除去、先頭アンダースコア除去、下線無視、区切り統一"""
    if not s:
        return ""
    t = unicodedata.normalize("NFKC", s).lower()
    t = t.replace("\\", "/").strip()
    t = re.sub(r"\s+", "", t)                              # 空白
    # アスタリスクと感嘆符は保持、不可視文字のみ削除
    t = re.sub(r"[\u200b\u200c\u200d]+", "", t)            # 不可視文字のみ
    t = re.sub(r"_pos_\d+_\d+_\d+_\d+", "", t)            # _pos_XXXX
    t = "/".join(p.lstrip("_") for p in t.split("/"))      # 各要素 先頭 _
    t = t.replace("_", "")                                 # 下線も無視（検出を緩く）
    t = re.sub(r"/+", "/", t)                              # // → /
    return t