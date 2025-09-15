# zundamon_layer_animator.py ーー 完全修正版
import os
import json
import subprocess
import time
import threading
import queue
import requests
import tempfile
import random
from streamer import VoiceVoxStreamer
import pygame
import re
import unicodedata
# === ヘルパー（クラスの外） =====================================

def _norm_key(s: str) -> str:
    """表記ゆれ正規化：NFKC、大小無視、全/半角混在、!*や空白など除去、区切り統一"""
    if not s:
        return ""
    t = unicodedata.normalize("NFKC", s).lower()
    t = t.replace("\\", "/").strip()
    # 空白全除去
    t = re.sub(r"\s+", "", t)
    # よくある装飾や不可視文字を除去（*, !, 全角版, ゼロ幅など）
    t = re.sub(r"[\*\!！＊\u200b\u200c\u200d]+", "", t)
    # スラッシュ連続を1つに
    t = re.sub(r"/+", "/", t)
    return t

def _build_png_index(root_dir: str) -> dict:
    """root_dir 以下の全PNGをインデックス化して、正規化キー→相対パス(複数)にマップ"""
    index = {}
    for r, _, files in os.walk(root_dir):
        for f in files:
            if not f.lower().endswith(".png"):
                continue
            full = os.path.join(r, f)
            rel  = os.path.relpath(full, root_dir).replace("\\", "/")
            base = os.path.splitext(f)[0]

            keys = set()
            keys.add(_norm_key(rel))   # 例: 目/目セット/黒目/普通目.png
            keys.add(_norm_key(base))  # 例: 普通目
            parts = rel.split("/")
            for k in range(1, 5):      # 末尾1〜4階層の組み合わせでもヒットさせる
                tail = "/".join(parts[-k:])
                keys.add(_norm_key(tail))

            for k in keys:
                index.setdefault(k, []).append(rel)
    return index

# === クラス本体 =================================================

