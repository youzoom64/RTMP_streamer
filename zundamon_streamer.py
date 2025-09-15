# zundamon_continuous_streamer.py
import os
import subprocess
import time
import threading
import queue
import tempfile
from streamer import VoiceVoxStreamer
from PIL import Image
from psd_tools import PSDImage

class ZundamonContinuousStreamer(VoiceVoxStreamer):
    def __init__(self, psd_path=None):
        super().__init__()
        self.streaming = False
        self.stream_process = None
        self.speech_queue = queue.Queue()
        self.playlist_file = "dynamic_playlist.txt"
        
        # ずんだもんPSD設定
        self.zundamon_psd_path = psd_path
        self.zundamon_frames = None
        if psd_path and os.path.exists(psd_path):
            self.prepare_zundamon_frames()
        
        # バックグラウンドワーカー開始
        self.start_workers()

    def prepare_zundamon_frames(self):
        """ずんだもんフレーム準備"""
        try:
            psd = PSDImage.open(self.zundamon_psd_path)
            base_layers, mouth_open, mouth_closed, eyes_open, eyes_closed = self.separate_zundamon_layers(psd)
            
            if mouth_open and mouth_closed and eyes_open:
                self.zundamon_frames = {
                    'talking': self.composite_zundamon(psd.size, base_layers, mouth_open, eyes_open),
                    'normal': self.composite_zundamon(psd.size, base_layers, mouth_closed, eyes_open)
                }
                print("ずんだもんフレーム準備完了")
            else:
                print("ずんだもんレイヤーが不完全です。音声のみ配信します。")
                
        except Exception as e:
            print(f"ずんだもんフレーム準備失敗: {e}")

    def separate_zundamon_layers(self, psd):
        def flatten_layers(node):
            out = []
            def walk(n):
                for layer in n:
                    if layer.is_group():
                        walk(layer)
                    else:
                        out.append(layer)
            walk(node)
            return out
        
        all_layers = flatten_layers(psd)
        mouth_open = [l for l in all_layers if "ほあー" in l.name]
        mouth_closed = [l for l in all_layers if "むふ" in l.name]
        eyes_open = [l for l in all_layers if any(x in l.name for x in ["黒目","普通目","普通白目"]) and l.is_visible()]
        eyes_closed = [l for l in all_layers if "UU" in l.name]
        base_layers = [l for l in all_layers if l.is_visible() and l not in mouth_open + mouth_closed + eyes_open + eyes_closed]
        
        return base_layers, mouth_open, mouth_closed, eyes_open, eyes_closed

    def composite_zundamon(self, size, base_layers, mouth_layers, eye_layers):
        W, H = size
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        
        for layers in [base_layers, mouth_layers, eye_layers]:
            for layer in layers:
                img = layer.topil()
                bbox = layer.bbox
                x, y = bbox[0], bbox[1]
                full = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                full.paste(img, (x, y))
                canvas = Image.alpha_composite(canvas, full)
        return canvas

    def create_simple_video(self, scene_data, audio_file, output_file):
        """ずんだもん対応版動画作成"""
        if not os.path.exists(audio_file):
            print(f"音声ファイルが存在しません: {audio_file}")
            return False
        
        video_width = scene_data.get("width", 1280)
        video_height = scene_data.get("height", 720)
        
        print(f"動画作成中: {audio_file}")
        
        try:
            if self.zundamon_frames:
                # ずんだもん画像準備
                zundamon_frame = self.zundamon_frames['talking']
                zundamon_resized = zundamon_frame.resize((400, 600), Image.Resampling.LANCZOS)
                
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as img_tmp:
                    zundamon_resized.save(img_tmp.name, 'PNG')
                    zundamon_path = img_tmp.name
                
                # ずんだもん付き動画
                filter_complex = "[1:v][2:v]overlay=50:H-h-50[final]"
                
                cmd = [
                    'ffmpeg', '-y', '-i', audio_file,
                    '-f', 'lavfi', '-i', f'color=c=0x87CEEB:size={video_width}x{video_height}',
                    '-i', zundamon_path,
                    '-filter_complex', filter_complex,
                    '-map', '[final]', '-map', '0:a',
                    '-c:v', 'libx264', '-c:a', 'aac', '-pix_fmt', 'yuv420p', '-shortest', output_file
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                os.unlink(zundamon_path)
            else:
                # 音声のみ（元の処理）
                cmd = [
                    'ffmpeg', '-y', '-i', audio_file,
                    '-f', 'lavfi', '-i', f'color=black:size={video_width}x{video_height}',
                    '-map', '1:v', '-map', '0:a',
                    '-c:v', 'libx264', '-c:a', 'aac', '-pix_fmt', 'yuv420p', '-shortest', output_file
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"動画作成エラー: {result.stderr}")
                return False
            
            print(f"動画作成完了: {output_file}")
            return True
            
        except Exception as e:
            print(f"動画作成エラー: {e}")
            return False

    def create_dynamic_playlist(self, video_files):
        """動的プレイリスト作成"""
        with open(self.playlist_file, 'w', encoding='utf-8') as f:
            for video_file in video_files:
                abs_path = os.path.abspath(video_file).replace('\\', '/')
                f.write(f"file '{abs_path}'\n")

    def start_workers(self):
        """バックグラウンドワーカー開始"""
        self.speech_worker_thread = threading.Thread(target=self.speech_worker, daemon=True)
        self.speech_worker_thread.start()

    def speech_worker(self):
        """音声処理ワーカー（配信継続版）"""
        while True:
            try:
                text = self.speech_queue.get(timeout=1)
                print(f"音声生成中: {text[:30]}...")
                
                # 音声動画作成
                video_file = f"output/speech_{int(time.time())}.mp4"
                scene_data = {"text": text, "speaker_id": 3, "width": 1280, "height": 720}
                audio_file = f"temp_audio_{int(time.time())}.wav"
                
                if self.generate_voice(text, 3, audio_file):
                    if self.create_simple_video(scene_data, audio_file, video_file):
                        # 音声動画を配信に追加
                        self.add_video_to_stream(video_file)
                
                # クリーンアップ
                if os.path.exists(audio_file):
                    os.unlink(audio_file)
                
                self.speech_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"音声処理エラー: {e}")

    def add_video_to_stream(self, speech_video):
        """配信中のストリームに動画を追加"""
        # 音声動画＋待機動画の組み合わせを作成
        combined_video = f"output/combined_{int(time.time())}.mp4"
        concat_list = f"temp_concat_{int(time.time())}.txt"
        
        try:
            # プレイリスト作成：音声動画→待機動画
            with open(concat_list, 'w', encoding='utf-8') as f:
                # 音声動画を1回
                f.write(f"file '{os.path.abspath(speech_video).replace(chr(92), '/')}'\n")
                # 待機動画を再開
                if hasattr(self, 'loop_video_path') and os.path.exists(self.loop_video_path):
                    f.write(f"file '{os.path.abspath(self.loop_video_path).replace(chr(92), '/')}'\n")
            
            # 結合動画作成
            cmd = [
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat_list,
                '-c', 'copy', combined_video
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # 既存配信を新しい結合動画に切り替え
                self.switch_stream_source(combined_video)
            
        finally:
            if os.path.exists(concat_list):
                os.remove(concat_list)

    def switch_stream_source(self, new_video):
        """配信ソースを切り替え"""
        # 現在の配信プロセスを停止
        if self.stream_process:
            self.stream_process.terminate()
            self.stream_process.wait()
        
        # 新しい動画で配信開始
        self.start_continuous_stream_with_video(new_video)

    def start_continuous_stream_with_video(self, video_file):
        """指定された動画で配信開始"""
        cmd = [
            'ffmpeg', '-re', '-stream_loop', '-1', '-i', video_file,
            '-c:v', 'libx264', '-c:a', 'aac', '-f', 'flv', self.rtmp_url
        ]
        
        print(f"配信切り替え: {video_file}")
        
        self.stream_process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        self.streaming = True
        
        # FFmpeg出力監視
        def monitor_ffmpeg():
            try:
                for line in self.stream_process.stdout:
                    print(f"FFmpeg: {line.strip()}")
            except:
                pass
        
        threading.Thread(target=monitor_ffmpeg, daemon=True).start()

    def prepare_all_scenes(self, script_data):
        """シーン準備（ずんだもん対応版）"""
        scenes = script_data.get("scenes", [])
        if not scenes:
            print("シーンが見つかりません")
            return False
            
        print(f"{len(scenes)}個のシーンを準備中...")
        
        for i, scene in enumerate(scenes):
            audio_file = os.path.join(self.audio_dir, f"scene_{i:03d}_audio.wav")
            video_file = os.path.join(self.video_dir, f"scene_{i:03d}_video.mp4")
            
            print(f"[{i+1}/{len(scenes)}] シーン処理中...")
            
            if not self.generate_voice(scene["text"], scene["speaker_id"], audio_file):
                return False
            
            if not self.create_simple_video(scene, audio_file, video_file):
                return False
            
            self.prepared_scenes.append(video_file)
            
        print(f"全{len(self.prepared_scenes)}シーン準備完了")
        return True

    def create_loop_video(self):
        """ループ動画作成"""
        if not self.prepared_scenes:
            print("準備されたシーンがありません")
            return None
        
        loop_video = "output/loop_stream.mp4"
        concat_list = "loop_concat_list.txt"
        
        try:
            with open(concat_list, 'w', encoding='utf-8') as f:
                for _ in range(10):  # 10回ループ
                    for video_file in self.prepared_scenes:
                        abs_path = os.path.abspath(video_file).replace('\\', '/')
                        f.write(f"file '{abs_path}'\n")
            
            cmd = [
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat_list,
                '-c:v', 'libx264', '-c:a', 'aac', loop_video
            ]
            
            print("ループ動画作成中...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"ループ動画作成完了: {loop_video}")
                return loop_video
            else:
                print(f"ループ動画作成失敗: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"ループ動画作成例外: {e}")
            return None
        finally:
            if os.path.exists(concat_list):
                os.remove(concat_list)

    def start_continuous_stream(self):
        """継続配信開始"""
        if not self.check_services():
            print("VoiceVoxサーバーを起動してください")
            return False
        
        if not self.start_rtmp_server():
            print("RTMPサーバー起動失敗")
            return False
        
        time.sleep(2)
        
        # 待機用ループ動画作成
        idle_script = {
            "scenes": [{
                "text": "待機中です。何か話しかけてください。",
                "speaker_id": 3
            }]
        }
        
        if self.prepare_all_scenes(idle_script):
            self.loop_video_path = self.create_loop_video()
            if self.loop_video_path:
                self.start_continuous_stream_with_video(self.loop_video_path)
                print("待機用ループ配信開始")
        
        print("配信開始完了")
        return True

    def add_speech(self, text):
        """音声を配信キューに追加"""
        if text.strip():
            self.speech_queue.put(text)
            print(f"キューに追加: {text[:30]}... (待ち: {self.speech_queue.qsize()})")

    def stop_stream(self):
        """配信停止"""
        if self.stream_process:
            self.stream_process.terminate()
            self.stream_process = None
        
        self.streaming = False
        self.stop_rtmp_server()
        print("配信停止")

def main():
    # ずんだもんPSDパス
    psd_path = "ずんだもん立ち絵素材2.3/ずんだもん立ち絵素材2.3.psd"
    if not os.path.exists(psd_path):
        psd_path = None
        print("PSDファイルが見つかりません。音声のみ配信します。")
    
    streamer = ZundamonContinuousStreamer(psd_path)
    
    try:
        if not streamer.start_continuous_stream():
            return
        
        print("VLCで rtmp://localhost:1935/live/test-stream を開いてください")
        print("配信中です。テキストを入力してください。")
        
        while True:
            text = input("\nずんだもんに話させる内容 (終了: exit): ")
            if text.lower() == 'exit':
                break
            
            streamer.add_speech(text)
            
    except KeyboardInterrupt:
        print("\n配信停止中...")
    finally:
        streamer.stop_stream()

if __name__ == "__main__":
    main()