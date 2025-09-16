"""メインアニメーターエンジン"""
import os
import time
import threading
import queue
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
        self.out_dir = os.path.join(layer_dir, "frames")
        os.makedirs(self.out_dir, exist_ok=True)
        
        # コンポーネント初期化
        self.compositor = ImageCompositor(layer_dir)
        self.voicevox = VoiceVoxClient()
        self.audio_player = AudioPlayer()
        self.expression_state = ExpressionState()
        self.blink_animator = BlinkAnimator(self.expression_state)
        self.rtmp_server = RTMPServer()
        self.ffmpeg_streamer = FFmpegStreamer()
        
        # 内部状態
        self.speech_queue = queue.Queue()
        self._render_thread = None
        self._speech_thread = None
        self._stop_event = threading.Event()
        self._frame_no = 0
        
        # ワーカー開始
        self._start_workers()
        
        trace_log("ZundamonAnimator初期化完了")
    
    def start_layer_stream(self, background_video: str) -> bool:
        """レイヤーアニメーション配信開始"""
        trace_log(f"配信開始要求: {background_video}")
        trace_log(f"背景動画存在確認: {os.path.exists(background_video)}")
        
        if not os.path.exists(background_video):
            trace_log("背景動画が見つかりません", "ERROR")
            return False
        
        trace_log("RTMPサーバー起動開始")
        if not self.rtmp_server.start():
            trace_log("RTMPサーバー起動失敗", "ERROR")
            return False
        trace_log("RTMPサーバー起動完了")
        
        trace_log("配信準備待機開始(1秒)")
        time.sleep(1.0)
        trace_log("配信準備待機完了")
        
        # フレームディレクトリクリア
        trace_log("フレームクリア開始")
        self._clear_frames()
        self._frame_no = 0
        trace_log("フレームクリア完了")
        
        # 先行フレーム生成
        trace_log("先行フレーム生成開始")
        self._seed_frames(seconds=1.0)
        trace_log(f"先行フレーム生成完了: {self._frame_no}フレーム")
        
        # レンダリング開始
        trace_log("レンダリングスレッド開始")
        self._stop_event.clear()
        self._render_thread = threading.Thread(target=self._render_loop, daemon=True)
        self._render_thread.start()
        trace_log("レンダリングスレッド起動完了")
        
        # まばたき開始
        trace_log("まばたきアニメーション開始")
        self.blink_animator.start()
        trace_log("まばたきアニメーション起動完了")
        
        # FFmpeg配信開始
        trace_log("FFmpeg配信開始")
        pattern = os.path.join(self.out_dir, "current_%06d.png")
        trace_log(f"フレームパターン: {pattern}")
        if not self.ffmpeg_streamer.start_stream(
            background_video, pattern, self.rtmp_server.rtmp_url, self.fps
        ):
            trace_log("FFmpeg配信開始失敗", "ERROR")
            self.stop_stream()
            return False
        trace_log("FFmpeg配信開始完了")
        
        trace_log("配信開始完了")
        return True
    
    def stop_stream(self):
        """配信停止"""
        trace_log("配信停止開始")
        self._stop_event.set()
        
        self.blink_animator.stop()
        
        if self._render_thread:
            self._render_thread.join(timeout=2.0)
        
        self.ffmpeg_streamer.stop()
        self.rtmp_server.stop()
        
        trace_log("配信停止完了")
    
    def add_speech(self, text: str):
        """音声追加"""
        if text.strip():
            self.speech_queue.put(text)
            trace_log(f"音声追加: {text[:30]}...")
    
    def change_expression(self, mouth: str = None, eyes: str = None):
        """表情変更"""
        trace_log(f"表情変更要求: mouth={mouth}, eyes={eyes}")
        if mouth:
            self.expression_state.set_mouth(mouth)
            trace_log(f"口変更: {mouth}")
        if eyes:
            self.expression_state.set_eyes(eyes)
            trace_log(f"目変更: {eyes}")
    
    def _start_workers(self):
        """ワーカースレッド開始"""
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
                    
                    # 口パクアニメーション用フラグ
                    mouth_animation_active = True
                    
                    # 口パクアニメーション
                    def mouth_sync():
                        while mouth_animation_active and not self._stop_event.is_set():
                            self.expression_state.set_mouth("ほあー")
                            time.sleep(1.0)  # 1秒
                            if mouth_animation_active:
                                self.expression_state.set_mouth("むふ")
                                time.sleep(1.0)  # 1秒
                    
                    # 口パクスレッド開始
                    mouth_thread = threading.Thread(target=mouth_sync, daemon=True)
                    mouth_thread.start()
                    
                    # 音声再生
                    self.audio_player.play_audio_data(audio_data, self._stop_event)
                    
                    # 音声終了後、口パク停止
                    mouth_animation_active = False
                    self.expression_state.set_talking(False)
                    self.expression_state.set_mouth("むふ")
                
                self.speech_queue.task_done()
        
        self._speech_thread = threading.Thread(target=speech_worker, daemon=True)
        self._speech_thread.start()
    
    def _render_loop(self):
        """フレームレンダリングループ"""
        interval = 1.0 / self.fps
        next_time = time.perf_counter()
        
        while not self._stop_event.is_set():
            mouth, eyes = self.expression_state.get_current_expression()
            frame = self.compositor.compose_expression(mouth, eyes)
            self._save_frame(frame)
            
            next_time += interval
            sleep_time = next_time - time.perf_counter()
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                next_time = time.perf_counter()
    
    def _save_frame(self, frame):
        """フレーム保存"""
        path = os.path.join(self.out_dir, f"current_{self._frame_no:06d}.png")
        frame.save(path)
        self._frame_no += 1
    
    def _seed_frames(self, seconds: float = 1.0):
        """先行フレーム生成"""
        n = max(1, int(self.fps * seconds))
        for _ in range(n):
            mouth, eyes = self.expression_state.get_current_expression()
            frame = self.compositor.compose_expression(mouth, eyes)
            self._save_frame(frame)
    
    def _clear_frames(self):
        """フレームディレクトリクリア"""
        for f in os.listdir(self.out_dir):
            if f.startswith("current_") and f.endswith(".png"):
                try:
                    os.remove(os.path.join(self.out_dir, f))
                except:
                    pass