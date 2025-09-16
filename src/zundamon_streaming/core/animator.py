"""メインアニメーターエンジン - 3ストリーム配信対応"""
import os
import time
import threading
import queue
from PIL import Image
from ..image.compositor import ImageCompositor
from ..audio.voicevox import VoiceVoxClient
from ..audio.player import AudioPlayer
from ..expression.state import ExpressionState
from ..expression.animation import BlinkAnimator
from ..rtmp.server import RTMPServer
from ..rtmp.ffmpeg import FFmpegStreamer

def trace_log(message, level="INFO"):
    timestamp = time.time()
    thread_id = threading.current_thread().ident
    print(f"[{timestamp:.3f}][{thread_id}][{level}] {message}")

class ZundamonAnimator:
    def __init__(self, layer_dir: str = "assets/zundamon", fps: int = 30):
        trace_log("ZundamonAnimator初期化開始")
        
        self.layer_dir = layer_dir
        self.fps = fps
        
        # 3ストリーム用ディレクトリ作成
        self.base_dir = os.path.join(layer_dir, "base")
        self.mouth_dir = os.path.join(layer_dir, "mouth")
        self.eyes_dir = os.path.join(layer_dir, "eyes")
        os.makedirs(self.base_dir, exist_ok=True)
        os.makedirs(self.mouth_dir, exist_ok=True)
        os.makedirs(self.eyes_dir, exist_ok=True)
        
        # コンポーネント初期化
        self.compositor = ImageCompositor(layer_dir)
        self.voicevox = VoiceVoxClient()
        self.audio_player = AudioPlayer()
        self.expression_state = ExpressionState()
        self.blink_animator = BlinkAnimator(self.expression_state)
        self.rtmp_server = RTMPServer()
        self.ffmpeg_streamer = FFmpegStreamer()
        
        # 3ストリーム管理
        self._frame_no = 0
        self._frame_lock = threading.Lock()
        self.current_mouth = "むふ"
        self.current_eyes = "普通目"
        
        # AudioPlayerにコールバック設定
        self.audio_player.mouth_callback = self._mouth_callback
        
        # 内部状態
        self.speech_queue = queue.Queue()
        self._render_thread = None
        self._speech_thread = None
        self._stop_event = threading.Event()
        
        # ワーカー開始
        self._start_workers()
        
        trace_log("ZundamonAnimator初期化完了")
    
    def start_layer_stream(self, background_video: str = None) -> bool:
        """3ストリーム配信開始"""
        trace_log("3ストリーム配信開始")
        
        if not self.rtmp_server.start():
            trace_log("RTMPサーバー起動失敗", "ERROR")
            return False
        
        time.sleep(1.0)
        
        # 3ストリーム初期フレーム生成
        self._generate_initial_streams()
        
        # レンダリング開始（目の更新用）
        self._stop_event.clear()
        self._render_thread = threading.Thread(target=self._eyes_render_loop, daemon=True)
        self._render_thread.start()
        
        # まばたき開始
        self.blink_animator.start()
        
        # FFmpeg 3ストリーム配信開始
        base_pattern = os.path.join(self.base_dir, "base_%06d.png")
        mouth_pattern = os.path.join(self.mouth_dir, "mouth_%06d.png")
        eyes_pattern = os.path.join(self.eyes_dir, "eyes_%06d.png")
        
        if not self.ffmpeg_streamer.start_3stream(
            base_pattern, mouth_pattern, eyes_pattern, 
            self.rtmp_server.rtmp_url, self.fps
        ):
            trace_log("FFmpeg 3ストリーム配信開始失敗", "ERROR")
            self.stop_stream()
            return False
        
        trace_log("3ストリーム配信開始完了")
        return True
    
    def _generate_initial_streams(self):
        """3ストリーム初期化"""
        trace_log("3ストリーム初期フレーム生成開始")
        
        # ベース画像を一度だけ生成・保存
        base_frame = self.compositor.get_base_image()
        for i in range(60):
            base_frame.save(os.path.join(self.base_dir, f"base_{i:06d}.png"))
        
        # 初期口・目フレーム生成
        mouth_frame = self.compositor.create_mouth_part("むふ")
        eyes_frame = self.compositor.create_eyes_part("普通目")
        
        for i in range(60):
            mouth_frame.save(os.path.join(self.mouth_dir, f"mouth_{i:06d}.png"))
            eyes_frame.save(os.path.join(self.eyes_dir, f"eyes_{i:06d}.png"))
        
        trace_log("3ストリーム初期フレーム生成完了")
    
    def _mouth_callback(self, is_speaking, amplitude_percent):
        """口ストリーム更新"""
        target_mouth = "ほあー" if is_speaking else "むふ"
        
        if target_mouth != self.current_mouth:
            mouth_frame = self.compositor.create_mouth_part(target_mouth)
            
            with self._frame_lock:
                frame_id = self._frame_no % 60
                mouth_frame.save(os.path.join(self.mouth_dir, f"mouth_{frame_id:06d}.png"))
                self._frame_no += 1
            
            self.current_mouth = target_mouth
            trace_log(f"口ストリーム更新: {target_mouth} ({amplitude_percent:.1f}%)")
    
    def _eyes_render_loop(self):
        """目ストリーム更新ループ"""
        interval = 1.0 / self.fps
        next_time = time.perf_counter()
        
        while not self._stop_event.is_set():
            _, current_eyes = self.expression_state.get_current_expression()
            
            if current_eyes != self.current_eyes:
                eyes_frame = self.compositor.create_eyes_part(current_eyes)
                
                with self._frame_lock:
                    frame_id = self._frame_no % 60
                    eyes_frame.save(os.path.join(self.eyes_dir, f"eyes_{frame_id:06d}.png"))
                    self._frame_no += 1
                
                self.current_eyes = current_eyes
                trace_log(f"目ストリーム更新: {current_eyes}")
            
            next_time += interval
            sleep_time = next_time - time.perf_counter()
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                next_time = time.perf_counter()
    
    def _start_workers(self):
        """音声処理ワーカー"""
        def speech_worker():
            while not self._stop_event.is_set():
                try:
                    text = self.speech_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                
                if not text.strip():
                    self.speech_queue.task_done()
                    continue
                
                trace_log(f"音声生成: {text[:30]}...")
                audio_data = self.voicevox.generate_voice(text)
                
                if audio_data:
                    self.expression_state.set_talking(True)
                    trace_log("音声再生開始（3ストリーム口パク）")
                    self.audio_player.play_audio_data(audio_data, self._stop_event)
                    self.expression_state.set_talking(False)
                    trace_log("音声再生完了")
                
                self.speech_queue.task_done()
        
        self._speech_thread = threading.Thread(target=speech_worker, daemon=True)
        self._speech_thread.start()
    
    def add_speech(self, text: str):
        """音声追加"""
        if text.strip():
            self.speech_queue.put(text)
            trace_log(f"音声追加: {text[:30]}...")
    
    def change_expression(self, mouth: str = None, eyes: str = None):
        """表情変更"""
        if mouth:
            self.expression_state.set_mouth(mouth)
            trace_log(f"口変更: {mouth}")
        if eyes:
            self.expression_state.set_eyes(eyes)
            trace_log(f"目変更: {eyes}")
    
    def stop_stream(self):
        """配信停止"""
        trace_log("3ストリーム配信停止開始")
        self._stop_event.set()
        
        self.blink_animator.stop()
        
        if self._render_thread:
            self._render_thread.join(timeout=2.0)
        
        self.ffmpeg_streamer.stop()
        self.rtmp_server.stop()
        
        trace_log("3ストリーム配信停止完了")
    
    def _clear_streams(self):
        """3ストリームディレクトリクリア"""
        for directory in [self.base_dir, self.mouth_dir, self.eyes_dir]:
            for f in os.listdir(directory):
                if f.endswith(".png"):
                    try:
                        os.remove(os.path.join(directory, f))
                    except:
                        pass
        self._frame_no = 0