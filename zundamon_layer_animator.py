# zundamon_layer_animator.py ーー 完全修正版（座標いじらない / PNGそのまま重ね）
import os
import json
import subprocess
import time
import threading
import queue
import requests
import tempfile
import random
import re
import unicodedata
from PIL import Image
import pygame

# 依存: streamer.py に VoiceVoxStreamer （start_rtmp_server/stop_rtmp_server/rtmp_url）実装前提
from streamer import VoiceVoxStreamer


# =========================
# 正規化 ＆ PNGインデックス
# =========================
def _norm_key(s: str) -> str:
    """表記ゆれ正規化：NFKC、記号/不可視除去、_pos_座標除去、先頭アンダースコア除去、下線無視、区切り統一"""
    if not s:
        return ""
    t = unicodedata.normalize("NFKC", s).lower()
    t = t.replace("\\", "/").strip()
    t = re.sub(r"\s+", "", t)                              # 空白
    t = re.sub(r"[\*\!！＊\u200b\u200c\u200d]+", "", t)    # *,!,不可視
    t = re.sub(r"_pos_\d+_\d+_\d+_\d+", "", t)            # _pos_XXXX
    t = "/".join(p.lstrip("_") for p in t.split("/"))      # 各要素 先頭 _
    t = t.replace("_", "")                                 # 下線も無視（検出を緩く）
    t = re.sub(r"/+", "/", t)                              # // → /
    return t


def _build_png_index(root_dir: str) -> dict:
    """root_dir 以下のPNGを正規化キー→相対パス(複数)の辞書に"""
    index = {}
    for r, _, files in os.walk(root_dir):
        for f in files:
            if not f.lower().endswith(".png"):
                continue
            full = os.path.join(r, f)
            rel  = os.path.relpath(full, root_dir).replace("\\", "/")
            base = os.path.splitext(f)[0]

            def _clean(s):
                s = re.sub(r"_pos_\d+_\d+_\d+_\d+", "", s)
                s = "/".join(p.lstrip("_") for p in s.split("/"))
                return s

            rel_clean  = _clean(rel)
            base_clean = _clean(base)
            parts = rel_clean.split("/")

            keys = set()
            keys.add(_norm_key(rel_clean))   # 例: 目/目セット/黒目/普通目.png
            keys.add(_norm_key(base_clean))  # 例: 普通目
            for k in range(1, 5):            # 末尾1〜4要素
                tail = "/".join(parts[-k:])
                keys.add(_norm_key(tail))
            for p in parts:                   # 各要素単体（普通白目, 黒目, いつもの服 等）
                keys.add(_norm_key(p))

            for k in keys:
                index.setdefault(k, []).append(rel)
    return index