class ZundamonLayerAnimator(VoiceVoxStreamer):
    def __init__(self, layer_dir="zundamon"):
        super().__init__()
        self.layer_dir = layer_dir
        self.position_map = None
        self.png_index = {}                 # 事前インデックス
        self.speech_queue = queue.Queue()
        self.stream_process = None
        self.is_talking = False
        self.is_blinking = False

        pygame.mixer.init()

        self.load_position_map()
        self.png_index = _build_png_index(self.layer_dir)
        print(f"PNGインデックス: {len(self.png_index)} キー")

        self.current_mouth = "むふ"
        self.current_eyes  = "普通目"

        self.start_workers()
        self.debug_dump_index()

    def load_position_map(self):
        """位置情報マップ読み込み"""
        map_file = os.path.join(self.layer_dir, "position_map.json")
        try:
            with open(map_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.position_map = data
                print(f"位置情報マップ読み込み完了: {len(data.get('layers', {}))}レイヤー")
        except Exception as e:
            print(f"位置情報マップ読み込みエラー: {e}")

    def find_layer_file(self, layer_path):
        """位置マップ優先 → インデックス(厳密) → インデックス(ファジー) → 従来fallback"""
        # 1) position_map.json を最優先
        if self.position_map and "layers" in self.position_map:
            cand_keys = [
                layer_path,
                layer_path.replace("!", "").replace("*", ""),
                layer_path.split("/")[-1],
            ]
            for ck in cand_keys:
                nk = _norm_key(ck)
                for k, meta in self.position_map["layers"].items():
                    if _norm_key(k) == nk and isinstance(meta, dict):
                        file_rel = meta.get("file") or meta.get("path")
                        if file_rel:
                            fp = os.path.join(self.layer_dir, file_rel)
                            if os.path.exists(fp):
                                return fp

        # 2) インデックス(厳密一致)
        keys_to_try = [
            layer_path,
            layer_path.replace("!", "").replace("*", ""),
            layer_path.split("/")[-1],
        ]
        alt = {
            "目/目セット/黒目/普通目": ["黒目/普通目", "目セット/黒目/普通目", "普通目"],
            "目/目セット/普通白目":   ["目セット/普通白目", "普通白目"],
            "口/むふ": ["*むふ", "むふ"],
            "口/ほあー": ["*ほあー", "ほあー"],
        }
        if layer_path in alt:
            keys_to_try += alt[layer_path]

        for k in keys_to_try:
            nk = _norm_key(k)
            hits = self.png_index.get(nk)
            if hits:
                return os.path.join(self.layer_dir, hits[0])

        # 3) インデックス(ファジー一致) ーー 強化版
        target = _norm_key(layer_path)
        best = None  # (score, relpath)
        for k, rels in self.png_index.items():
            # 末尾一致・拡張子付末尾一致・部分一致を許容
            hit = False
            score = 0
            if k.endswith("/" + target):
                hit = True; score += 100
            if k.endswith("/" + target + ".png"):
                hit = True; score += 90
            if target in k:
                hit = True; score += 10
            if hit:
                # より具体的なキー（長い方）を優先
                score += 0.01 * len(k)
                cand = os.path.join(self.layer_dir, rels[0])
                if (best is None) or (score > best[0]):
                    best = (score, cand)
        if best:
            return best[1]


        # 4) 最後の手段：ディレクトリ直下 startswith
        path_parts = layer_path.split('/')
        current_path = self.layer_dir
        for part in path_parts[:-1]:
            current_path = os.path.join(current_path, part)
        layer_name = path_parts[-1]
        if os.path.exists(current_path):
            for filename in os.listdir(current_path):
                if filename.startswith(layer_name) and filename.endswith('.png'):
                    return os.path.join(current_path, filename)

        print(f"[WARN] ファイル未検出: {layer_path}")
        return None

    def _find_by_keywords_in_index(self, *keywords):
        """インデックスから AND 検索（全キーワードを含むキーのうち最も具体的なものを選ぶ）"""
        wants = [_norm_key(w) for w in keywords if w]
        best = None  # (score, relpath)
        for k, rels in self.png_index.items():
            if all(w in k for w in wants):
                # 具体的なキー（長い方）ほどスコア高
                score = len(k)
                cand = os.path.join(self.layer_dir, rels[0])
                if (best is None) or (score > best[0]):
                    best = (score, cand)
        return best[1] if best else None

    def debug_dump_index(self, *words):
        """インデックス中からキーワードを含むキー/パスを抜粋表示（デバッグ用）"""
        if not words:
            words = ("口","むふ","ほあ","目","普通目","普通白目","黒目","枝豆","服装","眉","uu")
        nw = [_norm_key(w) for w in words]
        print("=== PNG Index sample ===")
        shown = 0
        for k, rels in self.png_index.items():
            if any(w in k for w in nw):
                print("KEY:", k, "=>", rels[:2])
                shown += 1
                if shown >= 50:
                    print("...omitted...")
                    break


    def get_expression_files(self):
        """現在の表情に対応するファイルパスを取得（重ね順を厳密に制御）"""
        files = {}  # dictの挿入順＝重ね順

        # ---- 1) 素体（最下層）----
        body = (self.find_layer_file("服装2/素体")
                or self._find_by_keywords_in_index("素体"))
        if body:
            files["base_body"] = body
        else:
            print("[WARN] 素体が見つかりません")

        # ---- 2) 枝豆（アクセント系の下地）----
        edamame = (self.find_layer_file("枝豆/枝豆通常")
                or self._find_by_keywords_in_index("枝豆", "通常")
                or self._find_by_keywords_in_index("枝豆"))
        if edamame:
            files["base_edamame"] = edamame
        else:
            print("[INFO] 枝豆（通常）なし：スキップ")

        # ---- 3) 服（1つだけ選ぶ：いつもの服 > 制服 > 他）----
        outfit = (self.find_layer_file("服装1/いつもの服")
                or self.find_layer_file("服装1/制服")
                or self._find_by_keywords_in_index("服装1", "服")
                or self._find_by_keywords_in_index("服装1"))
        if outfit:
            files["outfit"] = outfit
        else:
            print("[WARN] 服装1 が見つからないため、服は未適用です")

        # ---- 4) 腕（服装1 の 左腕/右腕 基本 を狙う。無ければキーワードAND）----
        left_arm = (self.find_layer_file("服装1/左腕/基本")
                    or self._find_by_keywords_in_index("服装1", "左腕", "基本")
                    or self._find_by_keywords_in_index("左腕", "基本"))
        right_arm = (self.find_layer_file("服装1/右腕/基本")
                    or self._find_by_keywords_in_index("服装1", "右腕", "基本")
                    or self._find_by_keywords_in_index("右腕", "基本"))
        if left_arm:
            files["arm_left"] = left_arm
        else:
            print("[WARN] 左腕(基本)が見つかりません")
        if right_arm:
            files["arm_right"] = right_arm
        else:
            print("[WARN] 右腕(基本)が見つかりません")

        # ---- 5) 眉（1つだけ：普通眉 > 怒り眉 > 他）----
        brow = (self.find_layer_file("眉/普通眉")
                or self.find_layer_file("眉/怒り眉")
                or self._find_by_keywords_in_index("眉", "普通")
                or self._find_by_keywords_in_index("眉"))
        if brow:
            files["brow"] = brow
        else:
            print("[WARN] 眉が見つかりません")

        # ---- 6) 目（白目→黒目の順で“先に白目”を置いてから“黒目”を重ねる）----
        if self.current_eyes == "普通目":
            # 白目（先）
            eye_white = (self.find_layer_file("目/目セット/普通白目")
                        or self._find_by_keywords_in_index("目", "普通白目")
                        or self._find_by_keywords_in_index("白目"))
            if eye_white:
                files["eye_white"] = eye_white
            else:
                print("[WARN] 普通白目が見つかりません")

            # 黒目（後）
            eye_black = (self.find_layer_file("目/目セット/黒目/普通目")
                        or self.find_layer_file("目/目セット/黒目/普通目2")
                        or self.find_layer_file("目/目セット/黒目/普通目3")
                        or self.find_layer_file("目/目セット/黒目/カメラ目線")
                        or self._find_by_keywords_in_index("目", "黒目", "普通目")
                        or self._find_by_keywords_in_index("黒目", "普通目")
                        or self._find_by_keywords_in_index("黒目"))
            if eye_black:
                files["eye_black"] = eye_black
            else:
                print("[WARN] 黒目(普通目)が見つかりません")
        else:
            # 閉じ目や他表情は単枚
            eyes = (self.find_layer_file(f"目/{self.current_eyes}")
                    or (None if self.current_eyes == "UU" else self.find_layer_file("目/UU"))
                    or self._find_by_keywords_in_index("目", self.current_eyes)
                    or self._find_by_keywords_in_index("目", "uu")
                    or self._find_by_keywords_in_index("uu"))
            if eyes:
                files["eyes"] = eyes
            else:
                print(f"[WARN] 目ファイル未検出: 目/{self.current_eyes}")

        # ---- 7) 口（最後に重ねる）----
        mouth = (self.find_layer_file(f"口/{self.current_mouth}")
                or self._find_by_keywords_in_index("口", self.current_mouth)
                or self.find_layer_file("口/むふ")
                or self._find_by_keywords_in_index("口", "むふ")
                or self.find_layer_file("口/ほあー")
                or self._find_by_keywords_in_index("口", "ほあ")
                or self._find_by_keywords_in_index("ほあ"))
        if mouth:
            files["mouth"] = mouth
        else:
            print(f"[WARN] 口ファイル未検出: 口/{self.current_mouth}")

        print("使用レイヤー（重ね順）:", files)
        return files


    def start_workers(self):
        """ワーカースレッド開始"""
        threading.Thread(target=self.speech_worker, daemon=True).start()
        threading.Thread(target=self.blink_worker, daemon=True).start()

    def speech_worker(self):
        """音声処理ワーカー"""
        while True:
            try:
                text = self.speech_queue.get(timeout=1)
                print(f"音声生成: {text[:30]}...")
                audio_data = self.generate_voice_data(text)
                if audio_data:
                    self.current_mouth = "ほあー"  # 口開き
                    self.is_talking = True
                    self.play_audio_data(audio_data)
                    self.current_mouth = "むふ"    # 口閉じ
                    self.is_talking = False
                self.speech_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"音声処理エラー: {e}")

    def blink_worker(self):
        """まばたきワーカー"""
        while True:
            if not self.is_talking:
                original_eyes = self.current_eyes
                self.current_eyes = "UU"   # 目閉じ
                time.sleep(0.15)
                self.current_eyes = original_eyes
                time.sleep(2 + random.random() * 3)
            else:
                time.sleep(0.1)

    def generate_voice_data(self, text, speaker_id=3):
        """VOICEVOX音声生成"""
        try:
            query_response = requests.post(
                f"http://localhost:50021/audio_query",
                params={"text": text, "speaker": speaker_id}
            )
            query_response.raise_for_status()
            synthesis_response = requests.post(
                f"http://localhost:50021/synthesis",
                params={"speaker": speaker_id},
                json=query_response.json(),
                headers={"Content-Type": "application/json"}
            )
            synthesis_response.raise_for_status()
            return synthesis_response.content
        except Exception as e:
            print(f"音声生成エラー: {e}")
            return None

    def play_audio_data(self, audio_data):
        """音声再生"""
        try:
            tmp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            tmp_file.write(audio_data)
            tmp_file.close()
            tmp_file_path = tmp_file.name
            time.sleep(0.1)
            pygame.mixer.music.load(tmp_file_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            pygame.mixer.music.unload()
            time.sleep(0.1)
            os.unlink(tmp_file_path)
        except Exception as e:
            print(f"音声再生エラー: {e}")

    def add_speech(self, text):
        """音声をキューに追加"""
        if text.strip():
            self.speech_queue.put(text)
            print(f"音声追加: {text[:30]}...")

    def change_expression(self, mouth=None, eyes=None):
        """表情変更"""
        if mouth:
            self.current_mouth = mouth
            print(f"口変更: {mouth}")
        if eyes:
            self.current_eyes = eyes
            print(f"目変更: {eyes}")

    def start_layer_stream(self, background_video):
        """レイヤー構成による配信開始"""
        if not os.path.exists(background_video):
            print(f"背景動画が見つかりません: {background_video}")
            return False

        if not self.start_rtmp_server():
            return False

        time.sleep(3)

        expression_files = self.get_expression_files()
        print(f"使用レイヤーキー: {list(expression_files.keys())}")

        if not expression_files:
            print("表情ファイルが見つかりません")
            self.stop_rtmp_server()
            return False

        # FFmpegコマンド構築
        cmd = ['ffmpeg', '-stream_loop', '-1', '-i', background_video]
        for layer_file in expression_files.values():
            cmd.extend(['-loop', '1', '-i', layer_file])

        # フィルター構築（順次オーバーレイ）
        filter_parts = []
        current_input = '[0:v]'  # 背景動画
        for i, (layer_name, _) in enumerate(expression_files.items(), 1):
            output_name = f'[layer{i}]' if i < len(expression_files) else '[out]'
            filter_parts.append(f'{current_input}[{i}:v]overlay{output_name}')
            current_input = output_name

        cmd.extend([
            '-filter_complex', ';'.join(filter_parts),
            '-map', '[out]', '-map', '0:a',
            '-c:v', 'libx264', '-preset', 'ultrafast',
            '-c:a', 'aac', '-f', 'flv', self.rtmp_url
        ])

        print("レイヤーアニメーション配信開始")
        self.stream_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        def monitor_ffmpeg():
            try:
                for line in self.stream_process.stdout:
                    print(f"FFmpeg: {line.strip()}")
            except:
                pass

        threading.Thread(target=monitor_ffmpeg, daemon=True).start()

        time.sleep(3)
        if self.stream_process.poll() is not None:
            print("FFmpegプロセス異常終了")
            self.stop_rtmp_server()
            return False

        print("配信開始完了")
        return True

    def stop_stream(self):
        """配信停止"""
        if self.stream_process:
            self.stream_process.terminate()
            self.stream_process = None
        self.stop_rtmp_server()
        print("配信停止")


    def debug_dump_index(self, *words):
        """インデックス中からキーワードを含むキー/パスを拾って上位だけ表示"""
        if not words:
            words = ("口", "むふ", "ほあ", "目", "黒目", "普通目", "普通白目", "uu")
        nw = [_norm_key(w) for w in words]
        shown = 0
        print("=== PNGインデックス ダンプ ===")
        for k, rels in list(self.png_index.items())[:]:
            if any(w in k for w in nw):
                print("KEY:", k, "=>", rels[:3])
                shown += 1
                if shown >= 40:  # 出し過ぎ防止
                    print("... more omitted ...")
                    break
    def debug_dump_index(self, *words):
        if not words:
            words = ("口","むふ","ほあ","目","普通目","普通白目","黒目","枝豆","服装","眉","uu")
        nw = [_norm_key(w) for w in words]
        print("=== PNG Index sample ===")
        shown = 0
        for k, rels in self.png_index.items():
            if any(w in k for w in nw):
                print("KEY:", k, "=>", rels[:2])
                shown += 1
                if shown >= 50:
                    print("...omitted...")
                    break



def main():
    background_video = "D:/Bandicam/CharaStudio 2025-04-01 11-45-21-752.mp4"

    if not os.path.exists(background_video):
        print(f"背景動画が見つかりません: {background_video}")
        return

    animator = ZundamonLayerAnimator()

    try:
        if not animator.start_layer_stream(background_video):
            return

        print("VLCで rtmp://localhost:1935/live/test-stream を開いてください")
        print("コマンド:")
        print("  テキスト = 音声で話す")
        print("  'happy' = 笑顔に変更")
        print("  'normal' = 通常に戻す")
        print("  'exit' = 終了")

        while True:
            text = input("\n入力: ")
            if text.lower() == 'exit':
                break
            elif text.lower() == 'happy':
                animator.change_expression(mouth="にっこり", eyes="にっこり")
            elif text.lower() == 'normal':
                animator.change_expression(mouth="むふ", eyes="普通目")
            else:
                animator.add_speech(text)

    except KeyboardInterrupt:
        print("\n配信停止中...")
    finally:
        animator.stop_stream()

    def _find_by_keywords_in_index(self, *keywords):
        """インデックスから AND 検索（すべて含むキーを最も具体的なものから選ぶ）"""
        wants = [_norm_key(w) for w in keywords if w]
        best = None  # (len_key, relpath)
        for k, rels in self.png_index.items():
            if all(w in k for w in wants):
                cand = os.path.join(self.layer_dir, rels[0])
                if (best is None) or (len(k) > best[0]):
                    best = (len(k), cand)
        return best[1] if best else None




if __name__ == "__main__":
    main()
