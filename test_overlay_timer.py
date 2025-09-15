# zundamon_layered_realtime_streamer.py
import os
import subprocess
import time
import threading
import tempfile
import queue
import requests
from streamer import VoiceVoxStreamer
from PIL import Image
from psd_tools import PSDImage
import pygame

class ZundamonLayeredRealtimeStreamer(VoiceVoxStreamer):
    def __init__(self, psd_path):
        super().__init__()
        self.psd_path = psd_path
        self.speech_queue = queue.Queue()
        self.stream_process = None
        self.is_talking = False
        self.is_blinking = False
        
        # レイヤーファイル名
        self.base_image = "layer_base.png"
        self.mouth_open_image = "layer_mouth_open.png"
        self.mouth_closed_image = "layer_mouth_closed.png"
        self.eyes_open_image = "layer_eyes_open.png"
        self.eyes_closed_image = "layer_eyes_closed.png"
        
        pygame.mixer.init()
        
        if psd_path and os.path.exists(psd_path):
            self.create_separate_layer_pngs()
        else:
            self.create_fallback_layers()
        
        self.start_speech_worker()
        self.start_blink_worker()

    def create_separate_layer_pngs(self):
        """PSDから個別レイヤーPNG作成"""
        try:
            psd = PSDImage.open(self.psd_path)
            base_layers, mouth_open, mouth_closed, eyes_open, eyes_closed = self.separate_zundamon_layers(psd)
            
            if base_layers and mouth_open and mouth_closed and eyes_open and eyes_closed:
                # 1. 全身ベース（口・目なし）
                base_composite = self.composite_layers(psd.size, base_layers, [], [])
                base_resized = base_composite.resize((300, 450), Image.Resampling.LANCZOS)
                base_resized.save(self.base_image, 'PNG')
                
                # 2. 口開きレイヤー
                mouth_open_composite = self.composite_layers(psd.size, [], mouth_open, [])
                mouth_open_resized = mouth_open_composite.resize((300, 450), Image.Resampling.LANCZOS)  
                mouth_open_resized.save(self.mouth_open_image, 'PNG')
                
                # 3. 口閉じレイヤー
                mouth_closed_composite = self.composite_layers(psd.size, [], mouth_closed, [])
                mouth_closed_resized = mouth_closed_composite.resize((300, 450), Image.Resampling.LANCZOS)
                mouth_closed_resized.save(self.mouth_closed_image, 'PNG')
                
                # 4. 目開きレイヤー
                eyes_open_composite = self.composite_layers(psd.size, [], [], eyes_open)
                eyes_open_resized = eyes_open_composite.resize((300, 450), Image.Resampling.LANCZOS)
                eyes_open_resized.save(self.eyes_open_image, 'PNG')
                
                # 5. 目閉じレイヤー
                eyes_closed_composite = self.composite_layers(psd.size, [], [], eyes_closed)
                eyes_closed_resized = eyes_closed_composite.resize((300, 450), Image.Resampling.LANCZOS)
                eyes_closed_resized.save(self.eyes_closed_image, 'PNG')
                
                print("PSD個別レイヤー作成完了")
            else:
                print("PSDレイヤーが不完全 - フォールバック使用")
                self.create_fallback_layers()
                
        except Exception as e:
            print(f"PSD処理エラー: {e} - フォールバック使用")
            self.create_fallback_layers()

    def create_fallback_layers(self):
        """フォールバック個別レイヤー作成"""
        base_img = Image.new('RGBA', (300, 450), (100, 200, 100, 150))
        mouth_open_img = Image.new('RGBA', (300, 450), (255, 100, 100, 200))
        mouth_closed_img = Image.new('RGBA', (300, 450), (200, 100, 100, 150))
        eyes_open_img = Image.new('RGBA', (300, 450), (100, 100, 255, 200))
        eyes_closed_img = Image.new('RGBA', (300, 450), (50, 50, 150, 200))
        
        base_img.save(self.base_image, 'PNG')
        mouth_open_img.save(self.mouth_open_image, 'PNG')
        mouth_closed_img.save(self.mouth_closed_image, 'PNG')
        eyes_open_img.save(self.eyes_open_image, 'PNG')
        eyes_closed_img.save(self.eyes_closed_image, 'PNG')

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

    def composite_layers(self, size, base_layers, mouth_layers, eye_layers):
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

    def start_speech_worker(self):
        def speech_worker():
            while True:
                try:
                    text = self.speech_queue.get(timeout=1)
                    print(f"音声生成中: {text[:30]}...")
                    
                    audio_data = self.generate_voice_data(text, speaker_id=3)
                    if audio_data:
                        self.is_talking = True
                        self.play_audio_data(audio_data)
                        self.is_talking = False
                    
                    self.speech_queue.task_done()
                    
                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"音声処理エラー: {e}")
        
        threading.Thread(target=speech_worker, daemon=True).start()

    def start_blink_worker(self):
        def blink_worker():
            while True:
                if not self.is_talking:  # 話していない時のみまばたき
                    self.is_blinking = True
                    time.sleep(0.15)  # まばたき時間
                    self.is_blinking = False
                    time.sleep(2 + (time.time() % 3))  # 2-5秒間隔
                else:
                    time.sleep(0.1)
        
        threading.Thread(target=blink_worker, daemon=True).start()

    def generate_voice_data(self, text, speaker_id=3):
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
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_file.write(audio_data)
                tmp_file_path = tmp_file.name
            
            pygame.mixer.music.load(tmp_file_path)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            
            os.unlink(tmp_file_path)
            
        except Exception as e:
            print(f"音声再生エラー: {e}")

    def add_speech(self, text):
        if text.strip():
            self.speech_queue.put(text)
            print(f"音声キューに追加: {text[:30]}...")

    def start_layered_stream(self, background_video):
        """レイヤー別リアルタイム配信（条件式なし版）"""
        if not os.path.exists(background_video):
            print(f"背景動画が見つかりません: {background_video}")
            return False
            
        if not self.start_rtmp_server():
            return False
        
        time.sleep(3)
        
        cmd = [
            'ffmpeg',
            '-stream_loop', '-1', '-i', background_video,      # 背景動画
            '-loop', '1', '-i', self.base_image,               # ベース全身
            '-loop', '1', '-i', self.mouth_closed_image,       # 口閉じ
            '-loop', '1', '-i', self.eyes_open_image,          # 目開き
            '-filter_complex',
            # シンプルなレイヤー合成のみ
            '[1:v][2:v]overlay[base_mouth];'           # ベース + 口閉じ
            '[base_mouth][3:v]overlay[zundamon];'      # + 目開き
            '[0:v][zundamon]overlay=50:H-h-50[out]',   # 背景に合成
            '-map', '[out]', '-map', '0:a',
            '-c:v', 'libx264', '-preset', 'ultrafast',
            '-c:a', 'aac', '-f', 'flv', self.rtmp_url
        ]
        
        print("レイヤー別配信開始（基本版）")
        
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
            return False
        
        print("配信開始完了")
        return True

    def stop_stream(self):
        if self.stream_process:
            self.stream_process.terminate()
            self.stream_process = None
        self.stop_rtmp_server()
        
        # レイヤーファイル削除
        for layer_file in [self.base_image, self.mouth_open_image, self.mouth_closed_image, 
                          self.eyes_open_image, self.eyes_closed_image]:
            if os.path.exists(layer_file):
                os.unlink(layer_file)
        
        print("配信停止")

def main():
    psd_path = "ずんだもん立ち絵素材2.3/ずんだもん立ち絵素材2.3.psd"
    background_video = "D:/Bandicam/CharaStudio 2025-04-01 11-45-21-752.mp4"
    
    if not os.path.exists(background_video):
        print(f"背景動画が見つかりません: {background_video}")
        return
    
    streamer = ZundamonLayeredRealtimeStreamer(psd_path)
    
    try:
        if not streamer.start_layered_stream(background_video):
            return
        
        print("VLCで rtmp://localhost:1935/live/test-stream を開いてください")
        print("PSDレイヤー別制御によるずんだもんが表示されます")
        print("テキスト入力で音声合成、exitで終了")
        
        while True:
            text = input("\n入力: ")
            if text.lower() == 'exit':
                break
            else:
                streamer.add_speech(text)
            
    except KeyboardInterrupt:
        print("\n配信停止中...")
    finally:
        streamer.stop_stream()

if __name__ == "__main__":
    main()