# =========================
# 本体
# =========================
class ZundamonLayerAnimator(VoiceVoxStreamer):
    def __init__(self, layer_dir="zundamon", fps=30, out_dir=None):
        super().__init__()
        self.layer_dir = layer_dir
        self.fps = int(fps)
        self.out_dir = out_dir or os.path.join(layer_dir, "frames")
        os.makedirs(self.out_dir, exist_ok=True)

        self.position_map = None
        self.png_index = {}
        self.speech_queue = queue.Queue()
        self.stream_process = None
        self.is_talking = False

        self.current_mouth = "むふ"     # 初期：口閉じ
        self.current_eyes  = "普通目"   # 初期：目開き

        # 内部制御
        self._warned_once = set()          # 同じWARNは一度だけ
        self._last_files_printed = None    # レイヤー構成の差分出力用
        self._render_thread = None
        self._stop_event = threading.Event()
        self._frame_no = 0
        self._img_cache = {}               # 画像キャッシュ（パス→PIL.Image）

        # pygame 音声
        pygame.mixer.init()

        # 位置情報＆インデックス
        self.load_position_map()
        self.png_index = _build_png_index(self.layer_dir)
        print(f"PNGインデックス: {len(self.png_index)} キー")
        self._debug_dump_index()  # 抜粋

        # ワーカー
        self._start_workers()

    # ---------- ユーティリティ ----------
    def _warn_once(self, key: str, msg: str):
        if key in self._warned_once:
            return
        print(msg)
        self._warned_once.add(key)

    def _print_files_once_on_change(self, files: dict):
        snapshot = tuple((k, os.path.relpath(v, self.layer_dir) if v else None)
                         for k, v in files.items())
        if snapshot != self._last_files_printed:
            print("使用レイヤー（重ね順）:", files)
            self._last_files_printed = snapshot

    def _debug_dump_index(self, *words):
        if not words:
            words = ("口", "むふ", "ほあ", "目", "黒目", "普通目", "普通白目", "uu", "枝豆", "服装", "眉")
        picks = [_norm_key(w) for w in words]
        print("=== PNG Index sample ===")
        shown = 0
        for k, rels in self.png_index.items():
            if any(w in k for w in picks):
                print("KEY:", k, "=>", rels[:2])
                shown += 1
                if shown >= 50:
                    print("...omitted...")
                    break

    # ---------- 位置マップ / 検索 ----------
    def load_position_map(self):
        map_file = os.path.join(self.layer_dir, "position_map.json")
        try:
            with open(map_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.position_map = data
                print(f"位置情報マップ読み込み完了: {len(data.get('layers', {}))}レイヤー")
        except Exception as e:
            print(f"位置情報マップ読み込みエラー: {e}")

    def _find_by_keywords_in_index(self, *keywords):
        """AND検索：全キーワードを含むキーのうち最も具体的なもの"""
        wants = [_norm_key(w) for w in keywords if w]
        best = None  # (score, relpath)
        for k, rels in self.png_index.items():
            if all(w in k for w in wants):
                score = len(k)
                cand = os.path.join(self.layer_dir, rels[0])
                if (best is None) or (score > best[0]):
                    best = (score, cand)
        return best[1] if best else None

    def find_layer_file(self, layer_path):
        """
        位置マップ → インデックス(厳密) → インデックス(ファジー) → 直下startswith の順。
        見つからなければ WARN 一度だけ。
        """
        # 1) position_map.json
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

        # 2) インデックス（厳密）
        keys_to_try = [
            layer_path,
            layer_path.replace("!", "").replace("*", ""),
            layer_path.split("/")[-1],
        ]
        alt = {
            "目/目セット/黒目/普通目": ["黒目/普通目", "目セット/黒目/普通目", "普通目"],
            "目/目セット/普通白目":   ["目セット/普通白目", "普通白目"],
            "口/むふ": ["むふ"],
            "口/ほあー": ["ほあー", "ほあ"],
        }
        if layer_path in alt:
            keys_to_try += alt[layer_path]

        for k in keys_to_try:
            nk = _norm_key(k)
            hits = self.png_index.get(nk)
            if hits:
                return os.path.join(self.layer_dir, hits[0])

        # 3) インデックス（ファジー）
        target = _norm_key(layer_path)
        best = None
        for k, rels in self.png_index.items():
            hit = False
            score = 0
            if k.endswith("/" + target):
                hit = True; score += 100
            if k.endswith("/" + target + ".png"):
                hit = True; score += 90
            if target in k:
                hit = True; score += 10
            if hit:
                score += 0.01 * len(k)
                cand = os.path.join(self.layer_dir, rels[0])
                if (best is None) or (score > best[0]):
                    best = (score, cand)
        if best:
            return best[1]

        # 4) 最後の手段：直下 startswith
        path_parts = layer_path.split('/')
        current_path = self.layer_dir
        for part in path_parts[:-1]:
            current_path = os.path.join(current_path, part)
        layer_name = path_parts[-1]
        if os.path.exists(current_path):
            for filename in os.listdir(current_path):
                if filename.startswith(layer_name) and filename.endswith('.png'):
                    return os.path.join(current_path, filename)

        self._warn_once(f"missing:{layer_path}", f"[WARN] ファイル未検出: {layer_path}")
        return None

    # ---------- レイヤー解決（重ね順を厳密） ----------
    def get_expression_files(self):
        """
        現在の表情に対応するファイルパス群を返す（dict挿入順 = 重ね順）
        座標はいじらない。PNGはすべて (0,0) で重ねる。
        """
        files = {}

        # 1) 素体（最下層）
        body = (self.find_layer_file("服装2/素体")
                or self._find_by_keywords_in_index("素体"))
        if body:
            files["base_body"] = body
        else:
            self._warn_once("missing:素体", "[WARN] 素体が見つかりません")

        # 2) 枝豆（任意）
        edamame = (self.find_layer_file("枝豆/枝豆通常")
                   or self._find_by_keywords_in_index("枝豆", "通常")
                   or self._find_by_keywords_in_index("枝豆"))
        if edamame:
            files["base_edamame"] = edamame

        # 3) 服（いつもの服 > 制服）
        outfit = (self.find_layer_file("服装1/いつもの服")
                  or self.find_layer_file("服装1/制服")
                  or self._find_by_keywords_in_index("服装1", "服"))
        if outfit:
            files["outfit"] = outfit
        else:
            self._warn_once("missing:服装1", "[WARN] 服が見つかりません（裸に見える可能性）")

        # 4) 腕（服装1/左腕/基本、服装1/右腕/基本）
        left_arm = (self.find_layer_file("服装1/左腕/基本")
                    or self._find_by_keywords_in_index("服装1", "左腕", "基本")
                    or self._find_by_keywords_in_index("左腕", "基本"))
        right_arm = (self.find_layer_file("服装1/右腕/基本")
                     or self._find_by_keywords_in_index("服装1", "右腕", "基本")
                     or self._find_by_keywords_in_index("右腕", "基本"))
        if left_arm:
            files["arm_left"] = left_arm
        else:
            self._warn_once("missing:左腕基本", "[WARN] 左腕(基本)が見つかりません")
        if right_arm:
            files["arm_right"] = right_arm
        else:
            self._warn_once("missing:右腕基本", "[WARN] 右腕(基本)が見つかりません")

        # 5) 眉（普通眉 > 怒り眉）
        brow = (self.find_layer_file("眉/普通眉")
                or self.find_layer_file("眉/怒り眉")
                or self._find_by_keywords_in_index("眉", "普通"))
        if brow:
            files["brow"] = brow
        else:
            self._warn_once("missing:眉", "[WARN] 眉が見つかりません")

        # 6) 目（白目→黒目の順に重ねる / 閉じ目は単枚）
        if self.current_eyes == "普通目":
            eye_white = (self.find_layer_file("目/目セット/普通白目")
                         or self._find_by_keywords_in_index("目", "普通白目")
                         or self._find_by_keywords_in_index("白目"))
            if eye_white:
                files["eye_white"] = eye_white
            else:
                self._warn_once("missing:普通白目", "[WARN] 普通白目が見つかりません")

            eye_black = (self.find_layer_file("目/目セット/黒目/普通目")
                         or self.find_layer_file("目/目セット/黒目/普通目2")
                         or self.find_layer_file("目/目セット/黒目/普通目3")
                         or self.find_layer_file("目/目セット/黒目/カメラ目線")
                         or self._find_by_keywords_in_index("目", "黒目", "普通目")
                         or self._find_by_keywords_in_index("黒目", "普通目"))
            if eye_black:
                files["eye_black"] = eye_black
            else:
                self._warn_once("missing:黒目普通目", "[WARN] 黒目(普通目)が見つかりません")
        else:
            eyes = (self.find_layer_file(f"目/{self.current_eyes}")
                    or (None if self.current_eyes == "UU" else self.find_layer_file("目/UU"))
                    or self._find_by_keywords_in_index("目", self.current_eyes)
                    or self._find_by_keywords_in_index("目", "uu")
                    or self._find_by_keywords_in_index("uu"))
            if eyes:
                files["eyes"] = eyes
            else:
                self._warn_once(f"missing:目/{self.current_eyes}", f"[WARN] 目ファイル未検出: 目/{self.current_eyes}")

        # 7) 口（最後に重ねる）
        mouth = (self.find_layer_file(f"口/{self.current_mouth}")
                 or self._find_by_keywords_in_index("口", self.current_mouth)
                 or self.find_layer_file("口/むふ")
                 or self._find_by_keywords_in_index("口", "むふ")
                 or self.find_layer_file("口/ほあー")
                 or self._find_by_keywords_in_index("口", "ほあ"))
        if mouth:
            files["mouth"] = mouth
        else:
            self._warn_once(f"missing:口/{self.current_mouth}", f"[WARN] 口ファイル未検出: 口/{self.current_mouth}")

        self._print_files_once_on_change(files)
        return files

    # ---------- 画像合成（PNGそのまま重ね / 0,0） ----------
    def _open_image_cached(self, path: str) -> Image.Image:
        im = self._img_cache.get(path)
        if im is None:
            im = Image.open(path).convert("RGBA")
            self._img_cache[path] = im
        return im

    def _compose_current_frame(self) -> Image.Image:
        """
        現在の self.current_mouth / self.current_eyes から合成。
        PNGを座標いじらず (0,0) で順に alpha_composite する。
        キャンバスサイズは最初に見つかったベース画像のサイズに合わせる。
        """
        files = self.get_expression_files()
        # キャンバス基準：base_body → outfit → どれも無ければ最初の要素
        base_key_order = ["base_body", "outfit", "base_edamame", "arm_left", "arm_right", "brow",
                          "eye_white", "eye_black", "eyes", "mouth"]
        base_size = None
        for k in ["base_body", "outfit", "base_edamame"]:
            if k in files:
                base_size = self._open_image_cached(files[k]).size
                break
        if base_size is None and len(files) > 0:
            any_path = next(iter(files.values()))
            base_size = self._open_image_cached(any_path).size
        if base_size is None:
            # 何も無い：透明1x1
            return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

        canvas = Image.new("RGBA", base_size, (0, 0, 0, 0))
        # dict挿入順（get_expression_filesの順）で重ねる
        for key in files:
            img = self._open_image_cached(files[key])
            # サイズが違っても座標は動かさない。PNGのまま (0,0) に重ねる
            if img.size != base_size:
                # サイズが違う場合はそのまま左上に被せる（ユーザー指定：座標いじらない）
                pass
            canvas.alpha_composite(img, dest=(0, 0))
        return canvas

    # ---------- フレーム生成/保存 ----------
    def _save_frame(self, img: Image.Image):
        path = os.path.join(self.out_dir, f"current_{self._frame_no:06d}.png")
        img.save(path)  # .png 拡張子固定（.tmp禁止）
        self._frame_no += 1

    def _seed_frames(self, seconds: float = 1.0):
        """配信前に先行フレーム生成：FFmpegの入力安定用"""
        n = max(1, int(self.fps * seconds))
        for _ in range(n):
            img = self._compose_current_frame()
            self._save_frame(img)

    def _render_loop(self):
        """常時レンダリング（blink/口はワーカーで state を更新、ここは現状を描画するだけ）"""
        interval = 1.0 / self.fps
        next_t = time.perf_counter()
        while not self._stop_event.is_set():
            img = self._compose_current_frame()
            self._save_frame(img)
            next_t += interval
            sleep = next_t - time.perf_counter()
            if sleep > 0:
                time.sleep(sleep)
            else:
                # 間に合ってないときは次フレームへ（落ち着いたら追いつく）
                next_t = time.perf_counter()

    # ---------- 音声（VOICEVOX） ----------
    def generate_voice_data(self, text, speaker_id=3):
        try:
            q = requests.post(
                "http://localhost:50021/audio_query",
                params={"text": text, "speaker": speaker_id}
            )
            q.raise_for_status()
            syn = requests.post(
                "http://localhost:50021/synthesis",
                params={"speaker": speaker_id},
                json=q.json(),
                headers={"Content-Type": "application/json"}
            )
            syn.raise_for_status()
            return syn.content
        except Exception as e:
            print(f"音声生成エラー: {e}")
            return None

    def play_audio_data(self, audio_data: bytes):
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.write(audio_data)
            tmp.close()
            p = tmp.name
            time.sleep(0.05)
            pygame.mixer.music.load(p)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy() and not self._stop_event.is_set():
                time.sleep(0.05)
            pygame.mixer.music.unload()
            time.sleep(0.02)
            os.unlink(p)
        except Exception as e:
            print(f"音声再生エラー: {e}")

    # ---------- ワーカー ----------
    def _start_workers(self):
        # まばたき
        def blink_worker():
            while not self._stop_event.is_set():
                if not self.is_talking:
                    original = self.current_eyes
                    self.current_eyes = "UU"
                    time.sleep(0.12)  # まばたき時間
                    self.current_eyes = original
                    time.sleep(2.0 + random.random() * 3.0)
                else:
                    time.sleep(0.1)
        threading.Thread(target=blink_worker, daemon=True).start()

        # 音声（口開閉は簡易。再生中 = ほあー / 終了 = むふ）
        def speech_worker():
            while not self._stop_event.is_set():
                try:
                    text = self.speech_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                if not text.strip():
                    self.speech_queue.task_done()
                    continue
                print(f"音声生成: {text[:30]}...")
                wav = self.generate_voice_data(text)
                if wav:
                    self.current_mouth = "ほあー"
                    self.is_talking = True
                    self.play_audio_data(wav)
                    self.is_talking = False
                    self.current_mouth = "むふ"
                self.speech_queue.task_done()
        threading.Thread(target=speech_worker, daemon=True).start()

    # ---------- API ----------
    def add_speech(self, text):
        if text.strip():
            self.speech_queue.put(text)
            print(f"音声追加: {text[:30]}...")

    def change_expression(self, mouth=None, eyes=None):
        if mouth:
            self.current_mouth = mouth
            print(f"口変更: {mouth}")
        if eyes:
            self.current_eyes = eyes
            print(f"目変更: {eyes}")

    # ---------- 配信 ----------
    def start_layer_stream(self, background_video: str):
        if not os.path.exists(background_video):
            print(f"背景動画が見つかりません: {background_video}")
            return False

        if not self.start_rtmp_server():
            return False

        time.sleep(1.0)

        # 先行フレーム（1秒分）
        # ※開始前に frames をクリアしておくと安全
        for f in os.listdir(self.out_dir):
            if f.startswith("current_") and f.endswith(".png"):
                try:
                    os.remove(os.path.join(self.out_dir, f))
                except:
                    pass
        self._frame_no = 0
        self._seed_frames(seconds=1.0)

        # 継続レンダスレッドスタート
        self._stop_event.clear()
        self._render_thread = threading.Thread(target=self._render_loop, daemon=True)
        self._render_thread.start()

        # FFmpeg起動（BG + image2シーケンス）
        # PNGは (0,0) でBGに重ねるだけ。サイズ違いでも座標はいじらない。
        pattern = os.path.join(self.out_dir, "current_%06d.png")
        cmd = [
            "ffmpeg",
            "-re",
            "-stream_loop", "-1", "-i", background_video,
            "-framerate", str(self.fps), "-start_number", "0", "-i", pattern,
            "-filter_complex", "[0:v][1:v]overlay[outv]",
            "-map", "[outv]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac", "-f", "flv", self.rtmp_url
        ]
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

        # 起動確認
        time.sleep(2.0)
        if self.stream_process.poll() is not None:
            print("FFmpegプロセス異常終了")
            self.stop_stream()
            return False

        print("配信開始完了")
        return True

    def stop_stream(self):
        self._stop_event.set()
        if self._render_thread:
            self._render_thread.join(timeout=2.0)
            self._render_thread = None
        if self.stream_process:
            try:
                self.stream_process.terminate()
            except:
                pass
            self.stream_process = None
        self.stop_rtmp_server()
        print("配信停止")


# =========================
# 実行
# =========================
def main():
    # ★背景動画はユーザーの環境に合わせて変更
    background_video = "D:/Bandicam/CharaStudio 2025-04-01 11-45-21-752.mp4"
    if not os.path.exists(background_video):
        print(f"背景動画が見つかりません: {background_video}")
        return

    animator = ZundamonLayerAnimator(layer_dir="zundamon", fps=30)

    try:
        if not animator.start_layer_stream(background_video):
            return

        print("VLCで rtmp://localhost:1935/live/test-stream を開いてください")
        print("コマンド:")
        print("  テキスト = 音声で話す")
        print("  'happy'  = 笑顔（例）")
        print("  'normal' = 通常に戻す")
        print("  'exit'   = 終了")

        while True:
            text = input("\n入力: ").strip()
            if text.lower() == "exit":
                break
            elif text.lower() == "happy":
                animator.change_expression(mouth="ほあー", eyes="にっこり")
            elif text.lower() == "normal":
                animator.change_expression(mouth="むふ", eyes="普通目")
            else:
                animator.add_speech(text)

    except KeyboardInterrupt:
        print("\n配信停止中...")
    finally:
        animator.stop_stream()


if __name__ == "__main__":
    main()
